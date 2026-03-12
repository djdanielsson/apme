from apme_engine.engine.annotators.module_annotator_base import ModuleAnnotator, ModuleAnnotatorResult
from apme_engine.engine.models import DefaultRiskType, KeyConfigChangeDetail, RiskAnnotation, TaskCall


class RpmKeyAnnotator(ModuleAnnotator):
    fqcn: str = "ansible.builtin.rpm_key"
    enabled: bool = True

    def run(self, task: TaskCall) -> ModuleAnnotatorResult:
        key = task.args.get("key")
        state = task.args.get("state")

        annotation = RiskAnnotation.init(
            risk_type=DefaultRiskType.CONFIG_CHANGE, detail=KeyConfigChangeDetail(_key_arg=key, _state_arg=state)
        )
        return ModuleAnnotatorResult(annotations=[annotation])
