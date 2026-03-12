from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from apme_engine.engine.models import Annotation, AnsibleRunContext, TaskCall


class Annotator:
    type: str = ""
    context: AnsibleRunContext | Any | None = None

    def __init__(self, context: AnsibleRunContext | Any | None = None) -> None:
        if context is not None:
            self.context = context

    def run(self, task: TaskCall) -> Any:
        raise ValueError("this is a base class method")


@dataclass
class AnnotatorResult:
    annotations: Sequence[Annotation] | None = field(default=None)
    data: Any = None

    def print(self) -> None:
        raise ValueError("this is a base class method")

    def to_json(self) -> Any:
        raise ValueError("this is a base class method")

    def error(self) -> None:
        raise ValueError("this is a base class method")
