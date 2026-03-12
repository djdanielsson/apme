from dataclasses import dataclass
from typing import Any

from apme_engine.engine.models import (
    AnsibleRunContext,
    Rule,
    RuleResult,
    RunTargetType,
    Severity,
)
from apme_engine.engine.models import (
    ExecutableType as ActionType,
)
from apme_engine.engine.models import (
    RuleTag as Tag,
)


@dataclass
class UnnecessarySetFactRule(Rule):
    rule_id: str = "L035"
    description: str = "set_fact is used without random filter"
    enabled: bool = True
    name: str = "UnnecessarySetFact"
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

        args_obj = getattr(task, "args", None)
        args = getattr(args_obj, "raw", None) if args_obj is not None else None
        is_impure = False
        detail: dict[str, Any] = {}
        if isinstance(args, str):
            is_impure = "random" in args
            detail["impure_args"] = args
        elif isinstance(args, dict):
            for v in args.values():
                if isinstance(v, str) and "random" in v:
                    is_impure = True
                    current = detail.get("impure_args", [])
                    if not isinstance(current, list):
                        current = []
                    current = list(current)
                    current.append(v)
                    detail["impure_args"] = current

        action_type = getattr(task, "action_type", "")
        resolved_action = getattr(task, "resolved_action", "")
        verdict = bool(
            action_type == ActionType.MODULE_TYPE
            and resolved_action
            and resolved_action == "ansible.builtin.set_fact"
            and is_impure
        )

        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())
