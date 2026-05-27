"""AWX-derived utilities for playbook detection and directory filtering."""

import os
import re

import yaml

from .models import YAMLDict

valid_playbook_re = re.compile(r"^\s*?-?\s*?(?:hosts|include|import_playbook):\s*?.*?$")

# EDA rulebook detection patterns (regex fallback when YAML does not parse):
# 1. List item start: "- name:" at column 0 indicates ruleset definition
# 2. Ruleset-level keys: "sources:" or "rules:" at exactly 2-space indent
# 3. Playbook-only keys at 2-space indent reject EDA classification
# 4. "rules:" alone requires a following "condition:" or "action:" at 4-space indent
_eda_list_item_re = re.compile(r"^-\s+name:\s*\S")
_eda_ruleset_key_re = re.compile(r"^  (?:sources|rules):\s*(?:\S.*)?$")
_eda_sources_key_re = re.compile(r"^  sources:\s*(?:\S.*)?$")
_eda_playbook_section_re = re.compile(r"^  (?:tasks|roles|handlers|pre_tasks|post_tasks):")
_eda_rule_structure_re = re.compile(r"^    (?:condition|action):")

# Keys that identify a play, not an EDA ruleset (first list item dict).
_PLAYBOOK_SECTION_KEYS = frozenset({"tasks", "roles", "handlers", "pre_tasks", "post_tasks"})


def _normalize_eda_path(fpath: str) -> str:
    """Normalize a file path for EDA directory matching.

    Args:
        fpath: Path to normalize.

    Returns:
        Lowercase path with OS separators replaced by ``/``.
    """
    return fpath.replace(os.sep, "/").lower()


def is_eda_rulebook_path(fpath: str) -> bool:
    """Return True if *fpath* lies under a conventional EDA rulebook directory.

    Matches both absolute segments (``/rulebooks/``) and relative paths
    (``rulebooks/foo.yml``, ``extensions/eda/...``) after normalizing separators.

    Args:
        fpath: Path to check.

    Returns:
        True when the path is under ``rulebooks/`` or ``extensions/eda/``.
    """
    norm = _normalize_eda_path(fpath)
    return (
        norm.startswith("rulebooks/")
        or "/rulebooks/" in norm
        or norm.startswith("extensions/eda/")
        or "/extensions/eda/" in norm
    )


def looks_like_eda_ruleset(ruleset: YAMLDict) -> bool:
    """Return True when *ruleset* is an EDA ruleset, not a play with stray keys.

    Playbooks that accidentally include ``sources``/``rules`` at the play level
    without EDA structure should remain playbooks so L095 can report unknown keys.

    Args:
        ruleset: First mapping from a YAML list (ruleset / play dict).

    Returns:
        True if the dict matches EDA ruleset structure.
    """
    if _PLAYBOOK_SECTION_KEYS & ruleset.keys():
        return False
    if "sources" in ruleset:
        sources = ruleset["sources"]
        if sources is None or isinstance(sources, list):
            return True
    if "rules" in ruleset:
        rules = ruleset["rules"]
        if isinstance(rules, list):
            if not rules:
                return "sources" in ruleset
            return any(isinstance(item, dict) and ("condition" in item or "action" in item) for item in rules)
    return False


def _read_yaml_header_lines(fpath: str, max_lines: int = 101) -> list[str] | None:
    """Read up to *max_lines* from a YAML file for heuristic scans.

    Args:
        fpath: Path to the YAML file.
        max_lines: Maximum number of lines to read.

    Returns:
        Lines read from the file, or None on I/O error.
    """
    try:
        lines: list[str] = []
        with open(fpath, encoding="utf-8", errors="ignore") as f:
            for line in f:
                lines.append(line)
                if len(lines) >= max_lines:
                    break
        return lines
    except OSError:
        return None


def _playbook_like_from_lines(lines: list[str]) -> bool:
    """Return True when *lines* contain playbook markers or a vault header.

    Args:
        lines: First portion of a YAML file.

    Returns:
        True when hosts/include/import_playbook or a vault header is present.
    """
    for n, line in enumerate(lines):
        if valid_playbook_re.match(line) or (n == 0 and line.startswith("$ANSIBLE_VAULT;")):
            return True
    return False


def _lines_might_contain_eda_keys(lines: list[str]) -> bool:
    """Return True when *lines* may contain ruleset-level EDA keys.

    Args:
        lines: First portion of a YAML file.

    Returns:
        True when a ruleset-level ``sources:`` or ``rules:`` line appears.
    """
    return any(
        _eda_sources_key_re.match(line) or (_eda_ruleset_key_re.match(line) and "rules:" in line) for line in lines
    )


def _eda_from_lines(lines: list[str]) -> bool:
    """Content-based EDA detection via line patterns (no YAML parse).

    Args:
        lines: First portion of a YAML file.

    Returns:
        True when line patterns match an EDA ruleset and no playbook sections appear.
    """
    saw_list_item = False
    saw_rules_key = False
    for line in lines:
        if _eda_playbook_section_re.match(line):
            return False
        if _eda_list_item_re.match(line):
            saw_list_item = True
        elif saw_list_item and _eda_sources_key_re.match(line):
            return True
        elif saw_list_item and _eda_ruleset_key_re.match(line) and "rules:" in line:
            saw_rules_key = True
        elif saw_rules_key and _eda_rule_structure_re.match(line):
            return True
    return False


