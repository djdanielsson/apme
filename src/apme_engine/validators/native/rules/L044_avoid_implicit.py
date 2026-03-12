from dataclasses import dataclass

from apme_engine.engine.models import (
    AnsibleRunContext,
    Rule,
    RuleResult,
    RunTargetType,
    Severity,
)
from apme_engine.engine.models import (
    RuleTag as Tag,
)

# Modules that commonly require explicit "state" to avoid implicit default behavior
MODULES_NEEDING_STATE = frozenset(
    {
        "ansible.builtin.file",
        "ansible.builtin.copy",
        "ansible.builtin.template",
        "ansible.builtin.package",
        "ansible.builtin.apt",
        "ansible.builtin.dnf",
        "ansible.builtin.yum",
        "ansible.builtin.service",
        "ansible.builtin.mount",
        "ansible.builtin.user",
        "ansible.builtin.group",
        "ansible.legacy.file",
        "ansible.legacy.copy",
        "ansible.legacy.template",
        "ansible.legacy.package",
        "ansible.legacy.apt",
        "ansible.legacy.dnf",
        "ansible.legacy.yum",
        "ansible.legacy.service",
        "ansible.legacy.mount",
        "ansible.legacy.user",
        "ansible.legacy.group",
    }
)


@dataclass
class AvoidImplicitRule(Rule):
    rule_id: str = "L044"
    description: str = "Avoid implicit behavior; set state (or other key) explicitly where it matters"
    enabled: bool = True
    name: str = "AvoidImplicit"
    version: str = "v0.0.1"
    severity: str = Severity.LOW
    tags: tuple[str, ...] = (Tag.CODING,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        task = ctx.current
        if task is None:
            return None
        resolved = getattr(task.spec, "resolved_name", "") or ""
        if resolved not in MODULES_NEEDING_STATE:
            return RuleResult(verdict=False, file=task.file_info(), rule=self.get_metadata())
        module_options = getattr(task.spec, "module_options", None) or {}
        has_state = "state" in module_options
        verdict = not has_state
        detail = {}
        if verdict:
            detail["module"] = resolved
            detail["message"] = "state is not set; consider setting state explicitly"
        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())
