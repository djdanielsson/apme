"""Rule-doc integration harness helpers (test-only scan path).

Creates minimal on-disk role trees so inline ``roles:`` references resolve
DEPENDENCY edges during single-file doc-integration scans.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import yaml

from apme_engine.runner import run_scan
from apme_engine.validators.base import ScanContext

logger = logging.getLogger(__name__)

_ROLE_STUB_TASK = "- name: apme role stub\n  ansible.builtin.debug:\n    msg: apme-stub\n  changed_when: false\n"

_ROLE_STUB_ARGUMENT_SPECS = """---
argument_specs:
  main:
    short_description: APME doc-integration stub role.
    options: {}
"""


def _role_meta_main_yml(role_name: str) -> str:
    """Return minimal meta/main.yml for a scaffolded stub role.

    Args:
        role_name: Short role directory name.

    Returns:
        YAML string for meta/main.yml.
    """
    return (
        "---\n"
        "galaxy_info:\n"
        f"  role_name: {role_name}\n"
        "  description: APME doc-integration stub role\n"
        '  min_ansible_version: "2.14"\n'
    )


def _is_safe_role_name(role_name: str, project_root: str) -> bool:
    """Return True when ``role_name`` is safe to use under ``roles/``.

    Args:
        role_name: Candidate role directory name from playbook YAML.
        project_root: Scan root directory.

    Returns:
        True when the resolved path stays inside ``roles/``.
    """
    if not role_name or role_name in (".", ".."):
        return False
    if os.sep in role_name or (os.altsep and os.altsep in role_name):
        return False
    if "/" in role_name or "\\" in role_name:
        return False

    roles_root = (Path(project_root).resolve() / "roles").resolve()
    try:
        (roles_root / role_name).resolve().relative_to(roles_root)
    except ValueError:
        return False
    return True


def _role_names_from_playbook_yaml(yaml_content: str) -> set[str]:
    """Extract short role names referenced from play ``roles:`` lists.

    Args:
        yaml_content: Playbook YAML string.

    Returns:
        Set of role names to scaffold under ``roles/<name>/``.
    """
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as exc:
        logger.debug("Skipping role scaffold parse: %s", exc)
        return set()
    if data is None:
        return set()

    plays: list[object]
    if isinstance(data, list):
        plays = data
    elif isinstance(data, dict):
        plays = [data]
    else:
        return set()

    names: set[str] = set()
    for play in plays:
        if not isinstance(play, dict):
            continue
        roles_raw = play.get("roles")
        if not isinstance(roles_raw, list):
            continue
        for entry in roles_raw:
            if isinstance(entry, str) and entry:
                names.add(entry.split("/")[-1])
            elif isinstance(entry, dict):
                role_val = entry.get("role") or entry.get("name")
                if isinstance(role_val, str) and role_val:
                    names.add(role_val.split("/")[-1])
    return names


def _scaffold_inline_roles(project_root: str, yaml_content: str) -> None:
    """Create minimal on-disk role trees for inline ``roles:`` references.

    Args:
        project_root: Scan root directory.
        yaml_content: Playbook YAML that may declare ``roles:``.
    """
    for role_name in _role_names_from_playbook_yaml(yaml_content):
        if not _is_safe_role_name(role_name, project_root):
            logger.debug("Skipping unsafe scaffold role name: %r", role_name)
            continue

        role_dir = os.path.join(project_root, "roles", role_name)
        tasks_dir = os.path.join(role_dir, "tasks")
        tasks_file = os.path.join(tasks_dir, "main.yml")
        if os.path.isfile(tasks_file):
            continue

        meta_dir = os.path.join(role_dir, "meta")
        os.makedirs(tasks_dir, exist_ok=True)
        os.makedirs(meta_dir, exist_ok=True)

        with open(tasks_file, "w") as f:
            f.write(_ROLE_STUB_TASK)
        with open(os.path.join(meta_dir, "main.yml"), "w") as f:
            f.write(_role_meta_main_yml(role_name))
        with open(os.path.join(meta_dir, "argument_specs.yml"), "w") as f:
            f.write(_ROLE_STUB_ARGUMENT_SPECS)


def run_scan_playbook_yaml(
    yaml_content: str,
    project_root: str | None = None,
    include_scandata: bool = True,
) -> ScanContext:
    """Run the engine on a playbook given as a YAML string (for integration tests).

    Writes content to a temporary playbook file and runs the scanner.

    Args:
        yaml_content: Full playbook YAML string (e.g. a list of plays with hosts and tasks).
        project_root: Unused; kept for call-site compatibility. A temp directory is always used.
        include_scandata: If True, attach the SingleScan to context for native validator.

    Returns:
        ScanContext with hierarchy_payload and optionally scandata.

    """
    del project_root
    with tempfile.TemporaryDirectory(prefix="apme_rule_doc_") as tmpdir:
        _scaffold_inline_roles(tmpdir, yaml_content)
        playbook_path = os.path.join(tmpdir, "playbook.yml")
        with open(playbook_path, "w") as f:
            f.write(yaml_content)
        return run_scan(playbook_path, tmpdir, include_scandata=include_scandata)
