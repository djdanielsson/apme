"""Native rule L099: detect inconsistent YAML string quoting style."""

import re
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

_SINGLE_QUOTED_VALUE = re.compile(r":\s+'[^']*'\s*$")


@dataclass
class YamlQuotedStringsRule(Rule):
    """Rule for preferring double quotes over single quotes in YAML.

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

    rule_id: str = "L099"
    description: str = "Prefer double quotes for YAML string values"
    enabled: bool = True
    name: str = "YamlQuotedStrings"
    version: str = "v0.0.1"
    severity: str = Severity.VERY_LOW
    tags: tuple[str, ...] = (Tag.CODING,)
    scope: str = RuleScope.PLAYBOOK

    def match(self, ctx: AnsibleRunContext) -> bool:
        """Check if context has raw content.

        Args:
            ctx: AnsibleRunContext to evaluate.

        Returns:
            True if current target has raw content.
        """
        if ctx.current is None:
            return False
        return bool(ctx.current.type in (RunTargetType.Task, RunTargetType.Play))

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        """Detect single-quoted YAML string values.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with detail, or None.
        """
        target = ctx.current
        if target is None:
            return None
        raw = getattr(target.spec, "yaml_lines", None) or ""
        if not raw:
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", target.file_info()),
                rule=self.get_metadata(),
            )

        single_quoted_lines: list[int] = []
        for i, line in enumerate(str(raw).splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if _SINGLE_QUOTED_VALUE.search(line):
                single_quoted_lines.append(i)

        verdict = len(single_quoted_lines) > 0
        detail: dict[str, object] = {}
        if single_quoted_lines:
            detail["single_quoted_lines"] = single_quoted_lines[:10]
            detail["message"] = f"found {len(single_quoted_lines)} single-quoted string(s); prefer double quotes"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", target.file_info()),
            rule=self.get_metadata(),
        )
