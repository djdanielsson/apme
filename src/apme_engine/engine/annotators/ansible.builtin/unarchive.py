import contextlib

from apme_engine.engine.annotators.module_annotator_base import ModuleAnnotator, ModuleAnnotatorResult
from apme_engine.engine.models import DefaultRiskType, InboundTransferDetail, RiskAnnotation, TaskCall
from apme_engine.engine.utils import parse_bool


class UnarchiveAnnotator(ModuleAnnotator):
    fqcn: str = "ansible.builtin.unarchive"
    enabled: bool = True

    def run(self, task: TaskCall) -> ModuleAnnotatorResult:
        src = task.args.get("src")  # required
        dest = task.args.get("dest")  # required
        remote_src = task.args.get("remote_src")

        is_remote_src = False
        if remote_src is not None:
            raw_val = getattr(remote_src, "raw", None)
            if isinstance(raw_val, (str, bool)):
                with contextlib.suppress(Exception):
                    is_remote_src = parse_bool(raw_val)
            templated_val = getattr(remote_src, "templated", None)
            if not is_remote_src and isinstance(templated_val, (str, bool)):
                with contextlib.suppress(Exception):
                    is_remote_src = parse_bool(templated_val)

        url_sep = "://"
        is_download = False
        if src is not None and is_remote_src:
            src_raw = getattr(src, "raw", "") or ""
            src_templated = getattr(src, "templated", "") or ""
            if url_sep in str(src_raw) or url_sep in str(src_templated):
                is_download = True

        if not is_download:
            return ModuleAnnotatorResult(annotations=[])

        annotation = RiskAnnotation.init(
            risk_type=DefaultRiskType.INBOUND, detail=InboundTransferDetail(_src_arg=src, _dest_arg=dest)
        )
        return ModuleAnnotatorResult(annotations=[annotation])
