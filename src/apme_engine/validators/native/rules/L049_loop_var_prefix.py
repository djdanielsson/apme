from dataclasses import dataclass

from apme_engine.engine.models import (
    AnsibleRunContext,
    Rule,
    RuleResult,
    RunTargetType,
    Severity,
)
from apme_engine.engine.models import (
    RuleTag as Tag,
)

DEFAULT_LOOP_VAR = "item"
LOOP_VAR_PREFIX = "item_"


@dataclass
class LoopVarPrefixRule(Rule):
    rule_id: str = "L049"
    description: str = "Loop variable should use a prefix (e.g. item_) to avoid shadowing"
    enabled: bool = True
    name: str = "LoopVarPrefix"
    version: str = "v0.0.1"
    severity: str = Severity.VERY_LOW
    tags: tuple[str, ...] = (Tag.VARIABLE,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        task = ctx.current
        if task is None:
            return None
        options = getattr(task.spec, "options", None) or {}
        loop_control = options.get("loop_control") if isinstance(options.get("loop_control"), dict) else None
        loop_var = loop_control.get("loop_var") if loop_control else None
        if not loop_var or loop_var == DEFAULT_LOOP_VAR:
            has_loop = bool(getattr(task.spec, "loop", None)) or "loop" in options
            verdict = has_loop
        else:
            verdict = not (isinstance(loop_var, str) and loop_var.startswith(LOOP_VAR_PREFIX))
        detail = {}
        if verdict:
            detail["loop_var"] = loop_var or DEFAULT_LOOP_VAR
            detail["message"] = "use a loop variable with prefix (e.g. item_) to avoid shadowing"
        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())
