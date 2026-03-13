"""Annotator for the ansible.builtin.get_url module."""

from apme_engine.engine.annotators.module_annotator_base import ModuleAnnotator, ModuleAnnotatorResult
from apme_engine.engine.models import DefaultRiskType, InboundTransferDetail, RiskAnnotation, TaskCall


class GetURLAnnotator(ModuleAnnotator):
    """Annotates get_url tasks with inbound transfer risk details.

    Attributes:
        fqcn: Fully qualified module name.
        enabled: Whether this annotator is active.

    """

    fqcn: str = "ansible.builtin.get_url"
    enabled: bool = True

    def run(self, task: TaskCall) -> ModuleAnnotatorResult:
        """Extract inbound transfer risk from get_url task arguments.

        Args:
            task: The task call to analyze.

        Returns:
            Result with inbound transfer risk annotations.

        """
        src = task.args.get("url")
        dest = task.args.get("dest")

        annotation = RiskAnnotation.init(
            risk_type=DefaultRiskType.INBOUND, detail=InboundTransferDetail(_src_arg=src, _dest_arg=dest)
        )
        return ModuleAnnotatorResult(annotations=[annotation])
