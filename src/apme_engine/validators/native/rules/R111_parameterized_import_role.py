from dataclasses import dataclass

from apme_engine.engine.models import (
    AnsibleRunContext,
    Rule,
    RuleResult,
    RunTargetType,
    Severity,
    TaskCall,
)
from apme_engine.engine.models import (
    ExecutableType as ActionType,
)
from apme_engine.engine.models import RuleTag as Tag


@dataclass
class ParameterizedImportRoleRule(Rule):
    rule_id: str = "R111"
    description: str = "Import/include a parameterized name of role"
    enabled: bool = True
    name: str = "ParameterizedImportRole"
    version: str = "v0.0.1"
    severity: str = Severity.HIGH
    tags: tuple[str, ...] = (Tag.DEPENDENCY,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        task = ctx.current
        if task is None or not isinstance(task, TaskCall):
            return None

        role_ref_arg = task.args.get("name")
        verdict = bool(
            task.action_type == ActionType.ROLE_TYPE and role_ref_arg is not None and role_ref_arg.is_mutable
        )
        role_ref = role_ref_arg.raw if role_ref_arg else None
        detail = {
            "role": role_ref,
        }

        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())
