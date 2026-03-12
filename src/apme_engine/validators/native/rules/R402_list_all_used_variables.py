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
class ListAllUsedVariablesRule(Rule):
    rule_id: str = "R402"
    description: str = "Listing all used variables"
    enabled: bool = True
    name: str = "ListAllUsedVariables"
    version: str = "v0.0.1"
    severity: str = Severity.NONE
    tags: tuple[str, ...] = (Tag.VARIABLE,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        task = ctx.current
        if task is None:
            return None

        verdict = False
        detail: dict[str, object] = {}
        if ctx.is_end(task) and isinstance(task, TaskCall):
            verdict = True
            detail["metadata"] = ctx.info
            detail["variables"] = list(task.variable_use.keys())

        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())
