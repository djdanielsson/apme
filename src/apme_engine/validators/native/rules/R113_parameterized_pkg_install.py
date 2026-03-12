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
class PkgInstallRuleResult(RuleResult):
    pass


@dataclass
class PkgInstallRule(Rule):
    rule_id: str = "R113"
    description: str = "A parameterized pkg installation is found"
    enabled: bool = True
    name: str = "PkgInstall"
    version: str = "v0.0.1"
    severity: str = Severity.MEDIUM
    tags: tuple[str, ...] = (Tag.PACKAGE,)
    result_type: type = PkgInstallRuleResult

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        task = ctx.current
        if task is None:
            return None

        ac = AnnotationCondition().risk_type(RiskType.PACKAGE_INSTALL).attr("is_mutable_pkg", True)
        verdict = task.has_annotation_by_condition(ac)

        detail = {}
        if verdict:
            anno = task.get_annotation_by_condition(ac)
            if anno:
                detail["pkg"] = getattr(anno, "pkg", None)

        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())
