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
class FileChangeRule(Rule):
    rule_id: str = "R114"
    description: str = "Parameterized file change is found"
    enabled: bool = True
    name: str = "ConfigChange"
    version: str = "v0.0.1"
    severity: str = Severity.LOW
    tags: tuple[str, ...] = (Tag.SYSTEM,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        task = ctx.current
        if task is None:
            return None

        ac = AnnotationCondition().risk_type(RiskType.FILE_CHANGE).attr("is_mutable_path", True)
        ac2 = AnnotationCondition().risk_type(RiskType.FILE_CHANGE).attr("is_mutable_src", True)
        verdict = False
        detail = {}
        if task.has_annotation_by_condition(ac):
            verdict = True
            anno = task.get_annotation_by_condition(ac)
            if anno:
                path = getattr(anno, "path", None)
                if path is not None:
                    detail["path"] = path.value

        if task.has_annotation_by_condition(ac2):
            verdict = True
            anno = task.get_annotation_by_condition(ac2)
            if anno:
                src = getattr(anno, "src", None)
                if src is not None:
                    detail["src"] = src.value

        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())
