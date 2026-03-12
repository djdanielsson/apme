from apme_engine.engine.annotators.module_annotator_base import ModuleAnnotatorResult
from apme_engine.engine.annotators.risk_annotator_base import RiskAnnotator
from apme_engine.engine.models import TaskCall


class AnsibleBuiltinRiskAnnotator(RiskAnnotator):
    name: str = "ansible.builtin"
    enabled: bool = True

    def match(self, task: TaskCall) -> bool:
        resolved_name = getattr(task.spec, "resolved_name", "") if task.spec else ""
        return bool(resolved_name and str(resolved_name).startswith("ansible.builtin."))

    # embed "analyzed_data" field in Task
    def run(self, task: TaskCall) -> ModuleAnnotatorResult:
        if not self.match(task):
            return ModuleAnnotatorResult(annotations=[])

        return self.run_module_annotators("ansible.builtin", task)
