"""Annotator for the ansible.builtin.pip module."""

from apme_engine.engine.annotators.module_annotator_base import ModuleAnnotator, ModuleAnnotatorResult
from apme_engine.engine.models import DefaultRiskType, PackageInstallDetail, RiskAnnotation, TaskCall


class PipAnnotator(ModuleAnnotator):
    """Annotates pip tasks with package install risk details.

    Attributes:
        fqcn: Fully qualified module name.
        enabled: Whether this annotator is active.

    """

    fqcn: str = "ansible.builtin.pip"
    enabled: bool = True

    def run(self, task: TaskCall) -> ModuleAnnotatorResult:
        """Extract package install risk from pip task arguments.

        Args:
            task: The task call to analyze.

        Returns:
            Result with package install risk annotations.

        """
        pkg = task.args.get("name")
        if pkg is None:
            pkg = task.args.get("requirements")

        annotation = RiskAnnotation.init(
            risk_type=DefaultRiskType.PACKAGE_INSTALL, detail=PackageInstallDetail(_pkg_arg=pkg)
        )
        return ModuleAnnotatorResult(annotations=[annotation])
