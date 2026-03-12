"""Stub for generated validate_pb2 (proto types)."""

from typing import Any

class ValidateRequest:
    request_id: str
    hierarchy_payload: bytes
    scandata: bytes
    files: list[Any]
    def __init__(self, **kwargs: Any) -> None: ...

class ValidateResponse:
    def __init__(self, **kwargs: Any) -> None: ...