def _load_first_ruleset_from_lines(lines: list[str]) -> YAMLDict | None:
    """Load the first list-item mapping from YAML text, if present.

    Args:
        lines: YAML source lines.

    Returns:
        The first mapping when the document is a non-empty list, else None.
    """
    try:
        data = yaml.safe_load("".join(lines))
    except yaml.YAMLError:
        return None
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    return None


def _eda_content_from_lines(lines: list[str]) -> bool:
    """Return True when *lines* describe EDA content (regex, then optional YAML parse).

    Args:
        lines: First portion of a YAML file.

    Returns:
        True when the content matches EDA ruleset structure.
    """
    if _eda_from_lines(lines):
        return True
    if not _lines_might_contain_eda_keys(lines):
        return False
    ruleset = _load_first_ruleset_from_lines(lines)
    return ruleset is not None and looks_like_eda_ruleset(ruleset)


def could_be_eda_rulebook(fpath: str) -> bool:
    """Check if a file is an EDA rulebook based on path and content.

    Uses a two-tier detection approach:
    1. Path-based: Files under ``rulebooks/`` or ``extensions/eda/`` directories
       (absolute or relative) are assumed to be EDA content regardless of
       their internal structure.
    2. Content-based: For files outside those directories, requires EDA
       rulebook structure: a list item (``- name: ...``) followed by
       ``sources:`` or ``rules:`` at exactly 2-space indent (ruleset-level
       keys, not nested in vars or module parameters).

    This tightened heuristic avoids false positives on Kubernetes manifests
    (``spec.rules:``) or playbooks with nested ``vars: {rules: ...}``.

    This function is called before could_be_playbook() to prevent EDA files
    from being misclassified as playbooks (which would cause L095 false
    positives for 'unknown play keyword' on sources/rules).

    Args:
        fpath: Path to the file to check.

    Returns:
        True if the file appears to be an EDA rulebook.
    """
    _, ext = os.path.splitext(fpath)
    if ext not in [".yml", ".yaml"]:
        return False

    # Path-based detection: files in rulebooks/ or extensions/eda/ directories
    if is_eda_rulebook_path(fpath):
        return True

    lines = _read_yaml_header_lines(fpath)
    if lines is None:
        return False
    return _eda_content_from_lines(lines)


# this method is based on awx code
# awx/main/utils/ansible.py#L42-L64 in ansible/awx
def could_be_playbook(fpath: str) -> bool:
    """Check if a file might be an Ansible playbook based on extension and content.

    Uses regex to detect hosts/include/import_playbook at top level or vault header,
    allowing files with invalid YAML to be identified as potential playbooks.

    Args:
        fpath: Path to the file to check.

    Returns:
        True if the file has .yml/.yaml extension and appears playbook-like.
    """
    _, ext = os.path.splitext(fpath)
    if ext not in [".yml", ".yaml"]:
        return False

    # Path-based EDA directories are never playbooks (no file read).
    if is_eda_rulebook_path(fpath):
        return False

    lines = _read_yaml_header_lines(fpath)
    if lines is None:
        return False

    # Cheap playbook heuristic first; skip YAML parse for vars/manifests, etc.
    if not _playbook_like_from_lines(lines):
        return False

    # Playbook-shaped files may still be EDA rulebooks (hosts + sources/rules).
    return not _eda_content_from_lines(lines)


# this method is based on awx code
# awx/main/models/projects.py#L206-L217 in ansible/awx
def search_playbooks(root_path: str) -> list[str]:
    """Recursively find all files that could be Ansible playbooks under a root path.

    Walks the directory tree, skipping directories per skip_directory, and returns
    paths to files that pass could_be_playbook.

    Args:
        root_path: Root directory to search.

    Returns:
        Sorted list of playbook file paths (case-insensitive sort).
    """
    results = []
    if root_path and os.path.exists(root_path):
        for dirpath, _dirnames, filenames in os.walk(root_path, followlinks=False):
            if skip_directory(dirpath):
                continue
            for filename in filenames:
                fpath = os.path.join(dirpath, filename)
                if could_be_playbook(fpath):
                    results.append(fpath)
    return sorted(results, key=lambda x: x.lower())


# this method is based on awx code
# awx/main/utils/ansible.py#L24-L39 in ansible/awx
def skip_directory(relative_directory_path: str) -> bool:
    """Determine if a directory should be excluded from playbook search.

    Skips roles, tasks, molecule, tests/integration, dot-prefixed paths,
    group_vars, and host_vars directories.

    Args:
        relative_directory_path: Path of the directory to check.

    Returns:
        True if the directory should be skipped.
    """
    path_elements = relative_directory_path.split(os.sep)
    # Exclude files in a roles subdirectory.
    if "roles" in path_elements:
        return True
    # Filter files in a tasks subdirectory.
    if "tasks" in path_elements:
        return True
    # Filter files in a molecule subdirectory.
    if "molecule" in path_elements:
        return True
    # Filter files in a tests/integration subdirectory.
    if "tests" in path_elements and "integration" in path_elements:
        return True
    for element in path_elements:
        # Do not include dot files or dirs
        if element.startswith("."):
            return True
    # Exclude anything inside of group or host vars directories
    return bool("group_vars" in path_elements or "host_vars" in path_elements)
