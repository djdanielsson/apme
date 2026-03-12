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


@dataclass
class RoleWithoutMetadataRule(Rule):
    rule_id: str = "L027"
    description: str = "A role without metadata is used"
    enabled: bool = True
    name: str = "RoleWithoutMetadata"
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

        verdict = not getattr(role.spec, "metadata", None)

        return RuleResult(verdict=verdict, file=role.file_info(), rule=self.get_metadata())
