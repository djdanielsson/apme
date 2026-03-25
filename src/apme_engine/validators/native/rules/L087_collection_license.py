"""Native rule L087: detect collections missing LICENSE or COPYING file."""

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
class CollectionLicenseRule(Rule):
    """Rule for collections to have a LICENSE or COPYING file at root.

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

    rule_id: str = "L087"
    description: str = "Collection root should have a LICENSE or COPYING file"
    enabled: bool = True
    name: str = "CollectionLicense"
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
        """Check for LICENSE/COPYING file presence.

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
        has_license = any(
            name in file_names for name in ("LICENSE", "LICENSE.MD", "LICENSE.TXT", "COPYING", "COPYING.MD")
        )
        verdict = not has_license
        detail: dict[str, object] = {}
        if verdict:
            detail["message"] = "collection root should have a LICENSE or COPYING file"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", target.file_info()),
            rule=self.get_metadata(),
        )
