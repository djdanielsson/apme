"""Native rule L092: detect loop variable references in task names."""

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

_LOOP_VAR_IN_NAME = re.compile(r"\{\{\s*item\b")


@dataclass
class LoopVarInNameRule(Rule):
    """Rule for detecting loop variable references in task names.

    Attributes:
        rule_id: Rule identifier.
        description: Rule description.
        enabled: Whether the rule is enabled.
        name: Rule name.
        version: Rule version.
        severity: Severity level.
        tags: Rule tags.
    """

    rule_id: str = "L092"
    description: str = "Avoid loop variable references in task names"
    enabled: bool = True
    name: str = "LoopVarInName"
    version: str = "v0.0.1"
    severity: str = Severity.VERY_LOW
    tags: tuple[str, ...] = (Tag.CODING,)

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
        """Check for loop variable references in task names.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with detail, or None.
        """
        task = ctx.current
        if task is None:
            return None
        task_name = getattr(task.spec, "name", "") or ""
        if not task_name:
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", task.file_info()),
                rule=self.get_metadata(),
            )
        verdict = bool(_LOOP_VAR_IN_NAME.search(task_name))
        detail: dict[str, object] = {}
        if verdict:
            detail["task_name"] = task_name
            detail["message"] = "avoid loop variable references ({{ item }}) in task names"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", task.file_info()),
            rule=self.get_metadata(),
        )
