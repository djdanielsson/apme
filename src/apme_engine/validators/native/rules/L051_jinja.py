import re
from dataclasses import dataclass
from typing import Any

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

# Jinja should have spaces inside {{ }}: {{ foo }} not {{foo}}
JINJA_NO_SPACE = re.compile(r"\{\{[^\s\}].*?\}\}|\{\{.*?[^\s\{]\}\}")


@dataclass
class JinjaRule(Rule):
    rule_id: str = "L051"
    description: str = "Jinja formatting: use spaces inside {{ }} (e.g. {{ foo }})"
    enabled: bool = True
    name: str = "Jinja"
    version: str = "v0.0.1"
    severity: str = Severity.VERY_LOW
    tags: tuple[str, ...] = (Tag.QUALITY,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        task = ctx.current
        if task is None:
            return None
        spec = task.spec
        yaml_lines = getattr(spec, "yaml_lines", "") or ""
        options = getattr(spec, "options", None) or {}
        module_options = getattr(spec, "module_options", None) or {}
        text = yaml_lines
        for v in (options, module_options):
            if isinstance(v, dict):
                for val in v.values():
                    if isinstance(val, str):
                        text += " " + val
        violations = JINJA_NO_SPACE.findall(text)
        verdict = len(violations) > 0
        detail: dict[str, Any] = {}
        if violations:
            detail["bad_expressions"] = list(dict.fromkeys(violations))[:10]
            detail["message"] = "use spaces inside Jinja expressions: {{ var }}"
        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())
