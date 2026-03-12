from dataclasses import dataclass

from apme_engine.engine.models import (
    ActionGroupMetadata,
    AnsibleRunContext,
    ExecutableType,
    Rule,
    RuleResult,
    RunTargetType,
    Severity,
    TaskCall,
)
from apme_engine.engine.models import RuleTag as Tag


def is_set_fact(module_fqcn: str) -> bool:
    return module_fqcn == "ansible.builtin.set_fact"


def is_meta(module_fqcn: str) -> bool:
    return module_fqcn == "ansible.builtin.meta"


@dataclass
class ModuleArgumentKeyValidationRule(Rule):
    rule_id: str = "P002"
    description: str = "Validate module argument keys and set annotations"
    enabled: bool = True
    name: str = "ModuleArgumentKeyValidation"
    version: str = "v0.0.1"
    severity: str = Severity.NONE
    tags: tuple[str, ...] = (Tag.QUALITY,)
    precedence: int = 0

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        task = ctx.current
        if task is None or not isinstance(task, TaskCall):
            return None

        if (
            getattr(task.spec, "executable_type", "") == ExecutableType.MODULE_TYPE
            and task.module
            and task.module.arguments
        ):
            mo = getattr(task.spec, "module_options", {})
            module_fqcn = task.get_annotation(key="module.correct_fqcn")
            module_short = ""
            if module_fqcn:
                parts = module_fqcn.split(".")
                if len(parts) <= 2:
                    module_short = module_fqcn.split(".")[-1]
                elif len(parts) > 2:
                    module_short = ".".join(module_fqcn.split(".")[2:])
            default_args = {}
            if module_short and module_short in task.module_defaults:
                default_args = task.module_defaults[module_short]
            elif module_fqcn and module_fqcn in task.module_defaults:
                default_args = task.module_defaults[module_fqcn]
            elif ctx.ram_client:
                for group_name in task.module_defaults:
                    tmp_args = task.module_defaults[group_name]
                    found = False
                    if not group_name.startswith("group/"):
                        continue
                    groups = ctx.ram_client.search_action_group(group_name)
                    if not groups:
                        continue
                    for group_dict in groups:
                        if not group_dict:
                            continue
                        if not isinstance(group_dict, dict):
                            continue
                        group = ActionGroupMetadata.from_dict(group_dict)
                        if (
                            module_short
                            and module_short in group.group_modules
                            or module_fqcn
                            and module_fqcn in group.group_modules
                        ):
                            found = True
                            default_args = tmp_args
                            break
                    if found:
                        break

            used_keys = []
            if isinstance(mo, dict):
                used_keys = list(mo.keys())

            available_keys = []
            required_keys = []
            alias_reverse_map = {}
            available_args = None
            wrong_keys = []
            missing_required_keys = []
            if not is_set_fact(module_fqcn) and not is_meta(module_fqcn):
                if task.module:
                    for arg in task.module.arguments:
                        available_keys.extend(arg.available_keys())
                        if arg.required:
                            aliases = arg.aliases if arg.aliases else []
                            req_k = {"key": arg.name, "aliases": aliases}
                            required_keys.append(req_k)
                        if arg.aliases:
                            for al in arg.aliases:
                                alias_reverse_map[al] = arg.name
                    available_args = task.module.arguments

                wrong_keys = [key for key in used_keys if key not in available_keys]

                for k in required_keys:
                    name = k.get("key", "")
                    aliases = k.get("aliases", [])
                    if name in used_keys:
                        continue
                    if name in default_args:
                        continue
                    if aliases:
                        found = False
                        for a_k in aliases:
                            if a_k in used_keys:
                                found = True
                                break
                            if a_k in default_args:
                                found = True
                                break
                        if found:
                            continue
                    # here, the required key was not found
                    missing_required_keys.append(name)

            used_alias_and_real_keys = []
            for k in used_keys:
                if k not in alias_reverse_map:
                    continue
                real_name = alias_reverse_map[k]
                used_alias_and_real_keys.append(
                    {
                        "used_alias": k,
                        "real_key": real_name,
                    }
                )

            task.set_annotation("module.wrong_arg_keys", wrong_keys, rule_id=self.rule_id)
            task.set_annotation("module.available_arg_keys", available_keys, rule_id=self.rule_id)
            task.set_annotation("module.required_arg_keys", required_keys, rule_id=self.rule_id)
            task.set_annotation("module.missing_required_arg_keys", missing_required_keys, rule_id=self.rule_id)
            task.set_annotation("module.available_args", available_args, rule_id=self.rule_id)
            task.set_annotation("module.default_args", default_args, rule_id=self.rule_id)
            task.set_annotation("module.used_alias_and_real_keys", used_alias_and_real_keys, rule_id=self.rule_id)

        # TODO: find duplicate keys

        return None
