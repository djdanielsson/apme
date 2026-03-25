"""Native rule L093: detect set_fact overriding role defaults/vars names."""

from dataclasses import dataclass
from typing import cast

from apme_engine.engine.models import (
    AnsibleRunContext,
    Rule,
    RuleResult,
    RunTargetType,
    Severity,
    YAMLDict,
)
from apme_engine.engine.models import (
    RuleTag as Tag,
)


@dataclass
class SetFactOverrideRule(Rule):
    """Rule for detecting set_fact that overrides role default/var names.

    Attributes:
        rule_id: Rule identifier.
        description: Rule description.
        enabled: Whether the rule is enabled.
        name: Rule name.
        version: Rule version.
        severity: Severity level.
        tags: Rule tags.
    """

    rule_id: str = "L093"
    description: str = "Do not override role defaults/vars with set_fact; use a different name"
    enabled: bool = True
    name: str = "SetFactOverride"
    version: str = "v0.0.1"
    severity: str = Severity.LOW
    tags: tuple[str, ...] = (Tag.VARIABLE,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        """Check if context has a task target.

        Args:
            ctx: AnsibleRunContext to evaluate.

        Returns:
            True if current target is a task.
        """
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        """Check for set_fact overriding role defaults.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with detail, or None.
        """
        task = ctx.current
        if task is None:
            return None
        resolved = getattr(task.spec, "resolved_name", "") or ""
        if resolved not in ("ansible.builtin.set_fact", "ansible.legacy.set_fact", "set_fact"):
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", task.file_info()),
                rule=self.get_metadata(),
            )
        module_options = getattr(task.spec, "module_options", None) or {}
        role_defaults = set()
        if hasattr(ctx, "role_defaults"):
            role_defaults = set(ctx.role_defaults or {})
        role_vars = set()
        if hasattr(ctx, "role_vars"):
            role_vars = set(ctx.role_vars or {})
        known_vars = role_defaults | role_vars
        if not known_vars:
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", task.file_info()),
                rule=self.get_metadata(),
            )
        overridden = [k for k in module_options if k in known_vars and k != "cacheable"]
        verdict = len(overridden) > 0
        detail: dict[str, object] = {}
        if overridden:
            detail["overridden_vars"] = overridden
            detail["message"] = "do not override role defaults/vars with set_fact; use a different name"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", task.file_info()),
            rule=self.get_metadata(),
        )
