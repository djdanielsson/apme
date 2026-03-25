"""Native rule L097: detect duplicate task names within a play."""

from collections import Counter
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
class NameUniqueRule(Rule):
    """Rule for task names to be unique within a play.

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

    rule_id: str = "L097"
    description: str = "Task names should be unique within a play"
    enabled: bool = True
    name: str = "NameUnique"
    version: str = "v0.0.1"
    severity: str = Severity.LOW
    tags: tuple[str, ...] = (Tag.QUALITY,)
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
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        """Check if a task name appears more than once among sibling tasks.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with duplicate names detail, or None.
        """
        task = ctx.current
        if task is None:
            return None
        task_name = getattr(task.spec, "name", None)
        if not task_name:
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", task.file_info()),
                rule=self.get_metadata(),
            )

        all_targets = list(ctx.sequence) if ctx.sequence else []
        all_names = [
            getattr(t.spec, "name", None)
            for t in all_targets
            if t.type == RunTargetType.Task and getattr(t.spec, "name", None)
        ]
        counts = Counter(all_names)
        verdict = counts.get(task_name, 0) > 1
        detail: dict[str, object] = {}
        if verdict:
            detail["duplicate_name"] = task_name
            detail["count"] = counts[task_name]
            detail["message"] = f"task name '{task_name}' is not unique (appears {counts[task_name]} times)"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", task.file_info()),
            rule=self.get_metadata(),
        )
