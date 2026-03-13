"""Annotator for the ansible.builtin.file module."""

from apme_engine.engine.annotators.module_annotator_base import ModuleAnnotator, ModuleAnnotatorResult
from apme_engine.engine.models import DefaultRiskType, FileChangeDetail, RiskAnnotation, TaskCall


class FileAnnotator(ModuleAnnotator):
    """Annotates file tasks with file change risk details.

    Attributes:
        fqcn: Fully qualified module name.
        enabled: Whether this annotator is active.

    """

    fqcn: str = "ansible.builtin.file"
    enabled: bool = True

    def run(self, task: TaskCall) -> ModuleAnnotatorResult:
        """Extract file change risk from file task arguments.

        Args:
            task: The task call to analyze.

        Returns:
            Result with file change risk annotations.

        """
        path = task.args.get("path")
        mode = task.args.get("mode")
        unsafe_writes = task.args.get("unsafe_writes")
        state = task.args.get("state")

        annotation = RiskAnnotation.init(
            risk_type=DefaultRiskType.FILE_CHANGE,
            detail=FileChangeDetail(_path_arg=path, _state_arg=state, _mode_arg=mode, _unsafe_write_arg=unsafe_writes),
        )
        return ModuleAnnotatorResult(annotations=[annotation])
