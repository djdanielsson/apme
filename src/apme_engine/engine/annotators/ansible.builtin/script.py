"""Annotator for the ansible.builtin.script module."""

from apme_engine.engine.annotators.module_annotator_base import ModuleAnnotator, ModuleAnnotatorResult
from apme_engine.engine.models import CommandExecDetail, DefaultRiskType, RiskAnnotation, TaskCall


class ScriptAnnotator(ModuleAnnotator):
    """Annotates script tasks with command execution risk details.

    Attributes:
        fqcn: Fully qualified module name.
        enabled: Whether this annotator is active.

    """

    fqcn: str = "ansible.builtin.script"
    enabled: bool = True

    def run(self, task: TaskCall) -> ModuleAnnotatorResult:
        """Extract command execution risk from script task arguments.

        Args:
            task: The task call to analyze.

        Returns:
            Result with command execution risk annotations.

        """
        cmd = task.args.get("")
        if cmd is None:
            cmd = task.args.get("cmd")
        if cmd is None:
            cmd = task.args.get("argv")

        annotation = RiskAnnotation.init(
            risk_type=DefaultRiskType.CMD_EXEC,
            detail=CommandExecDetail(command=cmd),
        )
        return ModuleAnnotatorResult(annotations=[annotation])
