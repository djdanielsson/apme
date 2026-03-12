from dataclasses import dataclass

from apme_engine.engine.models import (
    AnsibleRunContext,
    Rule,
    RuleResult,
    RunTargetType,
    Severity,
    TaskCall,
)
from apme_engine.engine.models import RuleTag as Tag


@dataclass
class PrivilegeEscalationRule(Rule):
    rule_id: str = "R108"
    description: str = "Privilege escalation is found"
    enabled: bool = True
    name: str = "PrivilegeEscalation"
    version: str = "v0.0.1"
    severity: str = Severity.HIGH
    tags: tuple[str, ...] = (Tag.SYSTEM,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        task = ctx.current
        if task is None or not isinstance(task, TaskCall):
            return None

        verdict = bool(task.become and task.become.enabled)
        detail = {}
        if verdict:
            detail = task.become.__dict__

        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())
