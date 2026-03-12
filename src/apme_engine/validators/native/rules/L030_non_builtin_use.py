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
class NonBuiltinUseRule(Rule):
    rule_id: str = "L030"
    description: str = "Non-builtin module is used"
    enabled: bool = True
    name: str = "NonBuiltinUse"
    version: str = "v0.0.1"
    severity: str = Severity.VERY_LOW
    tags: tuple[str, ...] = (Tag.DEPENDENCY,)

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
        resolved_name = getattr(task, "resolved_name", "")
        verdict = bool(
            action_type == ActionType.MODULE_TYPE
            and resolved_action
            and not resolved_action.startswith("ansible.builtin.")
        )

        detail = {
            "fqcn": resolved_name,
        }

        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())
