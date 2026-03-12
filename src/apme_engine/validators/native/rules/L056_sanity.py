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

# Paths that are commonly ignored by ansible-lint / sanity (e.g. .git, files in certain dirs)
SANITY_IGNORE_PATTERNS = [
    re.compile(r"\.git/"),
    re.compile(r"/\.ansible/"),
    re.compile(r"\.pyc$"),
    re.compile(r"__pycache__"),
]


@dataclass
class SanityRule(Rule):
    rule_id: str = "L056"
    description: str = "File may be in a path that should be excluded from lint/sanity"
    enabled: bool = True
    name: str = "Sanity"
    version: str = "v0.0.1"
    severity: str = Severity.VERY_LOW
    tags: tuple[str, ...] = (Tag.QUALITY,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        return bool(ctx.current is not None and ctx.current.type in (RunTargetType.Task, RunTargetType.Role))

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        target = ctx.current
        if target is None:
            return None
        defined_in = getattr(target.spec, "defined_in", "") or ""
        verdict = any(p.search(defined_in) for p in SANITY_IGNORE_PATTERNS)
        detail = {}
        if verdict:
            detail["path"] = defined_in
            detail["message"] = "path matches common ignore pattern; consider excluding from scan"
        return RuleResult(verdict=verdict, detail=detail, file=target.file_info(), rule=self.get_metadata())
