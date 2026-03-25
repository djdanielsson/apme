"""Native rule L079: detect role variables not prefixed with the role name."""

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

SKIP_VARS = frozenset(
    {
        "ansible_become",
        "ansible_become_method",
        "ansible_become_user",
        "ansible_connection",
        "ansible_host",
        "ansible_port",
        "ansible_user",
        "ansible_python_interpreter",
        "ansible_ssh_common_args",
        "ansible_ssh_private_key_file",
    }
)


@dataclass
class RoleVarPrefixRule(Rule):
    """Rule for role defaults/vars to be prefixed with the role name.

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

    rule_id: str = "L079"
    description: str = "Role defaults/vars should be prefixed with the role name"
    enabled: bool = True
    name: str = "RoleVarPrefix"
    version: str = "v0.0.1"
    severity: str = Severity.LOW
    tags: tuple[str, ...] = (Tag.VARIABLE,)
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
        """Check if role defaults/vars are prefixed with the role name.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with unprefixed_vars detail, or None.
        """
        target = ctx.current
        if target is None:
            return None
        role_name = getattr(target.spec, "name", "") or ""
        if not role_name:
            role_name = getattr(target, "name", "") or ""
        if not role_name:
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", target.file_info()),
                rule=self.get_metadata(),
            )
        defaults = getattr(target.spec, "defaults", None) or {}
        role_vars = getattr(target.spec, "variables", None) or {}
        all_vars = list(defaults.keys()) + list(role_vars.keys())
        prefix = role_name.replace("-", "_") + "_"
        unprefixed = [v for v in all_vars if v not in SKIP_VARS and not v.startswith(prefix) and not v.startswith("__")]
        verdict = len(unprefixed) > 0
        detail: dict[str, object] = {}
        if unprefixed:
            detail["unprefixed_vars"] = unprefixed[:20]
            detail["expected_prefix"] = prefix
            detail["message"] = f"role variables should be prefixed with '{prefix}'"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", target.file_info()),
            rule=self.get_metadata(),
        )
