"""Native rule L080: detect internal role variables not prefixed with double underscore."""

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
class InternalVarPrefixRule(Rule):
    """Rule for internal variables to be prefixed with __ (double underscore).

    Attributes:
        rule_id: Rule identifier.
        description: Rule description.
        enabled: Whether the rule is enabled.
        name: Rule name.
        version: Rule version.
        severity: Severity level.
        tags: Rule tags.
    """

    rule_id: str = "L080"
    description: str = "Internal role variables should be prefixed with __ (double underscore)"
    enabled: bool = True
    name: str = "InternalVarPrefix"
    version: str = "v0.0.1"
    severity: str = Severity.VERY_LOW
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
        """Check for set_fact/register vars in roles that lack __ prefix.

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
        filepath = ""
        fi = task.file_info()
        if fi:
            filepath = str(fi[0]) if fi else ""
        is_in_role = "/roles/" in filepath
        if not is_in_role:
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", fi),
                rule=self.get_metadata(),
            )
        module_options = getattr(task.spec, "module_options", None) or {}
        non_prefixed = [
            k for k in module_options if not k.startswith("__") and not k.startswith("_") and k != "cacheable"
        ]
        verdict = len(non_prefixed) > 0
        detail: dict[str, object] = {}
        if non_prefixed:
            detail["variables"] = non_prefixed
            detail["message"] = "internal role variables from set_fact should be prefixed with __"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", fi),
            rule=self.get_metadata(),
        )
