"""YAML formatter for Ansible content.

Phase 1 of the remediation pipeline: normalize YAML formatting so that
subsequent semantic fixes (modernize) produce clean, minimal diffs.

Uses FormattedYAML (ruamel.yaml round-trip) for comment-preserving
load/dump, plus targeted transforms for tab removal, key reordering,
and jinja spacing normalization.
"""

from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from apme_engine.engine.yaml_utils import FormattedYAML

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".tox", "htmlcov", ".eggs"}
YAML_EXTENSIONS = {".yml", ".yaml"}

JINJA_NORMALIZE_RE = re.compile(r"\{\{(\s*)(.*?)(\s*)\}\}")

TASK_KEY_ORDER = [
    "name",
    "block", "rescue", "always",
    "when", "changed_when", "failed_when",
    "loop", "loop_control",
    "with_items", "with_dict", "with_fileglob", "with_subelements",
    "with_sequence", "with_nested", "with_first_found",
    "register",
    "notify", "listen",
    "become", "become_user", "become_method",
    "delegate_to", "run_once",
    "ignore_errors", "ignore_unreachable",
    "no_log",
    "tags",
    "environment",
    "vars",
    "args",
]

_TASK_KEY_SET = set(TASK_KEY_ORDER)


@dataclass
class FormatResult:
    path: Path
    original: str
    formatted: str
    changed: bool
    diff: str = field(default="", repr=False)


def _normalize_jinja(match: re.Match) -> str:
    """Normalize {{ foo }} spacing to exactly one space inside braces."""
    inner = match.group(2).strip()
    if not inner:
        return "{{ }}"
    return "{{ " + inner + " }}"


def _fix_jinja_spacing(text: str) -> str:
    return JINJA_NORMALIZE_RE.sub(_normalize_jinja, text)


def _fix_tabs(text: str) -> str:
    return text.replace("\t", "  ")


def _reorder_task_keys(data: Any) -> None:
    """Reorder keys in task mappings so name comes first, then action, then meta keys."""
    if isinstance(data, CommentedSeq):
        for item in data:
            _reorder_task_keys(item)
    elif isinstance(data, CommentedMap):
        if "tasks" in data:
            _reorder_task_keys(data["tasks"])
        if "pre_tasks" in data:
            _reorder_task_keys(data["pre_tasks"])
        if "post_tasks" in data:
            _reorder_task_keys(data["post_tasks"])
        if "handlers" in data:
            _reorder_task_keys(data["handlers"])
        if "block" in data:
            _reorder_task_keys(data["block"])
        if "rescue" in data:
            _reorder_task_keys(data["rescue"])
        if "always" in data:
            _reorder_task_keys(data["always"])
        if "roles" in data:
            _reorder_task_keys(data["roles"])

        _reorder_single_task(data)


def _reorder_single_task(mapping: CommentedMap) -> None:
    """Reorder a single task/play CommentedMap: name first, then action, then known keys, then rest."""
    keys = list(mapping.keys())
    if len(keys) <= 1:
        return

    has_name = "name" in keys
    if not has_name:
        return

    action_key = None
    for k in keys:
        if k not in _TASK_KEY_SET and k != "name":
            action_key = k
            break

    desired: list[str] = []
    if has_name:
        desired.append("name")
    if action_key:
        desired.append(action_key)

    for k in TASK_KEY_ORDER:
        if k in keys and k != "name":
            desired.append(k)

    for k in keys:
        if k not in desired:
            desired.append(k)

    if desired == keys:
        return

    items = [(k, mapping[k]) for k in desired]

    mapping.clear()
    for k, v in items:
        mapping[k] = v


def format_content(text: str, filename: str = "<stdin>") -> FormatResult:
    """Format a YAML string. Returns FormatResult with original, formatted, diff."""
    original = text

    text = _fix_tabs(text)

    yaml = FormattedYAML(typ="rt", pure=True, version=(1, 1))

    try:
        data = yaml.load(text)
    except Exception:
        return FormatResult(
            path=Path(filename),
            original=original,
            formatted=original,
            changed=False,
            diff="",
        )

    if data is None or not isinstance(data, (CommentedMap, CommentedSeq, list, dict)):
        return FormatResult(
            path=Path(filename),
            original=original,
            formatted=original,
            changed=False,
            diff="",
        )

    if isinstance(data, CommentedSeq):
        for item in data:
            _reorder_task_keys(item)
    elif isinstance(data, CommentedMap):
        _reorder_task_keys(data)

    formatted = yaml.dumps(data)

    formatted = _fix_jinja_spacing(formatted)

    changed = formatted != original
    diff = ""
    if changed:
        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                formatted.splitlines(keepends=True),
                fromfile=f"a/{filename}",
                tofile=f"b/{filename}",
            )
        )

    return FormatResult(
        path=Path(filename),
        original=original,
        formatted=formatted,
        changed=changed,
        diff=diff,
    )


def format_file(path: Path) -> FormatResult:
    """Format a single YAML file on disk."""
    text = path.read_text(encoding="utf-8")
    result = format_content(text, filename=str(path))
    result.path = path
    return result


def format_directory(
    root: Path,
    exclude_patterns: list[str] | None = None,
) -> list[FormatResult]:
    """Walk a directory and format all .yml/.yaml files."""
    results: list[FormatResult] = []
    exclude = set(exclude_patterns or [])

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        rel_dir = Path(dirpath).relative_to(root)
        if any(_matches_glob(str(rel_dir / "*"), pat) for pat in exclude):
            dirnames.clear()
            continue

        for fname in sorted(filenames):
            fpath = Path(dirpath) / fname
            if fpath.suffix not in YAML_EXTENSIONS:
                continue

            rel = fpath.relative_to(root)
            if any(_matches_glob(str(rel), pat) for pat in exclude):
                continue

            results.append(format_file(fpath))

    return results


def _matches_glob(path_str: str, pattern: str) -> bool:
    """Simple glob matching using fnmatch."""
    import fnmatch
    return fnmatch.fnmatch(path_str, pattern)


def check_idempotent(result: FormatResult) -> bool:
    """Verify that formatting the formatted output produces no further changes."""
    second = format_content(result.formatted, filename=str(result.path))
    return not second.changed
