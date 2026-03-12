"""Sample custom risk annotator (example/template only)."""

from __future__ import annotations

from typing import Any

from apme_engine.engine.annotators.module_annotator_base import ModuleAnnotatorResult
from apme_engine.engine.annotators.risk_annotator_base import RiskAnnotator
from apme_engine.engine.models import DefaultRiskType, RiskAnnotation, TaskCall, VariableAnnotation


class SampleCustomAnnotator(RiskAnnotator):
    name: str = "sample"
    enabled: bool = False

    # whether this task should be analyzed by this or not
    def match(self, taskcall: TaskCall) -> bool:
        # resolved_name = taskcall.resolved_name
        # return resolved_name.startswith("sample.custom.")
        return False

    # extract analyzed_data from task and embed it
    def run(self, task: TaskCall) -> ModuleAnnotatorResult:
        resolved_name = getattr(task.spec, "resolved_name", "") if task.spec else ""
        options = getattr(task.spec, "module_options", {}) if task.spec else {}
        var_annos = task.get_annotation_by_type(VariableAnnotation.type)
        var_anno = var_annos[0] if len(var_annos) > 0 else VariableAnnotation()
        resolved_options = getattr(var_anno, "resolved_module_options", [])

        annotations: list[RiskAnnotation] = []
        # example of package_install
        if resolved_name == "sample.custom.homebrew":
            res = RiskAnnotation(type=self.type, risk_type=DefaultRiskType.PACKAGE_INSTALL)
            res.data = self.homebrew(options)  # type: ignore[attr-defined]
            resolved_data: list[dict[str, Any]] = []
            for ro in resolved_options:
                resolved_data.append(self.homebrew(ro))
            res.resolved_data = resolved_data  # type: ignore[attr-defined]
            annotations.append(res)
        return ModuleAnnotatorResult(annotations=annotations)

    def homebrew(self, options: Any) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if type(options) is not dict:
            return data
        if "name" in options:
            data["pkg"] = options["name"]
        if "state" in options and options["state"] == "absent":
            data["delete"] = True
        return data
