from apme_engine.engine.annotators.module_annotator_base import ModuleAnnotator, ModuleAnnotatorResult
from apme_engine.engine.models import DefaultRiskType, PackageInstallDetail, RiskAnnotation, TaskCall


class AptAnnotator(ModuleAnnotator):
    fqcn: str = "ansible.builtin.apt"
    enabled: bool = True

    def run(self, task: TaskCall) -> ModuleAnnotatorResult:
        pkg = task.args.get("name")
        if pkg is None:
            pkg = task.args.get("pkg")
        if pkg is None:
            pkg = task.args.get("deb")

        annotation = RiskAnnotation.init(
            risk_type=DefaultRiskType.PACKAGE_INSTALL, detail=PackageInstallDetail(_pkg_arg=pkg)
        )
        return ModuleAnnotatorResult(annotations=[annotation])
