"""Native rule L073: detect YAML indentation that is not 2 spaces."""

from dataclasses import dataclass
from typing import cast

from apme_engine.engine.models import (
    AnsibleRunContext,
    Rule,
    RuleResult,
    RuleScope,
    RunTargetType,
    Severity,
    YAMLDict,
)
from apme_engine.engine.models import (
    RuleTag as Tag,
)

EXPECTED_INDENT = 2


@dataclass
class IndentationRule(Rule):
    """Rule for YAML indentation (2 spaces expected).

    Attributes:
        rule_id: Rule identifier.
        description: Rule description.
        enabled: Whether the rule is enabled.
        name: Rule name.
        version: Rule version.
        severity: Severity level.
        tags: Rule tags.
        scope: Structural scope.
    """

    rule_id: str = "L073"
    description: str = "YAML should use 2-space indentation"
    enabled: bool = True
    name: str = "Indentation"
    version: str = "v0.0.1"
    severity: str = Severity.VERY_LOW
    tags: tuple[str, ...] = (Tag.CODING,)
    scope: str = RuleScope.PLAYBOOK

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
        """Check for non-2-space indentation and return result.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with bad_indent_lines detail, or None.
        """
        task = ctx.current
        if task is None:
            return None
        yaml_lines = getattr(task.spec, "yaml_lines", "") or ""
        bad_lines: list[int] = []
        for i, line in enumerate(yaml_lines.splitlines(), start=1):
            stripped = line.lstrip(" ")
            if stripped == "" or stripped.startswith("#"):
                continue
            indent = len(line) - len(stripped)
            if indent > 0 and indent % EXPECTED_INDENT != 0:
                bad_lines.append(i)
        verdict = len(bad_lines) > 0
        detail: dict[str, object] = {}
        if bad_lines:
            detail["bad_indent_lines"] = bad_lines
            detail["expected_indent"] = EXPECTED_INDENT
            detail["message"] = "indentation should be a multiple of 2 spaces"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", task.file_info()),
            rule=self.get_metadata(),
        )
