from dataclasses import dataclass

from apme_engine.engine.models import (
    AnnotationCondition,
    AnsibleRunContext,
    DefaultRiskType,
    Rule,
    RuleResult,
    RunTargetType,
    Severity,
    TaskCall,
)
from apme_engine.engine.models import RuleTag as Tag


@dataclass
class ListAllInboundSrcRule(Rule):
    rule_id: str = "R401"
    description: str = "List all inbound sources"
    enabled: bool = True
    name: str = "ListAllInboundSrcRule"
    version: str = "v0.0.1"
    severity: str = Severity.VERY_LOW
    tags: tuple[str, ...] = (Tag.DEBUG,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        task = ctx.current
        if task is None:
            return None

        ac = AnnotationCondition().risk_type(DefaultRiskType.INBOUND)
        verdict = False
        detail: dict[str, object] = {}
        src_list: list[str] = []
        if ctx.is_end(task):
            tasks = ctx.search(ac)
            for t in tasks:
                if isinstance(t, TaskCall):
                    anno = t.get_annotation_by_condition(ac)
                    if anno is not None and hasattr(anno, "src") and anno.src is not None:
                        src_list.append(anno.src.value)
            if len(src_list) > 0:
                verdict = True
                detail["inbound_src"] = src_list

        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())
