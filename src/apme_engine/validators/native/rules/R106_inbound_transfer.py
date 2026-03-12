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
class InboundRuleResult(RuleResult):
    pass


@dataclass
class InboundTransferRule(Rule):
    rule_id: str = "R106"
    description: str = "A inbound network transfer from a parameterized source is found"
    enabled: bool = True
    name: str = "InboundTransfer"
    version: str = "v0.0.1"
    severity: str = Severity.MEDIUM
    tags: tuple[str, ...] = (Tag.NETWORK,)
    result_type: type = InboundRuleResult

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        task = ctx.current
        if task is None:
            return None

        ac = AnnotationCondition().risk_type(RiskType.INBOUND).attr("is_mutable_src", True)
        verdict = task.has_annotation_by_condition(ac)

        detail = {}
        if verdict:
            anno = task.get_annotation_by_condition(ac)
            if anno:
                src = getattr(anno, "src", None)
                dest = getattr(anno, "dest", None)
                if src is not None:
                    detail["from"] = src.value
                if dest is not None:
                    detail["to"] = dest.value

        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())
