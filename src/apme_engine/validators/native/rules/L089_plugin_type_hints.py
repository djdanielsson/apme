"""Native rule L089: detect plugin Python files missing type hints."""

import re
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

_DEF_NO_HINTS = re.compile(r"def\s+\w+\s*\([^)]*\)\s*:")
_DEF_WITH_HINTS = re.compile(r"def\s+\w+\s*\([^)]*\)\s*->\s*\S+\s*:")


@dataclass
class PluginTypeHintsRule(Rule):
    """Rule for plugin Python files to include type hints.

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

    rule_id: str = "L089"
    description: str = "Plugin Python files should include type hints"
    enabled: bool = True
    name: str = "PluginTypeHints"
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
        """Check for type hints in Python plugin code.

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
        all_defs = len(_DEF_NO_HINTS.findall(content))
        typed_defs = len(_DEF_WITH_HINTS.findall(content))
        if all_defs == 0:
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", fi),
                rule=self.get_metadata(),
            )
        verdict = typed_defs < all_defs // 2
        detail: dict[str, object] = {}
        if verdict:
            detail["total_functions"] = all_defs
            detail["typed_functions"] = typed_defs
            detail["message"] = "plugin Python files should include type hints for clarity"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", fi),
            rule=self.get_metadata(),
        )
