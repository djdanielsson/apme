"""Native rule L084: detect task names in included files missing a sub-task prefix."""

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
class SubtaskPrefixRule(Rule):
    """Rule for task names in included files to use a sub-task prefix.

    Attributes:
        rule_id: Rule identifier.
        description: Rule description.
        enabled: Whether the rule is enabled.
        name: Rule name.
        version: Rule version.
        severity: Severity level.
        tags: Rule tags.
    """

    rule_id: str = "L084"
    description: str = "Task names in included sub-task files should use a prefix (e.g. 'sub | Description')"
    enabled: bool = True
    name: str = "SubtaskPrefix"
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
        """Check if task names in included files have a prefix separator.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with detail, or None.
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
        import os

        basename = os.path.basename(filepath)
        if basename == "main.yml" or basename == "main.yaml":
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", fi),
                rule=self.get_metadata(),
            )
        task_name = getattr(task.spec, "name", "") or ""
        if not task_name:
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", fi),
                rule=self.get_metadata(),
            )
        verdict = "|" not in task_name
        detail: dict[str, object] = {}
        if verdict:
            detail["task_name"] = task_name
            detail["file"] = basename
            detail["message"] = "task names in included files should use prefix (e.g. 'sub | Description')"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", fi),
            rule=self.get_metadata(),
        )
