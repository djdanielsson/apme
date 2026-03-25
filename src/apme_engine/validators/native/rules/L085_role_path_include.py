"""Native rule L085: detect include_tasks/include_vars without explicit role_path prefix."""

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

INCLUDE_MODULES = frozenset(
    {
        "ansible.builtin.include_tasks",
        "ansible.builtin.include_vars",
        "ansible.builtin.include_role",
        "ansible.legacy.include_tasks",
        "ansible.legacy.include_vars",
        "ansible.legacy.include_role",
        "include_tasks",
        "include_vars",
        "include_role",
    }
)

_ROLE_PATH_REF = re.compile(r"role_path")


@dataclass
class RolePathIncludeRule(Rule):
    """Rule for using explicit role_path prefix in include paths within roles.

    Attributes:
        rule_id: Rule identifier.
        description: Rule description.
        enabled: Whether the rule is enabled.
        name: Rule name.
        version: Rule version.
        severity: Severity level.
        tags: Rule tags.
    """

    rule_id: str = "L085"
    description: str = "Use explicit role_path prefix in include paths within roles"
    enabled: bool = True
    name: str = "RolePathInclude"
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
        """Check for include paths missing role_path prefix.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with detail, or None.
        """
        task = ctx.current
        if task is None:
            return None
        resolved = getattr(task.spec, "resolved_name", "") or ""
        if resolved not in INCLUDE_MODULES:
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", task.file_info()),
                rule=self.get_metadata(),
            )
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
        module_options = getattr(task.spec, "module_options", None) or {}
        src = module_options.get("file", "") or module_options.get("_raw_params", "") or ""
        if not src or "{{" not in src:
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", fi),
                rule=self.get_metadata(),
            )
        verdict = "{{" in src and not _ROLE_PATH_REF.search(src)
        detail: dict[str, object] = {}
        if verdict:
            detail["include_path"] = src
            detail["message"] = "use {{ role_path }}/... prefix for variable include paths in roles"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", fi),
            rule=self.get_metadata(),
        )
