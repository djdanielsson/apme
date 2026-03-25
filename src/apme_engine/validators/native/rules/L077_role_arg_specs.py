"""Native rule L077: detect roles missing meta/argument_specs.yml."""

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


@dataclass
class RoleArgSpecsRule(Rule):
    """Rule for roles that should have meta/argument_specs.yml for fail-fast validation.

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

    rule_id: str = "L077"
    description: str = "Roles should have meta/argument_specs.yml for fail-fast parameter validation"
    enabled: bool = True
    name: str = "RoleArgSpecs"
    version: str = "v0.0.1"
    severity: str = Severity.LOW
    tags: tuple[str, ...] = (Tag.QUALITY,)
    scope: str = RuleScope.ROLE

    def match(self, ctx: AnsibleRunContext) -> bool:
        """Check if context has a role target.

        Args:
            ctx: AnsibleRunContext to evaluate.

        Returns:
            True if current target is a role.
        """
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Role)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        """Check for presence of argument_specs.yml and return result.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with detail, or None.
        """
        target = ctx.current
        if target is None:
            return None
        metadata = getattr(target.spec, "metadata", None) or {}
        has_arg_specs = bool(metadata.get("argument_specs"))
        if not has_arg_specs:
            spec_files = getattr(target.spec, "files", None) or []
            has_arg_specs = any("argument_specs" in str(f) for f in spec_files)
        verdict = not has_arg_specs
        detail: dict[str, object] = {}
        if verdict:
            detail["message"] = "role should have meta/argument_specs.yml for fail-fast validation"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", target.file_info()),
            rule=self.get_metadata(),
        )
