from dataclasses import dataclass

from apme_engine.engine.models import (
    AnsibleRunContext,
    ArgumentsType,
    Rule,
    RuleResult,
    RunTargetType,
    Severity,
    TaskCall,
    VariableType,
)
from apme_engine.engine.models import RuleTag as Tag


def is_loop_var(value: str, task: TaskCall) -> bool:
    # `item` or alternative loop variable (if any) should not be replaced to avoid breaking loop
    skip_variables: list[str] = []
    loop = getattr(task.spec, "loop", None)
    if loop and isinstance(loop, dict):
        skip_variables.extend(list(loop.keys()))

    _v = value.replace(" ", "")

    for var in skip_variables:
        for _prefix in ["}}", "|", "."]:
            pattern = "{{" + var + _prefix
            if pattern in _v:
                return True
    return False


@dataclass
class VariableValidationRule(Rule):
    rule_id: str = "P004"
    description: str = "Validate variables and set annotations"
    enabled: bool = True
    name: str = "VariableValidation"
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

        undefined_variables: list[str] = []
        unknown_name_vars: list[str] = []
        unnecessary_loop: list[dict[str, str]] = []
        task_arg_keys = []
        if task.args.type == ArgumentsType.DICT:
            task_arg_keys = list(task.args.raw.keys())

        registered_vars = []
        for v_name in task.variable_set:
            v = task.variable_set[v_name]
            if v and v[-1].type == VariableType.RegisteredVars:
                registered_vars.append(v_name)

        for v_name in task.variable_use:
            first_v_name = v_name.split(".")[0]
            # skip registered vars
            if first_v_name in registered_vars:
                continue

            v = task.variable_use[v_name]
            if v and v[-1].type == VariableType.Unknown:
                if v_name not in undefined_variables:
                    undefined_variables.append(v_name)
                existing_names = [x["name"] for x in unnecessary_loop if isinstance(x, dict) and "name" in x]
                if v_name not in unknown_name_vars and v_name not in task_arg_keys:
                    unknown_name_vars.append(v_name)
                if v_name not in existing_names:
                    v_str = "{{ " + v_name + " }}"
                    if not is_loop_var(v_str, task):
                        unnecessary_loop.append({"name": v_name, "suggested": v_name.replace("item.", "")})

        task.set_annotation("variable.undefined_vars", undefined_variables, rule_id=self.rule_id)
        task.set_annotation("variable.unknown_name_vars", unknown_name_vars, rule_id=self.rule_id)
        task.set_annotation("variable.unnecessary_loop_vars", unnecessary_loop, rule_id=self.rule_id)

        return None
