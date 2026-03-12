"""Stub for generated primary_pb2 (proto types)."""

from typing import Any

class ScanOptions:
    ansible_core_version: str
    collection_specs: list[str]
    def __init__(self, **kwargs: Any) -> None: ...

class ScanRequest:
    def __init__(self, **kwargs: Any) -> None: ...

class ScanResponse:
    def __init__(self, **kwargs: Any) -> None: ...

class ScanDiagnostics:
    engine_parse_ms: float
    engine_annotate_ms: float
    engine_total_ms: float
    files_scanned: int
    trees_built: int
    total_violations: int
    validators: list[Any]
    fan_out_ms: float
    total_ms: float
    def __init__(self, **kwargs: Any) -> None: ...

class FormatRequest:
    def __init__(self, **kwargs: Any) -> None: ...

class FormatResponse:
    def __init__(self, **kwargs: Any) -> None: ...

class FileDiff:
    def __init__(self, **kwargs: Any) -> None: ...
