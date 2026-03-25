"""Native rule L091: detect bare variables in when conditions missing | bool filter."""

import re
from dataclasses import dataclass
from typing import cast

from apme_engine.engine.models import (
    AnsibleRunContext,
    Rule,
    RuleResult,
    RunTargetType,
    Severity,
    YAMLDict,
)
from apme_engine.engine.models import (
    RuleTag as Tag,
)

_BARE_VAR_WHEN = re.compile(
    r"when:\s*(\w+)\s*$"
    r"|when:\s*not\s+(\w+)\s*$",
    re.MULTILINE,
)


@dataclass
class BoolFilterRule(Rule):
    """Rule for using | bool filter on bare variables in when conditions.

    Attributes:
        rule_id: Rule identifier.
        description: Rule description.
        enabled: Whether the rule is enabled.
        name: Rule name.
        version: Rule version.
        severity: Severity level.
        tags: Rule tags.
    """

    rule_id: str = "L091"
    description: str = "Use | bool for bare variables in when conditions"
    enabled: bool = True
    name: str = "BoolFilter"
    version: str = "v0.0.1"
    severity: str = Severity.LOW
    tags: tuple[str, ...] = (Tag.CODING,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        """Check if context has a task target.

        Args:
            ctx: AnsibleRunContext to evaluate.

        Returns:
            True if current target is a task.
        """
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        """Check for bare variables in when without | bool.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with found_bare detail, or None.
        """
        task = ctx.current
        if task is None:
            return None
        yaml_lines = getattr(task.spec, "yaml_lines", "") or ""
        matches = _BARE_VAR_WHEN.findall(yaml_lines)
        found = [m[0] or m[1] for m in matches if m[0] or m[1]]
        found = [f for f in found if f not in ("true", "false", "yes", "no")]
        verdict = len(found) > 0
        detail: dict[str, object] = {}
        if found:
            detail["bare_variables"] = found
            detail["message"] = "use | bool filter for bare variables in when conditions"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", task.file_info()),
            rule=self.get_metadata(),
        )
