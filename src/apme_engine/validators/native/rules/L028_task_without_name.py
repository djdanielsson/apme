from dataclasses import dataclass

from apme_engine.engine.models import (
    AnsibleRunContext,
    Rule,
    RuleResult,
    RunTargetType,
    Severity,
)
from apme_engine.engine.models import (
    RuleTag as Tag,
)


@dataclass
class TaskWithoutNameRule(Rule):
    rule_id: str = "L028"
    description: str = "A task without name is found"
    enabled: bool = True
    name: str = "TaskWithoutName"
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

        verdict = not getattr(task.spec, "name", None)

        return RuleResult(verdict=verdict, file=task.file_info(), rule=self.get_metadata())
