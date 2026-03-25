"""Native rule L101: detect variable names that collide with Ansible reserved names."""

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

RESERVED_NAMES = frozenset(
    {
        "ansible_facts",
        "ansible_host",
        "ansible_port",
        "ansible_user",
        "ansible_connection",
        "ansible_ssh_private_key_file",
        "ansible_become",
        "ansible_become_user",
        "ansible_become_method",
        "ansible_become_pass",
        "ansible_python_interpreter",
        "ansible_check_mode",
        "ansible_diff_mode",
        "ansible_verbosity",
        "ansible_version",
        "ansible_play_hosts",
        "ansible_play_batch",
        "ansible_play_name",
        "ansible_role_name",
        "ansible_collection_name",
        "ansible_loop",
        "ansible_loop_var",
        "ansible_index_var",
        "ansible_parent_role_names",
        "ansible_parent_role_paths",
        "ansible_dependent_role_names",
        "ansible_run_tags",
        "ansible_skip_tags",
        "ansible_search_path",
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
        "ansible_config_file",
        "ansible_playbook_python",
    }
)


@dataclass
class VarNamingReservedRule(Rule):
    """Rule for variable names not to collide with Ansible reserved names.

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

    rule_id: str = "L101"
    description: str = "Variable names must not collide with Ansible reserved names"
    enabled: bool = True
    name: str = "VarNamingReserved"
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
        """Check variable definitions for reserved-name collisions.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with reserved_vars detail, or None.
        """
        task = ctx.current
        if task is None:
            return None
        spec = task.spec
        module = getattr(spec, "module", None) or ""
        module_opts = getattr(spec, "module_options", None) or {}

        reserved_vars: list[str] = []

        if module in ("ansible.builtin.set_fact", "set_fact") and isinstance(module_opts, dict):
            for key in module_opts:
                if key in ("cacheable",):
                    continue
                if key in RESERVED_NAMES:
                    reserved_vars.append(key)

        register = getattr(spec, "options", None) or {}
        if isinstance(register, dict):
            reg_name = register.get("register")
            if reg_name and str(reg_name) in RESERVED_NAMES:
                reserved_vars.append(str(reg_name))

        verdict = len(reserved_vars) > 0
        detail: dict[str, object] = {}
        if reserved_vars:
            detail["reserved_vars"] = reserved_vars
            detail["message"] = f"variable name(s) {', '.join(reserved_vars)} collide with Ansible reserved names"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", task.file_info()),
            rule=self.get_metadata(),
        )
