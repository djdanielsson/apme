from dataclasses import dataclass

from apme_engine.engine.models import (
    AnsibleRunContext,
    Rule,
    RuleResult,
    RunTargetType,
    Severity,
)
from apme_engine.engine.models import (
    ExecutableType as ActionType,
)
from apme_engine.engine.models import (
    RuleTag as Tag,
)


@dataclass
class UseShellRule(Rule):
    rule_id: str = "L029"
    description: str = "Use 'command' module instead of 'shell' "
    enabled: bool = True
    name: str = "UseShellRule"
    version: str = "v0.0.1"
    severity: str = Severity.VERY_LOW
    tags: tuple[str, ...] = (Tag.COMMAND,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        task = ctx.current
        if task is None:
            return None

        # define a condition for this rule here
        action_type = getattr(task, "action_type", "")
        spec_action = getattr(task.spec, "action", None)
        resolved_action = getattr(task, "resolved_action", "")
        verdict = bool(
            action_type == ActionType.MODULE_TYPE
            and spec_action
            and resolved_action
            and resolved_action == "ansible.builtin.shell"
        )

        return RuleResult(verdict=verdict, file=task.file_info(), rule=self.get_metadata())
