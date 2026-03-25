"""Native rule L078: detect dot notation for dict access in Jinja; prefer bracket notation."""

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

_DOT_ACCESS = re.compile(
    r"\bitem\.\w+"
    r"|\bresult\.\w+"
    r"|\boutput\.\w+"
    r"|\bhostvars\.\w+"
    r"|\bgroups\.\w+"
)


@dataclass
class DotNotationRule(Rule):
    """Rule for detecting dot notation in Jinja dict access.

    Attributes:
        rule_id: Rule identifier.
        description: Rule description.
        enabled: Whether the rule is enabled.
        name: Rule name.
        version: Rule version.
        severity: Severity level.
        tags: Rule tags.
    """

    rule_id: str = "L078"
    description: str = "Use bracket notation for dict key access in Jinja"
    enabled: bool = True
    name: str = "DotNotation"
    version: str = "v0.0.1"
    severity: str = Severity.VERY_LOW
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
        """Check for dot notation dict access in Jinja and return result.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with found_patterns detail, or None.
        """
        task = ctx.current
        if task is None:
            return None
        yaml_lines = getattr(task.spec, "yaml_lines", "") or ""
        found = sorted(set(_DOT_ACCESS.findall(yaml_lines)))
        verdict = len(found) > 0
        detail: dict[str, object] = {}
        if found:
            detail["found_patterns"] = found
            detail["message"] = "use bracket notation (e.g. item['key']) instead of dot notation"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", task.file_info()),
            rule=self.get_metadata(),
        )
