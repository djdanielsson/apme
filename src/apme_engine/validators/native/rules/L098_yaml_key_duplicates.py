"""Native rule L098: detect duplicate keys in YAML mappings."""

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

_KEY_LINE = re.compile(r"^(\s*)([^\s#:][^:]*?)\s*:")


@dataclass
class YamlKeyDuplicatesRule(Rule):
    """Rule for detecting duplicate YAML mapping keys.

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

    rule_id: str = "L098"
    description: str = "YAML files should not have duplicate mapping keys"
    enabled: bool = True
    name: str = "YamlKeyDuplicates"
    version: str = "v0.0.1"
    severity: str = Severity.HIGH
    tags: tuple[str, ...] = (Tag.CODING,)
    scope: str = RuleScope.PLAYBOOK

    def match(self, ctx: AnsibleRunContext) -> bool:
        """Check if context has raw file content.

        Args:
            ctx: AnsibleRunContext to evaluate.

        Returns:
            True if current target has raw content.
        """
        if ctx.current is None:
            return False
        return bool(ctx.current.type in (RunTargetType.Task, RunTargetType.Play))

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        """Scan YAML content for duplicate keys at the same indentation level.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with duplicates detail, or None.
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

        seen: dict[tuple[int, str], int] = {}
        duplicates: list[str] = []
        for line in str(raw).splitlines():
            m = _KEY_LINE.match(line)
            if not m:
                continue
            indent_len = len(m.group(1))
            key = m.group(2).strip()
            loc = (indent_len, key)
            if loc in seen:
                duplicates.append(f"duplicate key '{key}' at indent {indent_len}")
            seen[loc] = seen.get(loc, 0) + 1

        verdict = len(duplicates) > 0
        detail: dict[str, object] = {}
        if duplicates:
            detail["duplicates"] = duplicates
            detail["message"] = "; ".join(duplicates)
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", target.file_info()),
            rule=self.get_metadata(),
        )
