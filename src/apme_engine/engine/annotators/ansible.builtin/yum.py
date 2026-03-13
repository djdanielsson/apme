"""Annotator for the ansible.builtin.yum module."""

from apme_engine.engine.annotators.module_annotator_base import ModuleAnnotator, ModuleAnnotatorResult
from apme_engine.engine.models import DefaultRiskType, PackageInstallDetail, RiskAnnotation, TaskCall


class YumAnnotator(ModuleAnnotator):
    """Annotates yum tasks with package install risk details.

    Attributes:
        fqcn: Fully qualified module name.
        enabled: Whether this annotator is active.

    """

    fqcn: str = "ansible.builtin.yum"
    enabled: bool = True

    def run(self, task: TaskCall) -> ModuleAnnotatorResult:
        """Extract package install risk from yum task arguments.

        Args:
            task: The task call to analyze.

        Returns:
            Result with package install risk annotations.

        """
        pkg = task.args.get("name")
        allow_downgrade = task.args.get("allow_downgrade")
        validate_certs = task.args.get("validate_certs")

        annotation = RiskAnnotation.init(
            risk_type=DefaultRiskType.PACKAGE_INSTALL,
            detail=PackageInstallDetail(
                _pkg_arg=pkg, _validate_certs_arg=validate_certs, _allow_downgrade_arg=allow_downgrade
            ),
        )
        return ModuleAnnotatorResult(annotations=[annotation])
