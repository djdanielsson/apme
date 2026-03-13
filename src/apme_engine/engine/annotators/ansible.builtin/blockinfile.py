"""Annotator for the ansible.builtin.blockinfile module."""

from apme_engine.engine.annotators.module_annotator_base import ModuleAnnotator, ModuleAnnotatorResult
from apme_engine.engine.models import DefaultRiskType, FileChangeDetail, RiskAnnotation, TaskCall


class BlockinfileAnnotator(ModuleAnnotator):
    """Annotates blockinfile tasks with file change risk details.

    Attributes:
        fqcn: Fully qualified module name.
        enabled: Whether this annotator is active.

    """

    fqcn: str = "ansible.builtin.blockinfile"
    enabled: bool = True

    def run(self, task: TaskCall) -> ModuleAnnotatorResult:
        """Extract file change risk from blockinfile task arguments.

        Args:
            task: The task call to analyze.

        Returns:
            Result with file change risk annotations.

        """
        path = task.args.get("path")
        unsafe_writes = task.args.get("unsafe_writes")
        state = task.args.get("state")

        annotation = RiskAnnotation.init(
            risk_type=DefaultRiskType.FILE_CHANGE,
            detail=FileChangeDetail(_path_arg=path, _state_arg=state, _unsafe_write_arg=unsafe_writes),
        )
        return ModuleAnnotatorResult(annotations=[annotation])
