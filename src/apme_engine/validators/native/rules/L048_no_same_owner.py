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

COPY_MODULES = frozenset(
    {
        "ansible.builtin.copy",
        "ansible.legacy.copy",
    }
)


@dataclass
class NoSameOwnerRule(Rule):
    rule_id: str = "L048"
    description: str = "copy with remote_src should set owner explicitly; avoid same-owner default"
    enabled: bool = False
    name: str = "NoSameOwner"
    version: str = "v0.0.1"
    severity: str = Severity.LOW
    tags: tuple[str, ...] = (Tag.SYSTEM,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        task = ctx.current
        if task is None:
            return None
        resolved = getattr(task.spec, "resolved_name", "") or ""
        if resolved not in COPY_MODULES:
            return RuleResult(verdict=False, file=task.file_info(), rule=self.get_metadata())
        module_options = getattr(task.spec, "module_options", None) or {}
        remote_src = module_options.get("remote_src")
        if not remote_src:
            return RuleResult(verdict=False, file=task.file_info(), rule=self.get_metadata())
        has_owner = "owner" in module_options
        verdict = not has_owner
        detail = {}
        if verdict:
            detail["message"] = "copy with remote_src should set owner explicitly"
        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())
