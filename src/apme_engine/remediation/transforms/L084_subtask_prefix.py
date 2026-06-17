"""L084: Add filename-based prefix to task names in included role files."""

from __future__ import annotations

import os

from ruamel.yaml.comments import CommentedMap

from apme_engine.engine.models import ViolationDict


def fix_subtask_prefix(task: CommentedMap, violation: ViolationDict) -> bool:
    """Prefix a task name with the filename stem (e.g. ``install | Do thing``).

    Uses the violation's ``file`` field to derive the stem of the YAML
    file (e.g. ``validate_credentials.yml`` -> ``validate_credentials``).

    Args:
        task: Task CommentedMap to modify in-place.
        violation: Violation dict with ``file`` containing the source path.

    Returns:
        True if a change was applied.
    """
    name = task.get("name")
    if not isinstance(name, str) or not name:
        return False

    file_path = str(violation.get("file") or "")
    if not file_path:
        return False

    stem = os.path.splitext(os.path.basename(file_path))[0]
    if not stem or stem in ("main",):
        return False

    if "|" in name:
        prefix = name.split("|", 1)[0].strip()
        if prefix.lower() == stem.lower():
            return False
        description = name.split("|", 1)[1].strip()
        task["name"] = f"{stem} | {description}"
    else:
        task["name"] = f"{stem} | {name}"
    return True
