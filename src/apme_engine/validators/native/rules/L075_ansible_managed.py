"""Native rule L075: detect template tasks with non-.j2 source files."""

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
class AnsibleManagedRule(Rule):
    """Rule for template tasks whose src does not use .j2 extension.

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

    rule_id: str = "L075"
    description: str = "Template source files should use .j2 extension (ansible_managed best practice)"
    enabled: bool = True
    name: str = "AnsibleManaged"
    version: str = "v0.0.1"
    severity: str = Severity.LOW
    tags: tuple[str, ...] = (Tag.CODING,)
    scope: str = RuleScope.ROLE

    def match(self, ctx: AnsibleRunContext) -> bool:
        """Check if context has a task target using template module.

        Args:
            ctx: AnsibleRunContext to evaluate.

        Returns:
            True if current target is a task.
        """
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        """Check if template task src uses .j2 extension.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with detail, or None.
        """
        task = ctx.current
        if task is None:
            return None
        resolved = getattr(task.spec, "resolved_name", "") or ""
        template_modules = {
            "ansible.builtin.template",
            "ansible.legacy.template",
            "template",
        }
        if resolved not in template_modules:
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", task.file_info()),
                rule=self.get_metadata(),
            )
        module_options = getattr(task.spec, "module_options", None) or {}
        src = module_options.get("src", "")
        verdict = bool(src and not src.endswith(".j2"))
        detail: dict[str, object] = {}
        if verdict:
            detail["src"] = src
            detail["message"] = "template source should use .j2 extension and include ansible_managed"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", task.file_info()),
            rule=self.get_metadata(),
        )
