import re
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

# Bare variable: {{ var }} or {{var}} with no filter (no |)
BARE_VAR_PATTERN = re.compile(r"\{\{\s*[\w.]+\s*\}\}")


def _find_bare_vars(text: str | None) -> list[str]:
    if not text or not isinstance(text, str):
        return []
    return BARE_VAR_PATTERN.findall(text)


def _collect_strings_from_dict(d: object, out: list[str]) -> None:
    if not isinstance(d, dict):
        if isinstance(d, str):
            out.append(d)
        return
    for v in d.values():
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, dict):
            _collect_strings_from_dict(v, out)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    out.append(item)
                elif isinstance(item, dict):
                    _collect_strings_from_dict(item, out)


@dataclass
class DeprecatedBareVarsRule(Rule):
    rule_id: str = "L043"
    description: str = "Deprecated bare variables (e.g. {{ foo }}); prefer explicit form"
    enabled: bool = True
    name: str = "DeprecatedBareVars"
    version: str = "v0.0.1"
    severity: str = Severity.LOW
    tags: tuple[str, ...] = (Tag.VARIABLE,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        task = ctx.current
        if task is None:
            return None
        spec = task.spec
        sources = []
        yaml_lines = getattr(spec, "yaml_lines", "") or ""
        if yaml_lines:
            sources.append(yaml_lines)
        options = getattr(spec, "options", None) or {}
        module_options = getattr(spec, "module_options", None) or {}
        _collect_strings_from_dict(options, sources)
        _collect_strings_from_dict(module_options, sources)
        raw = getattr(getattr(task, "args", None), "raw", None)
        if isinstance(raw, str):
            sources.append(raw)
        elif isinstance(raw, dict):
            _collect_strings_from_dict(raw, sources)

        bare_vars = []
        for s in sources:
            bare_vars.extend(_find_bare_vars(s))
        bare_vars = list(dict.fromkeys(bare_vars))
        verdict = len(bare_vars) > 0
        detail = {}
        if bare_vars:
            detail["bare_vars"] = bare_vars
        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())
