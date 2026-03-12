from dataclasses import dataclass
from typing import Any

from apme_engine.engine.models import (
    AnsibleRunContext,
    Rule,
    RuleResult,
    RunTargetType,
    Severity,
    TaskCall,
)


@dataclass
class SampleRule(Rule):
    rule_id: str = "Sample101"
    description: str = "echo task block"
    enabled: bool = False
    name: str = "EchoTaskContent"
    version: str = "v0.0.1"
    severity: str = Severity.NONE
    tags: tuple[str, ...] = ("sample",)

    def match(self, ctx: AnsibleRunContext) -> bool:
        # specify targets to be checked
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        if ctx.current is None:
            return None
        task = ctx.current
        if not isinstance(task, TaskCall) or task.content is None:
            return None

        verdict = True
        detail: dict[str, Any] = {}
        task_block = task.content.yaml()
        detail["task_block"] = task_block

        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())
