"""Native rule L104: detect collections missing meta/runtime.yml."""

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
class GalaxyRuntimeRule(Rule):
    """Rule for collections to have meta/runtime.yml.

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

    rule_id: str = "L104"
    description: str = "Collection should have meta/runtime.yml"
    enabled: bool = True
    name: str = "GalaxyRuntime"
    version: str = "v0.0.1"
    severity: str = Severity.MEDIUM
    tags: tuple[str, ...] = (Tag.DEPENDENCY,)
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
        """Check for meta/runtime.yml file presence.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with detail, or None.
        """
        target = ctx.current
        if target is None:
            return None
        files = getattr(target.spec, "files", None) or []
        file_paths = [str(f) for f in files]
        has_runtime = any(p.endswith("meta/runtime.yml") or p.endswith("meta/runtime.yaml") for p in file_paths)
        verdict = not has_runtime
        detail: dict[str, object] = {}
        if verdict:
            detail["message"] = "collection should have meta/runtime.yml"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", target.file_info()),
            rule=self.get_metadata(),
        )
