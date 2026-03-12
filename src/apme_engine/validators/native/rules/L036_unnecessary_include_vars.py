from dataclasses import dataclass

from apme_engine.engine.models import (
    AnsibleRunContext,
    Rule,
    RuleResult,
    RunTargetType,
    Severity,
)
from apme_engine.engine.models import (
    ExecutableType as ActionType,
)
from apme_engine.engine.models import (
    RuleTag as Tag,
)


@dataclass
class UnnecessaryIncludeVarsRule(Rule):
    rule_id: str = "L036"
    description: str = "include_vars is used without any condition"
    enabled: bool = True
    name: str = "UnnecessaryIncludeVars"
    version: str = "v0.0.1"
    severity: str = Severity.VERY_LOW
    tags: tuple[str, ...] = (Tag.VARIABLE,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        task = ctx.current
        if task is None:
            return None

        action_type = getattr(task, "action_type", "")
        resolved_action = getattr(task, "resolved_action", "")
        spec_tags = getattr(task.spec, "tags", None)
        spec_when = getattr(task.spec, "when", None)
        verdict = bool(
            action_type == ActionType.MODULE_TYPE
            and resolved_action
            and resolved_action == "ansible.builtin.include_vars"
            and not spec_tags
            and not spec_when
        )

        return RuleResult(verdict=verdict, file=task.file_info(), rule=self.get_metadata())
