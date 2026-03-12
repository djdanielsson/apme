from dataclasses import dataclass

from apme_engine.engine.models import (
    AnsibleRunContext,
    RoleCall,
    Rule,
    RuleResult,
    RunTargetType,
    Severity,
)
from apme_engine.engine.models import RuleTag as Tag


@dataclass
class ExternalRoleRuleResult(RuleResult):
    pass


@dataclass
class ExternalRoleRule(Rule):
    rule_id: str = "R117"
    description: str = "An external role is used"
    enabled: bool = True
    name: str = "ExternalRole"
    version: str = "v0.0.1"
    severity: str = Severity.VERY_LOW
    tags: tuple[str, ...] = (Tag.DEPENDENCY,)
    result_type: type[RuleResult] = ExternalRoleRuleResult

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Role)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        role = ctx.current
        if role is None:
            return None

        spec_metadata = getattr(role.spec, "metadata", None)
        verdict = bool(
            not ctx.is_begin(role)
            and isinstance(role, RoleCall)
            and spec_metadata
            and isinstance(spec_metadata, dict)
            and spec_metadata.get("galaxy_info", None)
        )

        return RuleResult(verdict=verdict, file=role.file_info(), rule=self.get_metadata())
