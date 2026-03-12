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
class NoTabsRule(Rule):
    rule_id: str = "L040"
    description: str = "YAML should not contain tabs; use spaces"
    enabled: bool = True
    name: str = "NoTabs"
    version: str = "v0.0.1"
    severity: str = Severity.VERY_LOW
    tags: tuple[str, ...] = (Tag.DEPENDENCY,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        task = ctx.current
        if task is None:
            return None
        yaml_lines = getattr(task.spec, "yaml_lines", "") or ""
        lines_with_tabs = []
        for i, line in enumerate(yaml_lines.splitlines(), start=1):
            if "\t" in line:
                lines_with_tabs.append(i)
        verdict = len(lines_with_tabs) > 0
        detail = {}
        if lines_with_tabs:
            detail["lines_with_tabs"] = lines_with_tabs
        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())
