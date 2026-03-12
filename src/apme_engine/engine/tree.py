from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, cast

from . import logger
from .keyutil import detect_type, key_delimiter, object_delimiter
from .model_loader import load_builtin_modules
from .models import (
    CallObject,
    ExecutableType,
    LoadType,
    Module,
    Object,
    ObjectList,
    Play,
    Playbook,
    PlayCall,
    Role,
    RoleCall,
    RoleInPlay,
    Task,
    TaskCall,
    TaskFile,
    call_obj_from_spec,
)
from .risk_assessment_model import RAMClient

obj_type_dict = {
    "playbook": "playbooks",
    "play": "plays",
    "role": "roles",
    "taskfile": "taskfiles",
    "task": "tasks",
    "module": "modules",
}


@dataclass
class TreeNode:
    key: str = ""

    # children is a list of TreeNode
    children: list[TreeNode] = field(default_factory=list)

    definition: dict[str, Any] = field(default_factory=dict)

    # load a list of (src, dst) as a tree structure
    # which is composed of multiple TreeNode
    @staticmethod
    def load(graph: list[tuple[str | None, str]] | None = None) -> TreeNode:
        if graph is None:
            graph = []
        root_key_cands = [pair[1] for pair in graph if pair[0] is None]
        if len(root_key_cands) != 1:
            raise ValueError(f"tree array must have only one top with src == None, but found {len(root_key_cands)}")
        root_key = root_key_cands[0]
        tree = TreeNode()
        tree, _ = tree.recursive_tree_load(root_key, graph)
        tree.key = root_key
        tree.children = tree.children
        tree.definition = tree.definition
        return tree

    # output list of (src, dst) to stdout or file
    def dump(self, path: str = "") -> None:
        src_dst_array = self.to_graph()
        if path == "":
            print(json.dumps(src_dst_array, indent=2))
        else:
            tree_json = json.dumps(src_dst_array)
            with open(path, "w") as file:
                file.write(tree_json)

    def to_str(self) -> str:
        src_dst_array = self.to_graph()
        return json.dumps(src_dst_array)

    # return list of (src, dst)
    def to_graph(self) -> list[tuple[str | None, str]]:
        return self.recursive_graph_dump(None, self)

    # return list of dst keys
    def to_keys(self) -> list[str]:
        return [p[1] for p in self.to_graph()]

    # reutrn list of TreeNodes that are under this TreeNode
    def to_list(self) -> list[TreeNode]:
        return self.recursive_convert_to_list(self)

    def recursive_convert_to_list(self, node: TreeNode, nodelist: list[TreeNode] | None = None) -> list[TreeNode]:
        if nodelist is None:
            nodelist = []
        current = [pair for pair in nodelist]
        current.append(node)
        for child_node in node.children:
            current = self.recursive_convert_to_list(child_node, current)
        return current

    def recursive_tree_load(
        self,
        node_key: str,
        src_dst_array: list[tuple[str | None, str]],
        parent_keys: set[str] | None = None,
    ) -> tuple[TreeNode, set[str]]:
        if parent_keys is None:
            parent_keys = set()
        n = TreeNode(key=node_key)
        if node_key in parent_keys:
            return n, parent_keys
        parent_keys.add(node_key)
        new_parent_keys = parent_keys.copy()
        for src_key, dst_key in src_dst_array:
            children_keys = []
            if node_key == src_key:
                children_keys.append(dst_key)
            for c_key in children_keys:
                child_tree, sub_parent_keys = self.recursive_tree_load(c_key, src_dst_array, parent_keys)
                n.children.append(child_tree)
                new_parent_keys = new_parent_keys.union(sub_parent_keys)
        return n, new_parent_keys

    def recursive_graph_dump(
        self,
        parent_node: TreeNode | None,
        node: TreeNode,
        src_dst_array: list[tuple[str | None, str]] | None = None,
    ) -> list[tuple[str | None, str]]:
        if src_dst_array is None:
            src_dst_array = []
        current = [pair for pair in src_dst_array]
        src = None if parent_node is None else parent_node.key
        dst = node.key
        current.append((src, dst))
        for child_node in node.children:
            is_included = len([(src, dst) for (src, dst) in current if src == child_node.key]) > 0
            if is_included:
                continue
            current = self.recursive_graph_dump(node, child_node, current)
        return current

    # return a list of (src, dst) which ends with the "end_key"
    # this could return multiple paths
    def path_to_root(self, end_key: str) -> list[TreeNode]:
        path_array = self.search_branch_to_key(end_key, self)
        return [nodelist2branch(nodelist) for nodelist in path_array]

    def search_branch_to_key(
        self,
        search_key: str,
        node: TreeNode,
        ancestors: list[TreeNode] | None = None,
    ) -> list[list[TreeNode]]:
        if ancestors is None:
            ancestors = []
        current = [n for n in ancestors]
        found: list[list[TreeNode]] = []
        if node.key == search_key:
            found.append(current + [node])
        for child_node in node.children:
            found_in_child = self.search_branch_to_key(search_key, child_node, current + [node])
            found.extend(found_in_child)
        return found

    def copy(self) -> TreeNode:
        return deepcopy(self)

    @property
    def is_empty(self) -> bool:
        return self.key == "" and len(self.children) == 0

    @property
    def has_definition(self) -> bool:
        return len(self.definition) == 0


