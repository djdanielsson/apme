from dataclasses import dataclass

from apme_engine.engine.models import (
    AnsibleRunContext,
    Rule,
    RuleResult,
    RunTargetType,
    Severity,
    TaskCall,
    VariableDict,
)
from apme_engine.engine.models import RuleTag as Tag


@dataclass
class ShowVariablesRule(Rule):
    rule_id: str = "R404"
    description: str = "Show all variables"
    enabled: bool = False
    name: str = "ShowVariables"
    version: str = "v0.0.1"
    severity: str = Severity.NONE
    tags: tuple[str, ...] = (Tag.VARIABLE,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        task = ctx.current
        if task is None:
            return None

        verdict = True
        variables: dict[str, object] = {}
        if isinstance(task, TaskCall):
            variables = task.variable_set
        detail: dict[str, object] = {"variables": variables}

        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())

    def print(self, result: RuleResult) -> str:
        variables = result.detail.get("variables") if result.detail is not None else None
        var_table: str = "None"
        if variables:
            var_table = "\n" + VariableDict.print_table(variables)
        output = f"ruleID={self.rule_id}, \
            severity={self.severity}, \
            description={self.description}, \
            verdict={result.verdict}, \
            file={result.file}, \
            variables={var_table}\n"
        return output
