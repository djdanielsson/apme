"""Native rule L090: detect plugin entry files that are too large."""

from dataclasses import dataclass
from typing import cast

from apme_engine.engine.models import (
    AnsibleRunContext,
    Rule,
    RuleResult,
    RuleScope,
    Severity,
    YAMLDict,
)
from apme_engine.engine.models import (
    RuleTag as Tag,
)

MAX_PLUGIN_LINES = 500


@dataclass
class PluginFileSizeRule(Rule):
    """Rule for plugin entry files to be small; move helpers to module_utils.

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

    rule_id: str = "L090"
    description: str = "Plugin entry files should be small; move helpers to module_utils"
    enabled: bool = True
    name: str = "PluginFileSize"
    version: str = "v0.0.1"
    severity: str = Severity.VERY_LOW
    tags: tuple[str, ...] = (Tag.QUALITY,)
    scope: str = RuleScope.COLLECTION

    def match(self, ctx: AnsibleRunContext) -> bool:
        """Check if context has a plugin/module target.

        Args:
            ctx: AnsibleRunContext to evaluate.

        Returns:
            True if current target is relevant.
        """
        if ctx.current is None:
            return False
        return False  # no Python-file target type yet; YAML targets don't carry .py content

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        """Check plugin file line count.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with detail, or None.
        """
        target = ctx.current
        if target is None:
            return None
        filepath = ""
        fi = target.file_info()
        if fi:
            filepath = str(fi[0]) if fi else ""
        if not filepath.endswith(".py"):
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", fi),
                rule=self.get_metadata(),
            )
        if "/plugins/" not in filepath and "/modules/" not in filepath:
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", fi),
                rule=self.get_metadata(),
            )
        content = getattr(target.spec, "content", "") or ""
        if not content:
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", fi),
                rule=self.get_metadata(),
            )
        line_count = content.count("\n") + 1
        verdict = line_count > MAX_PLUGIN_LINES
        detail: dict[str, object] = {}
        if verdict:
            detail["line_count"] = line_count
            detail["max_lines"] = MAX_PLUGIN_LINES
            detail["message"] = f"plugin file is {line_count} lines; consider moving helpers to module_utils"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", fi),
            rule=self.get_metadata(),
        )
