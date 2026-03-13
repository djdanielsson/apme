"""Annotator for the ansible.builtin.rpm_key module."""

from apme_engine.engine.annotators.module_annotator_base import ModuleAnnotator, ModuleAnnotatorResult
from apme_engine.engine.models import DefaultRiskType, KeyConfigChangeDetail, RiskAnnotation, TaskCall


class RpmKeyAnnotator(ModuleAnnotator):
    """Annotates rpm_key tasks with key config change risk details.

    Attributes:
        fqcn: Fully qualified module name.
        enabled: Whether this annotator is active.

    """

    fqcn: str = "ansible.builtin.rpm_key"
    enabled: bool = True

    def run(self, task: TaskCall) -> ModuleAnnotatorResult:
        """Extract key config change risk from rpm_key task arguments.

        Args:
            task: The task call to analyze.

        Returns:
            Result with key config change risk annotations.

        """
        key = task.args.get("key")
        state = task.args.get("state")

        annotation = RiskAnnotation.init(
            risk_type=DefaultRiskType.CONFIG_CHANGE, detail=KeyConfigChangeDetail(_key_arg=key, _state_arg=state)
        )
        return ModuleAnnotatorResult(annotations=[annotation])
