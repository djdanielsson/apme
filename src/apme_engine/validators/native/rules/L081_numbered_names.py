"""Native rule L081: detect numbered role/playbook names."""

import re
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

_NUMBERED_PREFIX = re.compile(r"^\d+[_\-.]")


@dataclass
class NumberedNamesRule(Rule):
    """Rule for detecting numbered role or playbook names (e.g. 01_setup.yml).

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

    rule_id: str = "L081"
    description: str = "Do not number roles or playbooks"
    enabled: bool = True
    name: str = "NumberedNames"
    version: str = "v0.0.1"
    severity: str = Severity.LOW
    tags: tuple[str, ...] = (Tag.CODING,)
    scope: str = RuleScope.PLAYBOOK

    def match(self, ctx: AnsibleRunContext) -> bool:
        """Check if context has a task target.

        Args:
            ctx: AnsibleRunContext to evaluate.

        Returns:
            True if current target is a task.
        """
        if ctx.current is None:
            return False
        return bool(ctx.current.type in (RunTargetType.Task, RunTargetType.Role))

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        """Check for numbered file/role names and return result.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with detail, or None.
        """
        target = ctx.current
        if target is None:
            return None
        filepath = ""
        fi = target.file_info()
        if fi:
            filepath = str(fi[0]) if fi else ""
        if not filepath:
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", fi),
                rule=self.get_metadata(),
            )
        import os

        basename = os.path.basename(filepath)
        verdict = bool(_NUMBERED_PREFIX.match(basename))
        detail: dict[str, object] = {}
        if verdict:
            detail["filename"] = basename
            detail["message"] = "do not number roles or playbooks; use descriptive names"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", fi),
            rule=self.get_metadata(),
        )
