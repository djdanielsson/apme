"""Native rule L103: detect collections missing a CHANGELOG file."""

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


@dataclass
class GalaxyChangelogRule(Rule):
    """Rule for collections to have a CHANGELOG file at root.

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

    rule_id: str = "L103"
    description: str = "Collection should have a CHANGELOG file"
    enabled: bool = True
    name: str = "GalaxyChangelog"
    version: str = "v0.0.1"
    severity: str = Severity.LOW
    tags: tuple[str, ...] = (Tag.QUALITY,)
    scope: str = RuleScope.COLLECTION

    def match(self, ctx: AnsibleRunContext) -> bool:
        """Check if context has a collection target.

        Args:
            ctx: AnsibleRunContext to evaluate.

        Returns:
            True if current target is a collection-level element.
        """
        if ctx.current is None:
            return False
        return False  # no Collection target type yet; enable when engine supports it

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        """Check for CHANGELOG file presence.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with detail, or None.
        """
        target = ctx.current
        if target is None:
            return None
        files = getattr(target.spec, "files", None) or []
        file_names = {str(f).rsplit("/", 1)[-1].upper() for f in files}
        has_changelog = any(name.startswith("CHANGELOG") for name in file_names)
        verdict = not has_changelog
        detail: dict[str, object] = {}
        if verdict:
            detail["message"] = "collection should have a CHANGELOG file"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", target.file_info()),
            rule=self.get_metadata(),
        )
