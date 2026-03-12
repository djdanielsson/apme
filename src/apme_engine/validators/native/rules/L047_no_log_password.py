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

PASSWORD_LIKE_KEYS = frozenset({"password", "passwd", "pwd", "secret", "token", "api_key", "apikey", "private_key"})


def _option_keys_look_like_password(module_options: object) -> bool:
    if not isinstance(module_options, dict):
        return False
    return any(k and k.lower() in PASSWORD_LIKE_KEYS for k in module_options)


@dataclass
class NoLogPasswordRule(Rule):
    rule_id: str = "L047"
    description: str = "Tasks with password-like parameters should set no_log: true"
    enabled: bool = False
    name: str = "NoLogPassword"
    version: str = "v0.0.1"
    severity: str = Severity.MEDIUM
    tags: tuple[str, ...] = (Tag.SYSTEM,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        task = ctx.current
        if task is None:
            return None
        options = getattr(task.spec, "options", None) or {}
        module_options = getattr(task.spec, "module_options", None) or {}
        has_no_log = options.get("no_log") is True
        has_password_like = _option_keys_look_like_password(module_options) or _option_keys_look_like_password(options)
        verdict = has_password_like and not has_no_log
        detail = {}
        if verdict:
            detail["message"] = "password-like parameter detected; set no_log: true to avoid logging"
        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())
