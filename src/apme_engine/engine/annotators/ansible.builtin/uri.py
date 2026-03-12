from apme_engine.engine.annotators.module_annotator_base import ModuleAnnotator, ModuleAnnotatorResult
from apme_engine.engine.models import DefaultRiskType, OutboundTransferDetail, RiskAnnotation, TaskCall


class URIAnnotator(ModuleAnnotator):
    fqcn: str = "ansible.builtin.uri"
    enabled: bool = True

    def run(self, task: TaskCall) -> ModuleAnnotatorResult:
        method_val = task.args.get("method")
        method = getattr(method_val, "raw", method_val) if method_val is not None else None
        method_str = str(method) if method is not None else ""

        annotations = []
        if method_str in ["PUT", "POST", "PATCH"]:
            url = task.args.get("url")
            body = task.args.get("body")
            annotation = RiskAnnotation.init(
                risk_type=DefaultRiskType.OUTBOUND,
                detail=OutboundTransferDetail(_dest_arg=url, _src_arg=body),
            )
            annotations.append(annotation)
        return ModuleAnnotatorResult(annotations=annotations)
