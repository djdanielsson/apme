"""AWX-derived utilities for playbook detection and directory filtering."""

import codecs
import os
import re

valid_playbook_re = re.compile(r"^\s*?-?\s*?(?:hosts|include|import_playbook):\s*?.*?$")

# EDA rulebook detection patterns:
# 1. List item start: "- name:" at column 0 indicates ruleset definition
# 2. Ruleset-level keys: "sources:" or "rules:" at exactly 2-space indent
#    (child of the list item, not nested deeper in vars/module params)
_eda_list_item_re = re.compile(r"^-\s+name:\s*\S")
_eda_ruleset_key_re = re.compile(r"^  (?:sources|rules):\s*(?:\S.*)?$")


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
    basename, ext = os.path.splitext(fpath)
    if ext not in [".yml", ".yaml"]:
        return False

    # Path-based detection: files in rulebooks/ or extensions/eda/ directories
    if is_eda_rulebook_path(fpath):
        return True

    # Content-based detection: look for EDA rulebook structure
    # Requires seeing "- name:" list item followed by "sources:" or "rules:"
    # at exactly 2-space indent (ruleset-level, not nested in vars/params)
    try:
        saw_list_item = False
        with codecs.open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            for n, line in enumerate(f):
                if n > 100:
                    break
                if _eda_list_item_re.match(line):
                    saw_list_item = True
                elif saw_list_item and _eda_ruleset_key_re.match(line):
                    return True
    except OSError:
        return False
    return False


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
    basename, ext = os.path.splitext(fpath)
    if ext not in [".yml", ".yaml"]:
        return False

    # EDA rulebooks should not be treated as playbooks
    if could_be_eda_rulebook(fpath):
        return False

    # Filter files that do not have either hosts or top-level
    # includes. Use regex to allow files with invalid YAML to
    # show up.
    matched = False
    try:
        with codecs.open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            for n, line in enumerate(f):
                if valid_playbook_re.match(line) or n == 0 and line.startswith("$ANSIBLE_VAULT;"):
                    matched = True
                    break
    except OSError:
        return False
    return matched


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
