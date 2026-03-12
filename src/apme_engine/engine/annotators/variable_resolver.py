from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apme_engine.engine.annotators.annotator_base import Annotator, AnnotatorResult
from apme_engine.engine.context import Context, resolve_module_options
from apme_engine.engine.keyutil import detect_type
from apme_engine.engine.models import (
    Arguments,
    ArgumentsType,
    CallObject,
    Object,
    ObjectList,
    Playbook,
    Repository,
    Role,
    TaskCall,
    Variable,
    VariableAnnotation,
    VariableType,
)


class VariableAnnotator(Annotator):
    type: str = VariableAnnotation.type
    context: Context

    def __init__(self, context: Context) -> None:
        super().__init__(context=context)
        self.context = context

    def run(self, taskcall: TaskCall) -> VariableAnnotatorResult:
        resolved = resolve_module_options(self.context, taskcall)
        resolved_module_options = resolved[0]
        resolved_variables = resolved[1]
        # mutable_vars_per_mo = resolved[2]
        used_variables = resolved[3]
        _vars = []
        is_mutable = False
        for rv in resolved_variables:
            v_name = rv.get("key", "")
            v_value = rv.get("value", "")
            v_type = rv.get("type", VariableType.Unknown)
            elements = []
            if v_name in used_variables:
                if not isinstance(used_variables[v_name], dict):
                    continue
                for u_v_name, info in used_variables[v_name].items():
                    if u_v_name == v_name:
                        continue
                    u_v_value = info.get("value", "")
                    u_v_type = info.get("type", VariableType.Unknown)
                    u_v = Variable(
                        name=u_v_name,
                        value=u_v_value,
                        type=u_v_type,
                        used_in=taskcall.key,
                    )
                    elements.append(u_v)
            v = Variable(
                name=v_name,
                value=v_value,
                type=v_type,
                elements=elements,
                used_in=taskcall.key,
            )
            _vars.append(v)
            if v.is_mutable:
                is_mutable = True

        for v in _vars:
            history = self.context.var_use_history.get(v.name, [])
            history.append(v)
            self.context.var_use_history[v.name] = history

        m_opts = getattr(taskcall.spec, "module_options", None)
        if isinstance(m_opts, list):
            args_type = ArgumentsType.LIST
        elif isinstance(m_opts, dict):
            args_type = ArgumentsType.DICT
        else:
            args_type = ArgumentsType.SIMPLE
        args = Arguments(
            type=args_type,
            raw=m_opts,
            vars=_vars,
            resolved=True,  # TODO: False if not resolved
            templated=resolved_module_options,
            is_mutable=is_mutable,
        )
        taskcall.args = args
        # deep copy the history here because the context is updated by subsequent taskcalls
        if self.context.var_set_history:
            taskcall.variable_set = self.context.var_set_history.copy()
        if self.context.var_use_history:
            taskcall.variable_use = self.context.var_use_history.copy()
        taskcall.become = self.context.become
        taskcall.module_defaults = self.context.module_defaults

        return VariableAnnotatorResult()


@dataclass
class VariableAnnotatorResult(AnnotatorResult):
    pass


