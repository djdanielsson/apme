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

URL_PATTERN = re.compile(r"^https?://\S+$")


@dataclass
class MetaVideoLinksRule(Rule):
    rule_id: str = "L055"
    description: str = "Role meta video_links should be valid URLs"
    enabled: bool = True
    name: str = "MetaVideoLinks"
    version: str = "v0.0.1"
    severity: str = Severity.VERY_LOW
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
        video_links = galaxy_info.get("video_links") if galaxy_info else None
        if not video_links:
            return RuleResult(verdict=False, file=role.file_info(), rule=self.get_metadata())
        if not isinstance(video_links, list):
            return RuleResult(
                verdict=True,
                detail={"message": "video_links must be a list"},
                file=role.file_info(),
                rule=self.get_metadata(),
            )
        invalid = [u for u in video_links if not (isinstance(u, str) and URL_PATTERN.match(u.strip()))]
        verdict = len(invalid) > 0
        detail = {}
        if invalid:
            detail["invalid_links"] = invalid[:10]
        return RuleResult(verdict=verdict, detail=detail, file=role.file_info(), rule=self.get_metadata())
