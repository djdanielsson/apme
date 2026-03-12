from apme_engine.engine.annotators.module_annotator_base import ModuleAnnotator, ModuleAnnotatorResult
from apme_engine.engine.models import DefaultRiskType, FileChangeDetail, RiskAnnotation, TaskCall


class TemplateAnnotator(ModuleAnnotator):
    fqcn: str = "ansible.builtin.template"
    enabled: bool = True

    def run(self, task: TaskCall) -> ModuleAnnotatorResult:
        path = task.args.get("dest")
        src = task.args.get("src")
        mode = task.args.get("mode")
        unsafe_writes = task.args.get("unsafe_writes")

        annotation = RiskAnnotation.init(
            risk_type=DefaultRiskType.FILE_CHANGE,
            detail=FileChangeDetail(_path_arg=path, _src_arg=src, _mode_arg=mode, _unsafe_write_arg=unsafe_writes),
        )
        return ModuleAnnotatorResult(annotations=[annotation])
