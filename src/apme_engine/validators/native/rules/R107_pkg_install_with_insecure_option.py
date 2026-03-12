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
class InsecurePkgInstallRule(Rule):
    rule_id: str = "R107"
    description: str = "A package installation with insecure option is found"
    enabled: bool = True
    name: str = "InsecurePkgInstall"
    version: str = "v0.0.1"
    severity: str = Severity.HIGH
    tags: tuple[str, ...] = (Tag.PACKAGE,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        task = ctx.current
        if task is None:
            return None

        ac = AnnotationCondition().risk_type(RiskType.PACKAGE_INSTALL).attr("disable_validate_certs", True)
        ac2 = AnnotationCondition().risk_type(RiskType.PACKAGE_INSTALL).attr("allow_downgrade", True)
        verdict = task.has_annotation_by_condition(ac) or task.has_annotation_by_condition(ac2)

        detail = {}
        if verdict:
            anno = task.get_annotation_by_condition(ac)
            if anno:
                detail["pkg"] = getattr(anno, "pkg", None)
            anno2 = task.get_annotation_by_condition(ac2)
            if anno2:
                detail["pkg"] = getattr(anno2, "pkg", None)

        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())
