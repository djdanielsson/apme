"""Sample custom risk annotator (example/template only)."""

from __future__ import annotations

from typing import cast

from apme_engine.engine.annotators.module_annotator_base import ModuleAnnotatorResult
from apme_engine.engine.annotators.risk_annotator_base import RiskAnnotator
from apme_engine.engine.models import DefaultRiskType, RiskAnnotation, TaskCall, VariableAnnotation, YAMLDict


class SampleCustomAnnotator(RiskAnnotator):
    """Example risk annotator for custom modules (template only, disabled by default).

    Attributes:
        name: Annotator name identifier.
        enabled: Whether this annotator is active.

    """

    name: str = "sample"
    enabled: bool = False

    def match(self, taskcall: TaskCall) -> bool:
        """Return True if the task should be analyzed by this annotator.

        Args:
            taskcall: The task call to check.

        Returns:
            True if the task should be analyzed.

        """
        # resolved_name = taskcall.resolved_name
        # return resolved_name.startswith("sample.custom.")
        return False

    def run(self, task: TaskCall) -> ModuleAnnotatorResult:
        """Extract risk annotations from the task and return aggregated results.

        Args:
            task: The task call to analyze.

        Returns:
            Aggregated risk annotations for the task.

        """
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
            resolved_data: list[dict[str, object]] = []
            for ro in resolved_options:
                resolved_data.append(cast(dict[str, object], self.homebrew(ro)))
            res.resolved_data = resolved_data  # type: ignore[attr-defined]
            annotations.append(res)
        return ModuleAnnotatorResult(annotations=annotations)

    def homebrew(self, options: YAMLDict) -> YAMLDict:
        """Extract package install details from homebrew module options.

        Args:
            options: Module options dict from the task.

        Returns:
            Dict with package install details (pkg, delete).

        """
        data: YAMLDict = {}
        if type(options) is not dict:
            return data
        if "name" in options:
            data["pkg"] = options["name"]
        if "state" in options and options["state"] == "absent":
            data["delete"] = True
        return data
