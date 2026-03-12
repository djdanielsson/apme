"""Stub for generated common_pb2 (proto types)."""

from typing import Any

class Violation:
    rule_id: str
    level: str
    message: str
    file: str
    path: str
    line: int
    line_range: LineRange
    def __init__(self, **kwargs: Any) -> None: ...
    def HasField(self, name: str) -> bool: ...
    def CopyFrom(self, other: Any) -> None: ...

class LineRange:
    start: int
    end: int
    def __init__(self, **kwargs: Any) -> None: ...
    def CopyFrom(self, other: Any) -> None: ...

class File:
    path: str
    content: bytes
    def __init__(self, *, path: str = "", content: bytes = b"", **kwargs: Any) -> None: ...

class HealthRequest:
    def __init__(self) -> None: ...

class HealthResponse:
    status: str
    def __init__(self, *, status: str = "", **kwargs: Any) -> None: ...

class RuleTiming:
    rule_id: str
    elapsed_ms: float
    violations: int
    def __init__(self, *, rule_id: str = "", elapsed_ms: float = 0.0, violations: int = 0, **kwargs: Any) -> None: ...

class ValidatorDiagnostics:
    validator_name: str
    request_id: str
    total_ms: float
    files_received: int
    violations_found: int
    rule_timings: list[RuleTiming]
    metadata: dict[str, str]
    def __init__(self, **kwargs: Any) -> None: ...
