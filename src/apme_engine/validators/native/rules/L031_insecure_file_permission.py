from dataclasses import dataclass

from apme_engine.engine.models import (
    AnnotationCondition,
    AnsibleRunContext,
    Rule,
    RuleResult,
    RunTargetType,
    Severity,
)
from apme_engine.engine.models import (
    DefaultRiskType as RiskType,
)
from apme_engine.engine.models import (
    RuleTag as Tag,
)


@dataclass
class FilePermissionRule(Rule):
    rule_id: str = "L031"
    description: str = "File permission is not secure."
    enabled: bool = False
    name: str = "FilePermissionRule"
    version: str = "v0.0.1"
    severity: str = Severity.MEDIUM
    tags: tuple[str, ...] = (Tag.SYSTEM,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        task = ctx.current
        if task is None:
            return None

        # define a condition for this rule here
        ac = AnnotationCondition().risk_type(RiskType.FILE_CHANGE).attr("is_insecure_permissions", True)
        verdict = task.has_annotation_by_condition(ac)

        return RuleResult(verdict=verdict, file=task.file_info(), rule=self.get_metadata())
