"""Annotator for the ansible.builtin.subversion module."""

from apme_engine.engine.annotators.module_annotator_base import ModuleAnnotator, ModuleAnnotatorResult
from apme_engine.engine.models import DefaultRiskType, InboundTransferDetail, RiskAnnotation, TaskCall


class SubversionAnnotator(ModuleAnnotator):
    """Annotates subversion tasks with inbound transfer risk details.

    Attributes:
        fqcn: Fully qualified module name.
        enabled: Whether this annotator is active.

    """

    fqcn: str = "ansible.builtin.subversion"
    enabled: bool = True

    def run(self, task: TaskCall) -> ModuleAnnotatorResult:
        """Extract inbound transfer risk from subversion task arguments.

        Args:
            task: The task call to analyze.

        Returns:
            Result with inbound transfer risk annotations.

        """
        src = task.args.get("repo")
        dest = task.args.get("dest")
        annotation = RiskAnnotation.init(
            risk_type=DefaultRiskType.INBOUND, detail=InboundTransferDetail(_src_arg=src, _dest_arg=dest)
        )
        return ModuleAnnotatorResult(annotations=[annotation])
