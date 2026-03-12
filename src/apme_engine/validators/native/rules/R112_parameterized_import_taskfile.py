from dataclasses import dataclass

from apme_engine.engine.models import (
    AnsibleRunContext,
    Rule,
    RuleResult,
    RunTargetType,
    Severity,
    TaskCall,
)
from apme_engine.engine.models import (
    ExecutableType as ActionType,
)
from apme_engine.engine.models import RuleTag as Tag


@dataclass
class ParameterizedImportTaskfileRule(Rule):
    rule_id: str = "R112"
    description: str = "Import/include a parameterized name of taskfile"
    enabled: bool = True
    name: str = "ParameterizedImportTaskfile"
    version: str = "v0.0.1"
    severity: str = Severity.MEDIUM
    tags: tuple[str, ...] = (Tag.DEPENDENCY,)

    def match(self, ctx: AnsibleRunContext) -> bool:
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        task = ctx.current
        if task is None or not isinstance(task, TaskCall):
            return None

        # import_tasks: xxx.yml
        #   or
        # import_tasks:
        #   file: yyy.yml

        taskfile_ref_arg = task.args.get("file")
        if not taskfile_ref_arg:
            taskfile_ref_arg = task.args

        verdict = bool(
            task.action_type == ActionType.TASKFILE_TYPE
            and taskfile_ref_arg is not None
            and taskfile_ref_arg.is_mutable
        )
        taskfile_ref = taskfile_ref_arg.raw if taskfile_ref_arg else None
        detail = {
            "taskfile": taskfile_ref,
        }

        return RuleResult(verdict=verdict, detail=detail, file=task.file_info(), rule=self.get_metadata())
