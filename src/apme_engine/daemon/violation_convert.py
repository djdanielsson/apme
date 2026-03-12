"""Convert between dict violations (validator output) and proto Violation."""

from typing import Any

from apme.v1.common_pb2 import LineRange, Violation


def violation_dict_to_proto(v: dict[str, Any]) -> Violation:
    """Build a proto Violation from a dict with rule_id, level, message, file, line, path."""
    out = Violation(
        rule_id=v.get("rule_id") or "",
        level=v.get("level") or "",
        message=v.get("message") or "",
        file=v.get("file") or "",
        path=v.get("path") or "",
    )
    line = v.get("line")
    if isinstance(line, (list, tuple)) and len(line) >= 2:
        out.line_range.CopyFrom(LineRange(start=int(line[0]), end=int(line[1])))
    elif isinstance(line, int):
        out.line = line
    return out


def violation_proto_to_dict(v: Violation) -> dict[str, Any]:
    """Build a dict violation from proto (for CLI output)."""
    line: int | list[int] | None = v.line if v.HasField("line") else None
    if v.HasField("line_range"):
        line = [v.line_range.start, v.line_range.end]
    return {
        "rule_id": v.rule_id,
        "level": v.level,
        "message": v.message,
        "file": v.file,
        "line": line,
        "path": v.path,
    }