def nodelist2branch(nodelist: list[TreeNode]) -> TreeNode:
    if len(nodelist) == 0:
        return TreeNode()
    t = nodelist[0].copy()
    current = t
    for i, n in enumerate(nodelist):
        if i == 0:
            continue
        current.children = [n.copy()]
        current = current.children[0]
    return t


def load_single_definition(defs: dict[str, Any], key: str) -> ObjectList:
    obj_list = ObjectList()
    items = defs.get(key, [])
    for item in items:
        obj_list.add(item)
    return obj_list


def load_definitions(defs: dict[str, Any], types: list[str]) -> list[ObjectList]:
    def_list = []
    for type_key in types:
        objs_per_type = load_single_definition(defs, type_key)
        def_list.append(objs_per_type)
    return def_list


def load_all_definitions(definitions: dict[str, Any]) -> dict[str, ObjectList]:
    _definitions: dict[str, Any] = {}
    _definitions = {"root": definitions} if "mappings" in definitions else definitions
    loaded: dict[str, ObjectList] = {}
    types = ["collections", "roles", "taskfiles", "modules", "playbooks", "plays", "tasks"]
    for type_key in types:
        loaded[type_key] = ObjectList()
    for _, definitions_per_artifact in _definitions.items():
        def_list = load_definitions(definitions_per_artifact.get("definitions", {}), types)
        for i, type_key in enumerate(types):
            if type_key not in loaded:
                loaded[type_key] = def_list[i]
            else:
                loaded[type_key].merge(def_list[i])
    return loaded


def make_dicts(root_definitions: dict[str, Any], ext_definitions: dict[str, Any]) -> dict[str, dict[str, Any]]:
    definitions: dict[str, ObjectList] = {
        "roles": ObjectList(),
        "modules": ObjectList(),
        "taskfiles": ObjectList(),
        "playbooks": ObjectList(),
    }
    for type_key in definitions:
        definitions[type_key].merge(root_definitions.get(type_key, ObjectList()))
        definitions[type_key].merge(ext_definitions.get(type_key, ObjectList()))
    dicts: dict[str, dict[str, Any]] = {k: {} for k in definitions}
    for type_key, obj_list in definitions.items():
        for obj in obj_list.items:
            obj_dict_key = obj.fqcn if hasattr(obj, "fqcn") else obj.key
            if type_key not in dicts:
                dicts[type_key] = {}
            dicts[type_key][obj_dict_key] = obj
    return dicts


def load_module_redirects(
    root_definitions: dict[str, Any],
    ext_definitions: dict[str, Any],
    module_dict: dict[str, Any] | None = None,
) -> dict[str, str]:
    if module_dict is None:
        module_dict = {}
    collection_list = root_definitions.get("collections", ObjectList())
    ext_collection_list = ext_definitions.get("collections", ObjectList())
    collection_list.merge(ext_collection_list)
    redirects = {}
    for coll in collection_list.items:
        if not coll.meta_runtime:
            continue
        for short_name, routing in coll.meta_runtime.get("plugin_routing", {}).get("modules", {}).items():
            redirect_to = routing.get("redirect", "")
            if short_name in redirects:
                continue
            found_module = module_dict.get(redirect_to)
            if found_module:
                module_key = found_module.key
                redirects[short_name] = module_key
    return redirects


def resolve(obj: Task | Play, dicts: dict[str, dict[str, Any]]) -> tuple[Task | Play, bool]:
    failed = False
    if isinstance(obj, Task):
        task = obj
        if task.executable != "":
            if task.executable_type == ExecutableType.MODULE_TYPE:
                task.resolved_name = resolve_module(task.executable, dicts.get("modules", {}))
            elif task.executable_type == ExecutableType.ROLE_TYPE:
                task.resolved_name = resolve_role(
                    task.executable,
                    dicts.get("roles", {}),
                    task.collection,
                    task.collections_in_play,
                )
            elif task.executable_type == ExecutableType.TASKFILE_TYPE:
                task.resolved_name = resolve_taskfile(task.executable, dicts.get("taskfiles", {}), task.key)
            if task.resolved_name == "":
                failed = True
    elif isinstance(obj, Play):
        for i in range(len(obj.roles)):
            roleinplay = obj.roles[i]
            if not isinstance(roleinplay, RoleInPlay):
                continue
            roleinplay.resolved_name = resolve_role(
                roleinplay.name,
                dicts.get("roles", {}),
                roleinplay.collection,
                roleinplay.collections_in_play,
            )
            obj.roles[i] = roleinplay
            if roleinplay.resolved_name == "":
                failed = True
    return obj, failed


