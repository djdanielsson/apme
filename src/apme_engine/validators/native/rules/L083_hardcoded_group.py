"""Native rule L083: detect hardcoded host group names in roles."""

import re
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

_GROUP_REF = re.compile(r"groups\[(['\"])(\w+)\1\]")


@dataclass
class HardcodedGroupRule(Rule):
    """Rule for detecting hardcoded host group names in role tasks.

    Attributes:
        rule_id: Rule identifier.
        description: Rule description.
        enabled: Whether the rule is enabled.
        name: Rule name.
        version: Rule version.
        severity: Severity level.
        tags: Rule tags.
    """

    rule_id: str = "L083"
    description: str = "Do not hardcode host group names in roles"
    enabled: bool = True
    name: str = "HardcodedGroup"
    version: str = "v0.0.1"
    severity: str = Severity.LOW
    tags: tuple[str, ...] = (Tag.VARIABLE,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        """Check if context has a task target in a role.

        Args:
            ctx: AnsibleRunContext to evaluate.

        Returns:
            True if current target is a task.
        """
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        """Check for hardcoded group names in role tasks.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with found_groups detail, or None.
        """
        task = ctx.current
        if task is None:
            return None
        filepath = ""
        fi = task.file_info()
        if fi:
            filepath = str(fi[0]) if fi else ""
        if "/roles/" not in filepath:
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", fi),
                rule=self.get_metadata(),
            )
        yaml_lines = getattr(task.spec, "yaml_lines", "") or ""
        found_groups = sorted(set(m.group(2) for m in _GROUP_REF.finditer(yaml_lines)))
        skip_groups = {"all", "ungrouped"}
        found_groups = [g for g in found_groups if g not in skip_groups]
        verdict = len(found_groups) > 0
        detail: dict[str, object] = {}
        if found_groups:
            detail["found_groups"] = found_groups
            detail["message"] = "do not hardcode host group names in roles; parameterize them"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", fi),
            rule=self.get_metadata(),
        )
