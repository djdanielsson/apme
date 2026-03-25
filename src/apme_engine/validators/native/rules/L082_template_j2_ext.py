"""Native rule L082: detect template sources not using .j2 extension."""

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

TEMPLATE_MODULES = frozenset(
    {
        "ansible.builtin.template",
        "ansible.legacy.template",
        "template",
    }
)


@dataclass
class TemplateJ2ExtRule(Rule):
    """Rule for template source files to use .j2 extension.

    Attributes:
        rule_id: Rule identifier.
        description: Rule description.
        enabled: Whether the rule is enabled.
        name: Rule name.
        version: Rule version.
        severity: Severity level.
        tags: Rule tags.
    """

    rule_id: str = "L082"
    description: str = "Template source files should use .j2 extension"
    enabled: bool = True
    name: str = "TemplateJ2Ext"
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
        """Check if template src uses .j2 extension and return result.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with detail, or None.
        """
        task = ctx.current
        if task is None:
            return None
        resolved = getattr(task.spec, "resolved_name", "") or ""
        if resolved not in TEMPLATE_MODULES:
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", task.file_info()),
                rule=self.get_metadata(),
            )
        module_options = getattr(task.spec, "module_options", None) or {}
        src = module_options.get("src", "")
        if not src or "{{" in src:
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", task.file_info()),
                rule=self.get_metadata(),
            )
        verdict = not src.endswith(".j2")
        detail: dict[str, object] = {}
        if verdict:
            detail["src"] = src
            detail["message"] = "template source files should use .j2 extension"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", task.file_info()),
            rule=self.get_metadata(),
        )