def tree_to_task_list(tree: Any, node_objects: ObjectList) -> list[dict[str, Any]]:
    """Convert tree (TreeNode-like with .key, .children) to task list. tree is unused/dead."""
    node_dict: dict[str, Object | CallObject] = {}
    for no in node_objects.items:
        node_dict[no.key] = no

    def getSubTree(node: Any) -> tuple[list[dict[str, Any]], str]:
        tasks: list[dict[str, Any]] = []
        resolved_name = ""
        no = node_dict[node.key]
        node_type = detect_type(node.key)

        children_tasks: list[dict[str, Any]] = []
        if node_type == "module" or node_type == "role":
            resolved_name = getattr(no, "fqcn", "")
        elif node_type == "taskfile":
            resolved_name = no.key

        children_per_type: dict[str, list[Object | CallObject]] = {}
        for c in node.children:
            ctype = detect_type(c.key)
            if ctype in children_per_type:
                children_per_type[ctype].append(c)
            else:
                children_per_type[ctype] = [c]

        # obj["children_types"] = list(children_per_type.keys())
        if "playbook" in children_per_type:
            tasks_per_children = [getSubTree(c) for c in children_per_type["playbook"]]
            for _tasks, _ in tasks_per_children:
                children_tasks.extend(_tasks)
        if "play" in children_per_type:
            tasks_per_children = [getSubTree(c) for c in children_per_type["play"]]
            for _tasks, _ in tasks_per_children:
                children_tasks.extend(_tasks)
        if "role" in children_per_type:
            tasks_per_children = [getSubTree(c) for c in children_per_type["role"]]
            for _tasks, _ in tasks_per_children:
                children_tasks.extend(_tasks)
            if node_type == "task":
                fqcns = [fqcn for (_, fqcn) in tasks_per_children]
                resolved_name = fqcns[0] if len(fqcns) > 0 else ""
        if "taskfile" in children_per_type:
            tasks_per_children = [getSubTree(c) for c in children_per_type["taskfile"]]
            for _tasks, _ in tasks_per_children:
                children_tasks.extend(_tasks)
            if node_type == "task":
                _tf_path_list = [_tf_path for (_, _tf_path) in tasks_per_children]
                resolved_name = _tf_path_list[0] if len(_tf_path_list) > 0 else ""
        if "task" in children_per_type:
            tasks_per_children = [getSubTree(c) for c in children_per_type["task"]]
            for _tasks, _ in tasks_per_children:
                children_tasks.extend(_tasks)
        if "module" in children_per_type and node_type == "task":
            fqcns = [getSubTree(c)[1] for c in children_per_type["module"]]
            resolved_name = fqcns[0] if len(fqcns) > 0 else ""

        if node_type == "task":
            no.resolved_name = resolved_name  # type: ignore[union-attr]
            tasks.append(no.__dict__)
        tasks.extend(children_tasks)
        return tasks, resolved_name

    root = tree.items[0] if isinstance(tree, ObjectList) and tree.items else tree
    tasks, _ = getSubTree(root)
    return tasks


def resolve_variables(tree: ObjectList, additional: ObjectList) -> list[TaskCall]:
    first_item = tree.items[0] if len(tree.items) > 0 else None
    tree_root_key = getattr(getattr(first_item, "spec", None), "key", "") if first_item else ""
    inventories = get_inventories(tree_root_key, additional)
    context = Context(inventories=inventories)
    depth_dict: dict[str, int] = {}
    resolved_taskcalls: list[TaskCall] = []
    for call_obj in tree.items:
        caller_depth_lvl = 0
        called_from = getattr(call_obj, "called_from", "")
        if called_from != "":
            caller_key = called_from
            caller_depth_lvl = depth_dict.get(caller_key, 0)
        depth_lvl = caller_depth_lvl + 1
        depth_dict[call_obj.key] = depth_lvl
        context.add(call_obj, depth_lvl)
        if isinstance(call_obj, TaskCall):
            result = VariableAnnotator(context=context).run(call_obj)
            if not result:
                continue
            if result.annotations:
                call_obj.annotations.extend(result.annotations)
            resolved_taskcalls.append(call_obj)
    return resolved_taskcalls


def get_inventories(tree_root_key: str, additional: ObjectList) -> list[Any]:
    if tree_root_key == "":
        return []
    tree_root_type = detect_type(tree_root_key)
    projects = additional.find_by_type("repository")
    inventories = []
    found = False
    for p in projects:
        if not isinstance(p, Repository):
            continue
        if tree_root_type == "playbook":
            for playbook in p.playbooks:
                if isinstance(playbook, str):
                    if playbook == tree_root_key:
                        inventories = p.inventories
                        found = True
                elif isinstance(playbook, Playbook) and playbook.key == tree_root_key:
                    inventories = p.inventories
                    found = True
                if found:
                    break
        elif tree_root_type == "role":
            for role in p.roles:
                if isinstance(role, str):
                    if role == tree_root_key:
                        inventories = p.inventories
                        found = True
                elif isinstance(role, Role) and role.key == tree_root_key:
                    inventories = p.inventories
                    found = True
                if found:
                    break
        if found:
            break
    return inventories
