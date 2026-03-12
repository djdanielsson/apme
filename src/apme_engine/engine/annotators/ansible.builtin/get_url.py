from apme_engine.engine.annotators.module_annotator_base import ModuleAnnotator, ModuleAnnotatorResult
from apme_engine.engine.models import DefaultRiskType, InboundTransferDetail, RiskAnnotation, TaskCall


class GetURLAnnotator(ModuleAnnotator):
    fqcn: str = "ansible.builtin.get_url"
    enabled: bool = True

    def run(self, task: TaskCall) -> ModuleAnnotatorResult:
        src = task.args.get("url")
        dest = task.args.get("dest")

        annotation = RiskAnnotation.init(
            risk_type=DefaultRiskType.INBOUND, detail=InboundTransferDetail(_src_arg=src, _dest_arg=dest)
        )
        return ModuleAnnotatorResult(annotations=[annotation])
