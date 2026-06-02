"""Disk I/O helpers for saving scan artifacts (definitions)."""

from __future__ import annotations

import os
from pathlib import Path

import jsonpickle


def save_definitions(definitions: dict[str, object], out_dir: str) -> None:
    """Save definition objects to objects.json in out_dir.

    Args:
        definitions: Dict with definitions key containing serializable objects.
        out_dir: Output directory path.

    Raises:
        ValueError: If out_dir is empty.
    """
    if out_dir == "":
        raise ValueError("output dir must be a non-empty value")

    if not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    objects_json_str = jsonpickle.encode(definitions["definitions"], make_refs=False)
    fpath = os.path.join(out_dir, "objects.json")
    Path(fpath).write_text(objects_json_str)
