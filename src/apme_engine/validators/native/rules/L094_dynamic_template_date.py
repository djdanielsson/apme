"""Native rule L094: detect dynamic date expressions in templates."""

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

_DYNAMIC_DATE = re.compile(
    r"ansible_date_time"
    r"|now\(\)"
    r"|strftime"
    r"|lookup\(['\"]pipe['\"],\s*['\"]date",
    re.IGNORECASE,
)

TEMPLATE_MODULES = frozenset(
    {
        "ansible.builtin.template",
        "ansible.legacy.template",
        "template",
    }
)


@dataclass
class DynamicTemplateDateRule(Rule):
    """Rule for detecting dynamic date expressions in template content.

    Attributes:
        rule_id: Rule identifier.
        description: Rule description.
        enabled: Whether the rule is enabled.
        name: Rule name.
        version: Rule version.
        severity: Severity level.
        tags: Rule tags.
    """

    rule_id: str = "L094"
    description: str = "Do not put dynamic dates in templates; breaks change detection"
    enabled: bool = True
    name: str = "DynamicTemplateDate"
    version: str = "v0.0.1"
    severity: str = Severity.LOW
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
        """Check for dynamic date expressions in template tasks.

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
        yaml_lines = getattr(task.spec, "yaml_lines", "") or ""
        module_options = getattr(task.spec, "module_options", None) or {}
        content_to_check = yaml_lines + str(module_options)
        found = _DYNAMIC_DATE.findall(content_to_check)
        verdict = len(found) > 0
        detail: dict[str, object] = {}
        if found:
            detail["found_patterns"] = list(set(found))
            detail["message"] = "do not put dynamic dates in templates; breaks idempotent change detection"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", task.file_info()),
            rule=self.get_metadata(),
        )
