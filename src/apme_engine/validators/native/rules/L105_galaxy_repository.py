"""Native rule L105: detect galaxy.yml missing repository key."""

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
class GalaxyRepositoryRule(Rule):
    """Rule for galaxy.yml to have a repository key.

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

    rule_id: str = "L105"
    description: str = "galaxy.yml should have a repository key"
    enabled: bool = True
    name: str = "GalaxyRepository"
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
        """Check for repository key in galaxy.yml metadata.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with detail, or None.
        """
        target = ctx.current
        if target is None:
            return None
        metadata = getattr(target.spec, "metadata", None) or {}
        if not isinstance(metadata, dict):
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", target.file_info()),
                rule=self.get_metadata(),
            )
        has_repo = bool(metadata.get("repository"))
        verdict = not has_repo
        detail: dict[str, object] = {}
        if verdict:
            detail["message"] = "galaxy.yml should include a repository key"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", target.file_info()),
            rule=self.get_metadata(),
        )
