"""Native rule L102: detect attempts to set read-only Ansible variables."""

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

READ_ONLY_VARS = frozenset(
    {
        "ansible_version",
        "ansible_play_hosts",
        "ansible_play_hosts_all",
        "ansible_play_batch",
        "ansible_play_name",
        "ansible_role_name",
        "ansible_collection_name",
        "ansible_run_tags",
        "ansible_skip_tags",
        "ansible_check_mode",
        "ansible_diff_mode",
        "ansible_verbosity",
        "ansible_config_file",
        "ansible_playbook_python",
        "ansible_search_path",
        "ansible_loop",
        "ansible_loop_var",
        "ansible_index_var",
        "ansible_parent_role_names",
        "ansible_parent_role_paths",
        "ansible_dependent_role_names",
        "inventory_hostname",
        "inventory_hostname_short",
        "inventory_file",
        "inventory_dir",
        "groups",
        "group_names",
        "hostvars",
        "playbook_dir",
        "role_path",
        "role_name",
    }
)


@dataclass
class VarNamingReadOnlyRule(Rule):
    """Rule for not setting read-only Ansible variables.

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

    rule_id: str = "L102"
    description: str = "Do not set read-only Ansible variables"
    enabled: bool = True
    name: str = "VarNamingReadOnly"
    version: str = "v0.0.1"
    severity: str = Severity.HIGH
    tags: tuple[str, ...] = (Tag.VARIABLE,)
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
        """Check if task attempts to set read-only variables.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with read_only_vars detail, or None.
        """
        task = ctx.current
        if task is None:
            return None
        spec = task.spec
        module = getattr(spec, "module", None) or ""
        module_opts = getattr(spec, "module_options", None) or {}

        violations: list[str] = []

        if module in ("ansible.builtin.set_fact", "set_fact") and isinstance(module_opts, dict):
            for key in module_opts:
                if key in ("cacheable",):
                    continue
                if key in READ_ONLY_VARS:
                    violations.append(key)

        options = getattr(spec, "options", None) or {}
        if isinstance(options, dict):
            reg_name = options.get("register")
            if reg_name and str(reg_name) in READ_ONLY_VARS:
                violations.append(str(reg_name))

        verdict = len(violations) > 0
        detail: dict[str, object] = {}
        if violations:
            detail["read_only_vars"] = violations
            detail["message"] = f"attempting to set read-only variable(s): {', '.join(violations)}"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", task.file_info()),
            rule=self.get_metadata(),
        )
