"""Annotator for the ansible.builtin.assemble module."""

from apme_engine.engine.annotators.module_annotator_base import ModuleAnnotator, ModuleAnnotatorResult
from apme_engine.engine.models import DefaultRiskType, FileChangeDetail, RiskAnnotation, TaskCall


class AssembleAnnotator(ModuleAnnotator):
    """Annotates assemble tasks with file change risk details.

    Attributes:
        fqcn: Fully qualified module name.
        enabled: Whether this annotator is active.

    """

    fqcn: str = "ansible.builtin.assemble"
    enabled: bool = True

    def run(self, task: TaskCall) -> ModuleAnnotatorResult:
        """Extract file change risk from assemble task arguments.

        Args:
            task: The task call to analyze.

        Returns:
            Result with file change risk annotations.

        """
        path = task.args.get("dest")
        src = task.args.get("src")
        unsafe_writes = task.args.get("unsafe_writes")

        annotation = RiskAnnotation.init(
            risk_type=DefaultRiskType.FILE_CHANGE,
            detail=FileChangeDetail(_path_arg=path, _src_arg=src, _unsafe_write_arg=unsafe_writes),
        )
        return ModuleAnnotatorResult(annotations=[annotation])