def resolve_module(
    module_name: str,
    module_dict: dict[str, Any] | None = None,
    module_redirects: dict[str, str] | None = None,
) -> str:
    if module_redirects is None:
        module_redirects = {}
    if module_dict is None:
        module_dict = {}
    module_key = ""
    found_module = module_dict.get(module_name)
    if found_module is not None:
        module_key = found_module.key
    if module_key == "":
        for k in module_dict:
            suffix = f".{module_name}"
            if k.endswith(suffix):
                module_key = module_dict[k].key
                break
    if module_key == "" and module_name in module_redirects:
        module_key = module_redirects[module_name]
    return module_key


def resolve_role(
    role_name: str,
    role_dict: dict[str, Any] | None = None,
    my_collection_name: str = "",
    collections_in_play: list[str] | None = None,
) -> str:
    if collections_in_play is None:
        collections_in_play = []
    if role_dict is None:
        role_dict = {}
    if os.sep in role_name:
        role_name = os.path.basename(role_name)

    role_key = ""
    if "." not in role_name and len(collections_in_play) > 0:
        for coll in collections_in_play:
            role_name_cand = f"{coll}.{role_name}"
            found_role = role_dict.get(role_name_cand)
            if found_role is not None:
                role_key = found_role.key
    else:
        if "." not in role_name and my_collection_name != "":
            role_name_cand = f"{my_collection_name}.{role_name}"
            found_role = role_dict.get(role_name_cand)
            if found_role is not None:
                role_key = found_role.key
    if role_key == "":
        found_role = role_dict.get(role_name)
        if found_role is not None:
            role_key = found_role.key
        else:
            for k in role_dict:
                suffix = f".{role_name}"
                if k.endswith(suffix):
                    role_key = role_dict[k].key
                    break
    return role_key


def resolve_taskfile(
    taskfile_ref: str,
    taskfile_dict: dict[str, Any] | None = None,
    task_key: str = "",
) -> str:
    if taskfile_dict is None:
        taskfile_dict = {}
    type_prefix = "task "
    parts = task_key[len(type_prefix) :].split(object_delimiter)
    parent_key = ""
    task_defined_path = ""
    for p in parts[::-1]:
        if p.startswith("playbook" + key_delimiter) or p.startswith("taskfile" + key_delimiter):
            task_defined_path = p.split(key_delimiter)[1]
            parent_key = task_key[len(type_prefix) :].split(p)[0]
            break

    # include/import tasks can have a path like "roles/xxxx/tasks/yyyy.yml"
    # then try to find roles directory
    if taskfile_ref.startswith("roles/") and "roles/" in task_defined_path:
        roles_parent_dir = task_defined_path.split("roles/")[0]
        fpath = os.path.join(roles_parent_dir, taskfile_ref)
        fpath = os.path.normpath(fpath)
        taskfile_key = f"taskfile {parent_key}taskfile{key_delimiter}{fpath}"
        found_tf = taskfile_dict.get(taskfile_key)
        if found_tf is not None:
            return str(found_tf.key)

    task_dir = os.path.dirname(task_defined_path)
    fpath = os.path.join(task_dir, taskfile_ref)
    # need to normalize path here because taskfile_ref can be
    # something like "../some_taskfile.yml".
    # it should be "tasks/some_taskfile.yml"
    fpath = os.path.normpath(fpath)
    taskfile_key = f"taskfile {parent_key}taskfile{key_delimiter}{fpath}"
    found_tf = taskfile_dict.get(taskfile_key)
    if found_tf is not None:
        return str(found_tf.key)

    return ""


def resolve_playbook(
    playbook_ref: str,
    playbook_dict: dict[str, Any] | None = None,
    play_key: str = "",
) -> str:
    if playbook_dict is None:
        playbook_dict = {}
    type_prefix = "play "
    parts = play_key[len(type_prefix) :].split(object_delimiter)
    parent_key = ""
    play_defined_path = ""
    for p in parts[::-1]:
        if p.startswith("playbook" + key_delimiter):
            play_defined_path = p.split(key_delimiter)[1]
            parent_key = play_key[len(type_prefix) :].split(p)[0]
            break

    play_dir = os.path.dirname(play_defined_path)
    fpath = os.path.join(play_dir, playbook_ref)
    # need to normalize path here because playbook_ref can be
    # something like "../some_playbook.yml"
    fpath = os.path.normpath(fpath)
    playbook_key = f"playbook {parent_key}playbook{key_delimiter}{fpath}"
    found_playbook = playbook_dict.get(playbook_key)
    if found_playbook is not None:
        return str(found_playbook.key)
    return ""


def init_builtin_modules() -> list[Any]:
    builtin_module_dict = load_builtin_modules()
    modules = list(builtin_module_dict.values())
    return modules


