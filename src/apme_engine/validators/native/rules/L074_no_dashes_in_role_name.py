"""Native rule L074: detect dashes in role names."""

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
class NoDashesInRoleNameRule(Rule):
    """Rule for detecting dashes in role names (incompatible with collections).

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

    rule_id: str = "L074"
    description: str = "Role names should not contain dashes"
    enabled: bool = True
    name: str = "NoDashesInRoleName"
    version: str = "v0.0.1"
    severity: str = Severity.LOW
    tags: tuple[str, ...] = (Tag.DEPENDENCY,)
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
        """Check for dashes in role name and return result.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with role_name detail, or None.
        """
        target = ctx.current
        if target is None:
            return None
        role_name = getattr(target.spec, "name", "") or ""
        if not role_name:
            role_name = getattr(target, "name", "") or ""
        verdict = "-" in role_name
        detail: dict[str, object] = {}
        if verdict:
            detail["role_name"] = role_name
            detail["message"] = "role names with dashes cause collection compatibility issues"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", target.file_info()),
            rule=self.get_metadata(),
        )
