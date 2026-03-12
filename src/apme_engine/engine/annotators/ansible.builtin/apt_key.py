from apme_engine.engine.annotators.module_annotator_base import ModuleAnnotator, ModuleAnnotatorResult
from apme_engine.engine.models import DefaultRiskType, KeyConfigChangeDetail, RiskAnnotation, TaskCall


class AptKeyAnnotator(ModuleAnnotator):
    fqcn: str = "ansible.builtin.apt_key"
    enabled: bool = True

    def run(self, task: TaskCall) -> ModuleAnnotatorResult:
        # id = task.args.get("id")
        key = None
        if key is None:
            key = task.args.get("url")
        if key is None:
            key = task.args.get("data")
        if key is None:
            key = task.args.get("keyserver")

        state = task.args.get("state")

        annotation = RiskAnnotation.init(
            risk_type=DefaultRiskType.CONFIG_CHANGE, detail=KeyConfigChangeDetail(_key_arg=key, _state_arg=state)
        )
        return ModuleAnnotatorResult(annotations=[annotation])
