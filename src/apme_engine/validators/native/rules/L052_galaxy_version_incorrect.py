# L052: Galaxy version in meta should follow semantic version format

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

GALAXY_VERSION_PATTERN = re.compile(r"^\d+\.\d+(\.\d+)?$")


@dataclass
class GalaxyVersionIncorrectRule(Rule):
    rule_id: str = "L052"
    description: str = "Galaxy version in meta should follow semantic version format (x.y.z)"
    enabled: bool = True
    name: str = "GalaxyVersionIncorrect"
    version: str = "v0.0.1"
    severity: str = Severity.LOW
    tags: tuple[str, ...] = (Tag.DEPENDENCY,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Role)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        role = ctx.current
        if role is None:
            return None
        metadata = getattr(role.spec, "metadata", None) or {}
        gi = metadata.get("galaxy_info")
        galaxy_info = gi if isinstance(gi, dict) else {}
        version = galaxy_info.get("version") if galaxy_info else None
        if version is None:
            return RuleResult(verdict=False, file=role.file_info(), rule=self.get_metadata())
        vs = str(version).strip()
        verdict = not bool(GALAXY_VERSION_PATTERN.match(vs))
        detail = {}
        if verdict:
            detail["version"] = vs
            detail["message"] = "galaxy version should be semantic (e.g. 1.0.0)"
        return RuleResult(verdict=verdict, detail=detail, file=role.file_info(), rule=self.get_metadata())