class TreeLoader:
    def __init__(
        self,
        root_definitions: dict[str, Any],
        ext_definitions: dict[str, Any],
        ram_client: RAMClient | None = None,
        target_playbook_path: str | None = None,
        target_taskfile_path: str | None = None,
        load_all_taskfiles: bool = False,
    ) -> None:
        self.ram_client: RAMClient | None = ram_client

        self.org_root_definitions = root_definitions
        self.org_ext_definitions = ext_definitions

        self.root_definitions = load_all_definitions(root_definitions)
        self.ext_definitions = load_all_definitions(ext_definitions)
        self.add_builtin_modules()

        self.dicts = make_dicts(self.root_definitions, self.ext_definitions)

        self.module_redirects = load_module_redirects(
            self.root_definitions, self.ext_definitions, self.dicts["modules"]
        )

        # use mappings just to get tree tops (playbook/role)
        # we don't load any files by this mappings here
        self.load_and_mapping = root_definitions.get("mappings")
        load_mapping = self.load_and_mapping
        self.playbook_mappings = load_mapping.playbooks if load_mapping else []
        self.role_mappings = load_mapping.roles if load_mapping else []
        self.taskfile_mappings = []

        # role can have child playbooks (mostly for test)
        # we add them to playbook_mappins here
        if self.role_mappings:
            for mapping in self.role_mappings:
                role_key = mapping[1]
                role = self.get_object(role_key, False)
                if not role or not isinstance(role, Role):
                    continue
                playbook_keys = role.playbooks
                playbook_mappings_in_role = [(None, p_key) for p_key in playbook_keys]
                self.playbook_mappings.extend(playbook_mappings_in_role)

        if target_playbook_path:
            self.playbook_mappings = [p for p in self.playbook_mappings if p[0] == target_playbook_path]
            self.role_mappings = []

        # some taskfiles might not be included from `tasks/main.yml` of a role.
        # ARI does not scan them by default, but it does when `load_all_taskfiles == True`
        if load_all_taskfiles:
            for mapping in self.role_mappings:
                role_key = mapping[1]
                role = self.get_object(role_key, False)
                if not role or not isinstance(role, Role):
                    continue
                taskfile_keys = role.taskfiles
                taskfile_mappings_in_role = [(None, tf_key) for tf_key in taskfile_keys]
                self.taskfile_mappings.extend(taskfile_mappings_in_role)
            self.taskfile_mappings.extend(load_mapping.taskfiles if load_mapping else [])
        # or, if the scan is for a single taskfile, ARI just scans it
        elif target_taskfile_path:
            self.taskfile_mappings = load_mapping.taskfiles if load_mapping else []
            self.taskfile_mappings = [tf for tf in self.taskfile_mappings if tf[0] == target_taskfile_path]
            self.playbook_mappings = []
            self.role_mappings = []

        # TODO: dependency check, especially for
        # collection dependencies for role

        self.target_playbook_path = target_playbook_path
        self.load_all_taskfiles = load_all_taskfiles

        self.module_resolve_cache: dict[str, str] = {}
        self.role_resolve_cache: dict[str, str] = {}
        self.taskfile_resolve_cache: dict[str, str] = {}

        self.resolved_module_from_ram: dict[str, tuple[str, str]] = {}
        self.resolved_role_from_ram: dict[str, tuple[str, str]] = {}
        self.resolved_taskfile_from_ram: dict[str, tuple[str, str]] = {}

        self.extra_requirements: list[dict[str, Any]] = []
        self.extra_requirement_obj_set: set[str] = set()

        self.trees: list[ObjectList] = []

        self.resolve_failures: dict[str, dict[str, int]] = {
            "module": {},
            "taskfile": {},
            "role": {},
        }
        return

    def run(self) -> tuple[list[ObjectList], ObjectList]:
        additional_objects = ObjectList()
        if self.load_and_mapping and self.load_and_mapping.target_type == LoadType.PROJECT:
            p_defs = self.org_root_definitions.get("definitions", {}).get("projects", [])
            if len(p_defs) > 0:
                additional_objects.add(p_defs[0])
        covered_taskfiles = []
        for i, mapping in enumerate(self.playbook_mappings):
            logger.debug(f"[{i + 1}/{len(self.playbook_mappings)}] {mapping[1]}")
            playbook_key = mapping[1]
            tree_objects = self._recursive_get_calls(playbook_key)
            self.trees.append(tree_objects)

            if self.load_all_taskfiles and tree_objects and tree_objects.items:
                for call_obj in tree_objects.items:
                    if not isinstance(call_obj, CallObject):
                        continue
                    spec_obj = call_obj.spec
                    if isinstance(spec_obj, TaskFile):
                        taskfile_key = spec_obj.key
                        if taskfile_key not in covered_taskfiles:
                            covered_taskfiles.append(taskfile_key)

        for i, mapping in enumerate(self.role_mappings):
            logger.debug(f"[{i + 1}/{len(self.role_mappings)}] {mapping[1]}")
            role_key = mapping[1]
            tree_objects = self._recursive_get_calls(role_key)
            self.trees.append(tree_objects)

            if self.load_all_taskfiles and tree_objects and tree_objects.items:
                for call_obj in tree_objects.items:
                    if not isinstance(call_obj, CallObject):
                        continue
                    spec_obj = call_obj.spec
                    if isinstance(spec_obj, TaskFile):
                        taskfile_key = spec_obj.key
                        if taskfile_key not in covered_taskfiles:
                            covered_taskfiles.append(taskfile_key)

        for i, mapping in enumerate(self.taskfile_mappings):
            logger.debug(f"[{i + 1}/{len(self.taskfile_mappings)}] {mapping[1]}")
            taskfile_key = mapping[1]
            if self.load_all_taskfiles and taskfile_key in covered_taskfiles:
                continue
            tree_objects = self._recursive_get_calls(taskfile_key)
            self.trees.append(tree_objects)
        return self.trees, additional_objects

    def _recursive_get_calls(
        self,
        key: str,
        caller: CallObject | None = None,
        handover: dict[str, Any] | None = None,
        index: int = 0,
        history: list[str] | None = None,
    ) -> ObjectList:
        if history is None:
            history = []
        if handover is None:
            handover = {}
        obj_list = ObjectList()
        obj = self.get_object(key)
        if obj is None:
            return obj_list
        if key in history:
            return obj_list
        spec_obj = obj.spec if isinstance(obj, CallObject) else obj
        _history = []
        if history:
            _history = [h for h in history]
        call_obj = call_obj_from_spec(
            spec=spec_obj,
            caller=caller,
            index=index,
        )
        if call_obj is not None:
            obj_list.add(call_obj, update_dict=False)
            _history.append(key)
        children_keys, from_ram, handover = self._get_children_keys(obj, handover_from_upper_node=handover)
        for i, c_key in enumerate(children_keys):
            loop_found = False
            loop_obj = None
            if c_key in _history:
                loop_found = True
                loop_obj = self.get_object(c_key)
                if isinstance(loop_obj, CallObject):
                    loop_obj = loop_obj.spec
            child_objects = self._recursive_get_calls(
                c_key,
                call_obj,
                handover,
                i,
                _history,
            )
            if isinstance(call_obj, TaskCall):
                taskcall = call_obj
                task_spec = cast(Task, taskcall.spec)
                if len(child_objects.items) > 0:
                    c_obj = cast(CallObject, child_objects.items[0])
                    if task_spec.executable_type == ExecutableType.MODULE_TYPE:
                        mod_spec = cast(Module, c_obj.spec)
                        taskcall.module = mod_spec
                        if c_key in from_ram:
                            req_info = from_ram[c_key]
                            task_spec.possible_candidates = [(mod_spec.fqcn, req_info)]
                        else:
                            task_spec.resolved_name = mod_spec.fqcn
                        task_spec.module_info = {
                            "collection": mod_spec.collection,
                            "short_name": mod_spec.name,
                            "fqcn": mod_spec.fqcn,
                            "key": mod_spec.key,
                        }
                    elif task_spec.executable_type == ExecutableType.ROLE_TYPE:
                        role_spec = cast(Role, c_obj.spec)
                        if c_key in from_ram:
                            req_info = from_ram[c_key]
                            task_spec.possible_candidates = [(role_spec.fqcn, req_info)]
                        else:
                            task_spec.resolved_name = role_spec.fqcn
                        task_spec.include_info = {
                            "type": "role",
                            "fqcn": role_spec.fqcn,
                            "path": role_spec.defined_in,
                            "key": role_spec.key,
                        }
                    elif task_spec.executable_type == ExecutableType.TASKFILE_TYPE:
                        tf_spec = cast(TaskFile, c_obj.spec)
                        if c_key in from_ram:
                            req_info = from_ram[c_key]
                            task_spec.possible_candidates = [(tf_spec.key, req_info)]
                        else:
                            task_spec.resolved_name = tf_spec.key
                        task_spec.include_info = {
                            "type": "taskfile",
                            "path": tf_spec.defined_in,
                            "key": tf_spec.key,
                        }
                elif loop_found and loop_obj:
                    loop_spec = loop_obj.spec if isinstance(loop_obj, CallObject) else loop_obj
                    if task_spec.executable_type == ExecutableType.ROLE_TYPE:
                        task_spec.include_info = {
                            "type": "role",
                            "path": getattr(loop_spec, "defined_in", ""),
                            "key": getattr(loop_spec, "key", ""),
                        }
                    elif task_spec.executable_type == ExecutableType.TASKFILE_TYPE:
                        task_spec.include_info = {
                            "type": "taskfile",
                            "path": getattr(loop_spec, "defined_in", ""),
                            "key": getattr(loop_spec, "key", ""),
                        }
            elif isinstance(call_obj, PlayCall):
                playcall = call_obj
                if len(child_objects.items) > 0 and "roles_info" in handover:
                    first_child = child_objects.items[0]
                    if isinstance(first_child, RoleCall):
                        role_spec = cast(Role, first_child.spec)
                        play_spec = playcall.spec
                        if isinstance(play_spec, Play):
                            for rip in play_spec.roles:
                                if not isinstance(rip, RoleInPlay):
                                    continue
                                resolved_key = handover["roles_info"].get(rip.key, "")
                                if resolved_key and resolved_key == role_spec.key:
                                    rip.role_info = {
                                        "fqcn": role_spec.fqcn,
                                        "path": role_spec.defined_in,
                                        "key": role_spec.key,
                                    }
            for child_obj in child_objects.items:
                obj_list.add(child_obj)
        return obj_list

    def _recursive_make_graph(
        self,
        key: str,
        graph: list[list[str | None]],
        _objects: ObjectList,
        caller: CallObject | None = None,
    ) -> list[list[str | None]]:
        current_graph = [g for g in graph]
        # if this key is already in the graph src, no need to trace children
        key_in_graph_src = [g for g in current_graph if g[0] == key]
        if len(key_in_graph_src) > 0:
            return current_graph
        # otherwise, trace children
        obj = self.get_object(key)
        if obj is None:
            return current_graph
        spec_obj = obj.spec if isinstance(obj, CallObject) else obj
        call_obj = call_obj_from_spec(
            spec=spec_obj,
            caller=caller,
        )
        if call_obj is not None:
            caller_key = None if caller is None else caller.key
            my_key = call_obj.key
            current_graph.append([caller_key, my_key])
            _objects.add(call_obj, update_dict=False)
        children_keys, _, _ = self._get_children_keys(obj)
        for c_key in children_keys:
            updated_graph = self._recursive_make_graph(
                c_key,
                current_graph,
                _objects,
                call_obj,
            )
            current_graph = updated_graph
        return current_graph

    # get definition object from root/ext definitions
    def get_object(self, obj_key: str, search_ram: bool = False) -> Object | CallObject | None:
        obj_type = detect_type(obj_key)
        if obj_type == "":
            raise ValueError(f'failed to detect object type from key "{obj_key}"')
        type_key = obj_type_dict[obj_type]
        root_definitions = self.root_definitions.get(type_key, ObjectList())
        obj = root_definitions.find_by_key(obj_key)
        if obj is not None:
            return obj
        ext_definitions = self.ext_definitions.get(type_key, ObjectList())
        obj = ext_definitions.find_by_key(obj_key)
        if obj is not None:
            return obj

        if search_ram and self.ram_client:
            matched_obj = self.ram_client.get_object_by_key(obj_key)
            if matched_obj is not None:
                obj = matched_obj.get("object", None)
            if obj is not None:
                return cast(Object | CallObject, obj)

        return None

    def add_builtin_modules(self) -> None:
        builtin_module_dict = load_builtin_modules()
        builtin_modules = list(builtin_module_dict.values())
        obj_list = ObjectList(items=[cast(Object | CallObject, m) for m in builtin_modules])
        self.ext_definitions["modules"].merge(obj_list)

    def _get_children_keys(
        self,
        obj: Object | CallObject,
        handover_from_upper_node: dict[str, Any] | None = None,
    ) -> tuple[list[str], dict[str, str], dict[str, Any]]:
        if handover_from_upper_node is None:
            handover_from_upper_node = {}
        if isinstance(obj, CallObject):
            return self._get_children_keys(obj.spec, handover_from_upper_node)
        children_keys = []
        from_ram = {}
        handover: dict[str, Any] = {}
        if isinstance(obj, Playbook):
            children_keys = obj.plays
        elif isinstance(obj, Play):
            if obj.import_playbook != "":
                resolved_playbook_key = resolve_playbook(obj.import_playbook, self.dicts["playbooks"], obj.key)
                if resolved_playbook_key != "":
                    children_keys.append(resolved_playbook_key)
            for rip in obj.roles:
                if not isinstance(rip, RoleInPlay):
                    continue

                if rip.name in self.role_resolve_cache:
                    resolved_role_key = self.role_resolve_cache[rip.name]
                else:
                    resolved_role_key = resolve_role(
                        rip.name,
                        self.dicts["roles"],
                        obj.collection,
                        obj.collections_in_play,
                    )
                    if resolved_role_key != "":
                        self.role_resolve_cache[rip.name] = resolved_role_key

                if resolved_role_key == "" and self.ram_client is not None:
                    if rip.name in self.resolved_role_from_ram:
                        resolved_role_key, req_info = self.resolved_role_from_ram[rip.name]
                        from_ram[resolved_role_key] = req_info
                    else:
                        matched_roles = self.ram_client.search_role(rip.name)
                        if len(matched_roles) > 0:
                            resolved_role_key = matched_roles[0]["object"].key
                            self.ext_definitions["roles"].add(matched_roles[0]["object"])
                            for offspr_obj in matched_roles[0].get("offspring_objects", []):
                                type_str = offspr_obj["type"] + "s"
                                self.ext_definitions[type_str].add(offspr_obj["object"])
                            if matched_roles[0]["object"].key not in self.extra_requirement_obj_set:
                                self.extra_requirements.append(
                                    {
                                        "type": "role",
                                        "name": matched_roles[0]["object"].fqcn,
                                        "defined_in": matched_roles[0]["defined_in"],
                                        "used_in": obj.defined_in,
                                    }
                                )
                                self.extra_requirement_obj_set.add(matched_roles[0]["object"].key)
                            for offspr_obj in matched_roles[0].get("offspring_objects", []):
                                if hasattr(offspr_obj["object"], "builtin") and offspr_obj["object"].builtin:
                                    continue
                                if offspr_obj["object"].key not in self.extra_requirement_obj_set:
                                    self.extra_requirements.append(
                                        {
                                            "type": offspr_obj["type"],
                                            "name": offspr_obj["name"],
                                            "defined_in": offspr_obj["defined_in"],
                                            "used_in": offspr_obj["used_in"],
                                        }
                                    )
                                    self.extra_requirement_obj_set.add(offspr_obj["object"].key)
                            self.resolved_role_from_ram[rip.name] = (resolved_role_key, matched_roles[0]["defined_in"])
                            from_ram[resolved_role_key] = matched_roles[0]["defined_in"]

                if resolved_role_key != "":
                    children_keys.append(resolved_role_key)
                    if "roles_info" not in handover:
                        handover["roles_info"] = {}
                    handover["roles_info"][rip.key] = resolved_role_key
            children_keys.extend(obj.pre_tasks)
            children_keys.extend(obj.tasks)
            children_keys.extend(obj.post_tasks)
            children_keys.extend(obj.handlers)
        elif isinstance(obj, Role):
            target_taskfiles = ["main.yml", "main.yaml"]
            if isinstance(handover_from_upper_node, dict) and "tasks_from" in handover_from_upper_node:
                tasks_from = handover_from_upper_node.get("tasks_from")
                if tasks_from:
                    target_taskfiles = [tasks_from]
            target_taskfile_key = [
                tf
                for tf in obj.taskfiles
                if tf.split(key_delimiter)[-1].split("/")[-1] in target_taskfiles and "/handlers/" not in tf
            ]
            children_keys.extend(target_taskfile_key)
        elif isinstance(obj, TaskFile):
            children_keys = obj.tasks
        elif isinstance(obj, Task):
            executable_type = obj.executable_type
            resolved_key = ""
            if obj.executable == "":
                return [], {}, {}
            target_name = obj.executable
            if executable_type == ExecutableType.MODULE_TYPE:
                if target_name in self.module_resolve_cache:
                    resolved_key = self.module_resolve_cache[target_name]
                else:
                    resolved_key = resolve_module(target_name, self.dicts["modules"], self.module_redirects)
                    if resolved_key != "":
                        self.module_resolve_cache[target_name] = resolved_key
                if resolved_key == "" and self.ram_client is not None:
                    if target_name in self.resolved_module_from_ram:
                        resolved_key, req_info = self.resolved_module_from_ram[target_name]
                        from_ram[resolved_key] = req_info
                    else:
                        matched_modules = self.ram_client.search_module(target_name)
                        if len(matched_modules) > 0:
                            resolved_key = matched_modules[0]["object"].key
                            self.ext_definitions["modules"].add(matched_modules[0]["object"])
                            if (
                                matched_modules[0]["object"].key not in self.extra_requirement_obj_set
                                and not matched_modules[0]["object"].builtin
                            ):
                                self.extra_requirements.append(
                                    {
                                        "type": "module",
                                        "name": matched_modules[0]["object"].fqcn,
                                        "defined_in": matched_modules[0]["defined_in"],
                                        "used_in": obj.defined_in,
                                    }
                                )
                                self.extra_requirement_obj_set.add(matched_modules[0]["object"].key)
                            self.resolved_module_from_ram[target_name] = (
                                resolved_key,
                                matched_modules[0]["defined_in"],
                            )
                            from_ram[resolved_key] = matched_modules[0]["defined_in"]
                if resolved_key == "":
                    if target_name not in self.resolve_failures["module"]:
                        self.resolve_failures["module"][target_name] = 0
                    self.resolve_failures["module"][target_name] += 1
            elif executable_type == ExecutableType.ROLE_TYPE:
                tasks_from = None
                if isinstance(obj.module_options, dict):
                    tasks_from = obj.module_options.get("tasks_from", None)
                if tasks_from:
                    handover["tasks_from"] = tasks_from

                if target_name in self.role_resolve_cache:
                    resolved_key = self.role_resolve_cache[target_name]
                else:
                    resolved_key = resolve_role(
                        target_name,
                        self.dicts["roles"],
                        obj.collection,
                        obj.collections_in_play,
                    )
                    if resolved_key != "":
                        self.role_resolve_cache[target_name] = resolved_key
                if resolved_key == "" and self.ram_client is not None:
                    if target_name in self.resolved_role_from_ram:
                        resolved_key, req_info = self.resolved_role_from_ram[target_name]
                        from_ram[resolved_key] = req_info
                    else:
                        matched_roles = self.ram_client.search_role(target_name)
                        if len(matched_roles) > 0:
                            resolved_key = matched_roles[0]["object"].key
                            self.ext_definitions["roles"].add(matched_roles[0]["object"])
                            if matched_roles[0]["object"].key not in self.extra_requirement_obj_set:
                                self.extra_requirements.append(
                                    {
                                        "type": "role",
                                        "name": matched_roles[0]["object"].fqcn,
                                        "defined_in": matched_roles[0]["defined_in"],
                                        "used_in": obj.defined_in,
                                    }
                                )
                                self.extra_requirement_obj_set.add(matched_roles[0]["object"].key)
                            for offspr_obj in matched_roles[0].get("offspring_objects", []):
                                if hasattr(offspr_obj["object"], "builtin") and offspr_obj["object"].builtin:
                                    continue
                                if offspr_obj["object"].key not in self.extra_requirement_obj_set:
                                    self.extra_requirements.append(
                                        {
                                            "type": offspr_obj["type"],
                                            "name": offspr_obj["name"],
                                            "defined_in": offspr_obj["defined_in"],
                                            "used_in": offspr_obj["used_in"],
                                        }
                                    )
                                    self.extra_requirement_obj_set.add(offspr_obj["object"].key)
                            self.resolved_role_from_ram[target_name] = (resolved_key, matched_roles[0]["defined_in"])
                            from_ram[resolved_key] = matched_roles[0]["defined_in"]
                if resolved_key == "":
                    if target_name not in self.resolve_failures["role"]:
                        self.resolve_failures["role"][target_name] = 0
                    self.resolve_failures["role"][target_name] += 1
            elif executable_type == ExecutableType.TASKFILE_TYPE:
                if is_templated(target_name):
                    target_name = render_template(target_name)
                if target_name in self.taskfile_resolve_cache:
                    resolved_key = self.taskfile_resolve_cache[target_name]
                else:
                    resolved_key = resolve_taskfile(
                        target_name,
                        self.dicts["taskfiles"],
                        obj.key,
                    )
                    if resolved_key != "":
                        self.taskfile_resolve_cache[target_name] = resolved_key
                if resolved_key == "" and self.ram_client is not None:
                    if obj.executable in self.resolved_role_from_ram:
                        resolved_key, req_info = self.resolved_role_from_ram[target_name]
                        from_ram[resolved_key] = req_info
                    else:
                        matched_taskfiles = self.ram_client.search_taskfile(
                            target_name, from_path=obj.defined_in, from_key=obj.key
                        )
                        if len(matched_taskfiles) > 0:
                            resolved_key = matched_taskfiles[0]["object"].key
                            self.ext_definitions["taskfiles"].add(matched_taskfiles[0]["object"], update_dict=False)
                            if matched_taskfiles[0]["object"].key not in self.extra_requirement_obj_set:
                                self.extra_requirements.append(
                                    {
                                        "type": "taskfile",
                                        "name": matched_taskfiles[0]["object"].key,
                                        "defined_in": matched_taskfiles[0]["defined_in"],
                                        "used_in": obj.defined_in,
                                    }
                                )
                                self.extra_requirement_obj_set.add(matched_taskfiles[0]["object"].key)
                            for offspr_obj in matched_taskfiles[0].get("offspring_objects", []):
                                if hasattr(offspr_obj["object"], "builtin") and offspr_obj["object"].builtin:
                                    continue
                                if offspr_obj["object"].key not in self.extra_requirement_obj_set:
                                    self.extra_requirements.append(
                                        {
                                            "type": offspr_obj["type"],
                                            "name": offspr_obj["name"],
                                            "defined_in": offspr_obj["defined_in"],
                                            "used_in": offspr_obj["used_in"],
                                        }
                                    )
                                    self.extra_requirement_obj_set.add(offspr_obj["object"].key)
                            self.resolved_taskfile_from_ram[target_name] = (
                                resolved_key,
                                matched_taskfiles[0]["defined_in"],
                            )
                            from_ram[resolved_key] = matched_taskfiles[0]["defined_in"]
                if resolved_key == "":
                    if target_name not in self.resolve_failures["taskfile"]:
                        self.resolve_failures["taskfile"][target_name] = 0
                    self.resolve_failures["taskfile"][target_name] += 1

            if resolved_key != "":
                children_keys.append(resolved_key)
        return children_keys, from_ram, handover

    def node_objects(self, tree: TreeNode) -> ObjectList:
        loaded: dict[str, Object | CallObject] = {}
        obj_list = ObjectList()
        for k in tree.to_keys():
            if k in loaded:
                obj_list.add(loaded[k])
                continue
            obj = self.get_object(k)
            if obj is None:
                logger.warning(f"object not found for the key {k}")
                continue
            obj_list.add(obj)
            loaded[k] = obj
        return obj_list


def is_templated(txt: str) -> bool:
    return "{{" in txt


# TODO: need to use variable manager
def render_template(txt: str, variable_manager: Any = None) -> str:
    regex = r'[\'"]([^\'"]+\.ya?ml)[\'"]'
    matched = re.search(regex, txt)
    if matched:
        return matched.group(1)
    if "{{ ansible_facts.os_family }}.yml" in txt:
        return "Debian.yml"
    if "{{ gcloud_install_type }}/main.yml" in txt:
        return "package/main.yml"
    if "{{ ansible_os_family | lower }}.yml" in txt:
        return "debian.yml"
    return txt


def dump_node_objects(obj_list: ObjectList, path: str = "") -> None:
    if path == "":
        lines = obj_list.dump()
        for line in lines:
            obj_dict = json.loads(line)
            print(json.dumps(obj_dict, indent=2))
    else:
        obj_list.dump(fpath=path)


def key_to_file_name(prefix: str, key: str) -> str:
    trans_table = str.maketrans({" ": "___", "/": "---", ".": "_dot_"})
    return prefix + "___" + key.translate(trans_table) + ".json"
