"""Base classes for risk annotators that delegate to module-specific annotators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from apme_engine.engine.annotators.annotator_base import Annotator, AnnotatorResult
from apme_engine.engine.annotators.module_annotator_base import ModuleAnnotator, ModuleAnnotatorResult
from apme_engine.engine.models import RiskAnnotation, TaskCall
from apme_engine.engine.utils import load_classes_in_dir


class RiskAnnotator(Annotator):
    """Base class for risk annotators that match tasks and delegate to module annotators.

    Attributes:
        type: Annotator type identifier.
        name: Annotator name identifier.
        enabled: Whether this annotator is active.
        module_annotator_cache: Cache of loaded module annotators by directory path.

    """

    type: str = RiskAnnotation.type
    name: str = ""
    enabled: bool = False

    module_annotator_cache: dict[str, list[ModuleAnnotator]] = {}

    def match(self, task: TaskCall) -> bool:
        """Return True if this annotator should analyze the given task.

        Args:
            task: The task call to check.

        Returns:
            True if this annotator should analyze the task.

        Raises:
            ValueError: When called on base class (override required).

        """
        raise ValueError("this is a base class method")

    def run(self, task: TaskCall) -> ModuleAnnotatorResult:
        """Run risk analysis on the task and return annotations.

        Args:
            task: The task call to analyze.

        Returns:
            Aggregated annotations from module annotators.

        Raises:
            ValueError: When called on base class (override required).

        """
        raise ValueError("this is a base class method")

    def load_module_annotators(self, dir_path: str) -> list[ModuleAnnotator]:
        """Load and cache module annotators from the given directory.

        Args:
            dir_path: Directory path containing module annotator modules.

        Returns:
            List of instantiated module annotators.

        """
        if dir_path in self.module_annotator_cache:
            return self.module_annotator_cache[dir_path]

        annotator_classes, _ = load_classes_in_dir(dir_path, ModuleAnnotator, __file__)
        module_annotators: list[ModuleAnnotator] = []
        for a_c in annotator_classes:
            annotator = cast(type[ModuleAnnotator], a_c)(context=self.context)
            module_annotators.append(annotator)
        if module_annotators:
            self.module_annotator_cache[dir_path] = module_annotators
        return module_annotators

    def run_module_annotators(self, dir_path: str, task: TaskCall) -> ModuleAnnotatorResult:
        """Run all matching module annotators for the task and aggregate results.

        Args:
            dir_path: Directory path for module annotator lookup.
            task: The task call to analyze.

        Returns:
            Aggregated annotations from all matching module annotators.

        """
        if not dir_path:
            return ModuleAnnotatorResult(annotations=[])

        resolved_name = getattr(task.spec, "resolved_name", "") if task.spec else ""
        module_annotators = self.load_module_annotators(dir_path)

        # TODO: need to consider annotator precedence

        annotations: list[RiskAnnotation] = []

        for annotator in module_annotators:
            if not isinstance(annotator, ModuleAnnotator):
                continue
            if not annotator.fqcn:
                continue
            if resolved_name != annotator.fqcn:
                continue

            result = annotator.run(task)
            if not result:
                continue

            if result.annotations:
                annotations.extend(result.annotations)  # type: ignore[arg-type]
        if annotations:
            return ModuleAnnotatorResult(annotations=annotations)
        return ModuleAnnotatorResult(annotations=[])


@dataclass
class RiskAnnotatorResult(AnnotatorResult):
    """Result container for risk annotator output."""

    pass
