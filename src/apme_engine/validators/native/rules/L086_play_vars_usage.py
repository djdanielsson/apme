"""Native rule L086: detect routine config in playbook/play vars instead of inventory."""

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
class PlayVarsUsageRule(Rule):
    """Rule for avoiding play-level vars for routine configuration.

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

    rule_id: str = "L086"
    description: str = "Avoid playbook/play vars for routine config; use inventory vars"
    enabled: bool = True
    name: str = "PlayVarsUsage"
    version: str = "v0.0.1"
    severity: str = Severity.VERY_LOW
    tags: tuple[str, ...] = (Tag.VARIABLE,)
    scope: str = RuleScope.PLAY

    def match(self, ctx: AnsibleRunContext) -> bool:
        """Check if context has a play target.

        Args:
            ctx: AnsibleRunContext to evaluate.

        Returns:
            True if current target is a play.
        """
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Play)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        """Check for play-level vars and return result.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with detail, or None.
        """
        target = ctx.current
        if target is None:
            return None
        play_vars = getattr(target.spec, "variables", None) or {}
        if not play_vars:
            play_vars = getattr(target.spec, "vars", None) or {}
        var_count = len(play_vars) if isinstance(play_vars, dict) else 0
        verdict = var_count > 5
        detail: dict[str, object] = {}
        if verdict:
            detail["var_count"] = var_count
            detail["message"] = "consider moving routine config variables to inventory group_vars"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", target.file_info()),
            rule=self.get_metadata(),
        )
