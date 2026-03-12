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
class UnresolvedModuleRule(Rule):
    rule_id: str = "L037"
    description: str = "Unresolved module is found"
    enabled: bool = True
    name: str = "UnresolvedModule"
    version: str = "v0.0.1"
    severity: str = Severity.LOW
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
        spec_action = getattr(task.spec, "action", None)
        resolved_action = getattr(task, "resolved_action", "")
        verdict = bool(action_type == ActionType.MODULE_TYPE and spec_action and not resolved_action)
        detail = {
            "module": spec_action or "",
        }

        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())
