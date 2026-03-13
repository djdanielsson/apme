"""Base classes for module-level risk annotators."""

from dataclasses import dataclass

from apme_engine.engine.annotators.annotator_base import Annotator, AnnotatorResult
from apme_engine.engine.models import TaskCall


class ModuleAnnotator(Annotator):
    """Base class for annotators that analyze a specific Ansible module's task call.

    Attributes:
        type: Annotator type identifier.
        fqcn: Fully qualified module name to be annotated.

    """

    type: str = "module_annotation"
    fqcn: str = "<module FQCN to be annotated by this>"

    def run(self, task: TaskCall) -> AnnotatorResult:
        """Analyze a task and return annotations. Override in subclasses.

        Args:
            task: The task call to analyze.

        Returns:
            Annotations for the task.

        Raises:
            ValueError: When called on base class (override required).

        """
        raise ValueError("this is a base class method")


@dataclass
class ModuleAnnotatorResult(AnnotatorResult):
    """Result container for module annotator output."""

    pass
