"""Native rule L076: detect injected fact variables instead of ansible_facts bracket notation."""

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

INJECTED_FACTS = frozenset(
    {
        "ansible_distribution",
        "ansible_distribution_major_version",
        "ansible_distribution_version",
        "ansible_distribution_release",
        "ansible_os_family",
        "ansible_architecture",
        "ansible_hostname",
        "ansible_fqdn",
        "ansible_default_ipv4",
        "ansible_default_ipv6",
        "ansible_all_ipv4_addresses",
        "ansible_all_ipv6_addresses",
        "ansible_memtotal_mb",
        "ansible_processor_vcpus",
        "ansible_kernel",
        "ansible_system",
        "ansible_pkg_mgr",
        "ansible_service_mgr",
        "ansible_python_interpreter",
        "ansible_user_id",
        "ansible_env",
        "ansible_interfaces",
        "ansible_mounts",
        "ansible_devices",
        "ansible_virtualization_type",
        "ansible_virtualization_role",
        "ansible_selinux",
        "ansible_apparmor",
        "ansible_date_time",
        "ansible_dns",
        "ansible_domain",
        "ansible_machine",
        "ansible_nodename",
        "ansible_processor",
        "ansible_swaptotal_mb",
        "ansible_uptime_seconds",
    }
)

_FACT_PATTERN = re.compile(r"\b(" + "|".join(re.escape(f) for f in sorted(INJECTED_FACTS)) + r")\b")


@dataclass
class AnsibleFactsBracketRule(Rule):
    """Rule for using ansible_facts bracket notation instead of injected fact variables.

    Attributes:
        rule_id: Rule identifier.
        description: Rule description.
        enabled: Whether the rule is enabled.
        name: Rule name.
        version: Rule version.
        severity: Severity level.
        tags: Rule tags.
    """

    rule_id: str = "L076"
    description: str = "Use ansible_facts['key'] bracket notation instead of injected fact variables"
    enabled: bool = True
    name: str = "AnsibleFactsBracket"
    version: str = "v0.0.1"
    severity: str = Severity.VERY_LOW
    tags: tuple[str, ...] = (Tag.VARIABLE,)

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
        """Check for injected fact variable usage and return result.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with found_facts detail, or None.
        """
        task = ctx.current
        if task is None:
            return None
        yaml_lines = getattr(task.spec, "yaml_lines", "") or ""
        found = sorted(set(_FACT_PATTERN.findall(yaml_lines)))
        verdict = len(found) > 0
        detail: dict[str, object] = {}
        if found:
            detail["found_facts"] = found
            detail["message"] = "use ansible_facts['key'] bracket notation instead"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", task.file_info()),
            rule=self.get_metadata(),
        )
