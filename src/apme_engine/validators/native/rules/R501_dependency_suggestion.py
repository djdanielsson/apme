from dataclasses import dataclass

from apme_engine.engine.models import (
    AnsibleRunContext,
    Rule,
    RuleResult,
    RunTargetType,
    Severity,
    Task,
)
from apme_engine.engine.models import RuleTag as Tag


@dataclass
class DependencySuggestionRule(Rule):
    rule_id: str = "R501"
    description: str = "Suggest dependencies for unresolved modules/roles"
    enabled: bool = True
    name: str = "DependencySuggestion"
    version: str = "v0.0.1"
    severity: str = Severity.NONE
    tags: tuple[str, ...] = (Tag.DEPENDENCY,)

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
        spec = task.spec
        if isinstance(spec, Task) and spec.possible_candidates:
            verdict = True
            detail["type"] = spec.executable_type.lower()
            detail["fqcn"] = spec.possible_candidates[0][0]
            req_info = spec.possible_candidates[0][1]
            req_dict = req_info if isinstance(req_info, dict) else {}
            detail["suggestion"] = {
                "type": req_dict.get("type", ""),
                "name": req_dict.get("name", ""),
                "version": req_dict.get("version", ""),
            }

        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())
