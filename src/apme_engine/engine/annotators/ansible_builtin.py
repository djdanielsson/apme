"""Risk annotator for ansible.builtin modules."""

from apme_engine.engine.annotators.module_annotator_base import ModuleAnnotatorResult
from apme_engine.engine.annotators.risk_annotator_base import RiskAnnotator
from apme_engine.engine.models import TaskCall


class AnsibleBuiltinRiskAnnotator(RiskAnnotator):
    """Risk annotator that delegates to module-specific annotators for ansible.builtin.*.

    Attributes:
        name: Annotator name identifier.
        enabled: Whether this annotator is active.

    """

    name: str = "ansible.builtin"
    enabled: bool = True

    def match(self, task: TaskCall) -> bool:
        """Return True if the task uses an ansible.builtin module.

        Args:
            task: The task call to check.

        Returns:
            True if the task uses an ansible.builtin module.

        """
        resolved_name = getattr(task.spec, "resolved_name", "") if task.spec else ""
        return bool(resolved_name and str(resolved_name).startswith("ansible.builtin."))

    def run(self, task: TaskCall) -> ModuleAnnotatorResult:
        """Run module annotators for ansible.builtin tasks and return aggregated annotations.

        Args:
            task: The task call to analyze.

        Returns:
            Aggregated annotations from matching module annotators.

        """
        if not self.match(task):
            return ModuleAnnotatorResult(annotations=[])

        return self.run_module_annotators("ansible.builtin", task)
