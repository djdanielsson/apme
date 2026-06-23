"""Run the integrated scan engine and return a ScanContext."""

import logging
import os
import tempfile
import time
from pathlib import Path

import yaml

from apme_engine.engine.scanner import AnsibleProjectLoader
from apme_engine.validators.base import EngineDiagnostics, ScanContext

logger = logging.getLogger("apme.engine")

_ROLE_STUB_TASK = "- name: apme role stub\n  ansible.builtin.meta: end_host\n"


def _role_names_from_playbook_yaml(yaml_content: str) -> set[str]:
    """Extract short role names referenced from play ``roles:`` lists.

    Args:
        yaml_content: Playbook YAML string.

    Returns:
        Set of role names to scaffold under ``roles/<name>/``.
    """
    try:
        data = yaml.safe_load(yaml_content)
    except Exception:
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
        tasks_dir = os.path.join(project_root, "roles", role_name, "tasks")
        tasks_file = os.path.join(tasks_dir, "main.yml")
        if os.path.isfile(tasks_file):
            continue
        os.makedirs(tasks_dir, exist_ok=True)
        with open(tasks_file, "w") as f:
            f.write(_ROLE_STUB_TASK)


def run_scan_playbook_yaml(
    yaml_content: str,
    project_root: str | None = None,
    include_scandata: bool = True,
) -> ScanContext:
    """Run the engine on a playbook given as a YAML string (e.g. for integration tests).

    Writes content to a temporary playbook file and runs the scanner.

    Args:
        yaml_content: Full playbook YAML string (e.g. a list of plays with hosts and tasks).
        project_root: Root directory for the scan. If None, a temp directory is used.
        include_scandata: If True, attach the SingleScan to context for native validator.

    Returns:
        ScanContext with hierarchy_payload and optionally scandata.

    """
    with tempfile.TemporaryDirectory(prefix="apme_rule_doc_") as tmpdir:
        _scaffold_inline_roles(tmpdir, yaml_content)
        playbook_path = os.path.join(tmpdir, "playbook.yml")
        with open(playbook_path, "w") as f:
            f.write(yaml_content)
        # Use temp dir as project root so scanner writes under tmpdir (works in sandbox)
        return run_scan(playbook_path, tmpdir, include_scandata=include_scandata)


def run_scan(
    target_path: str,
    project_root: str,
    include_scandata: bool = True,
    dependency_dir: str = "",
    include_test_contents: bool = True,
) -> ScanContext:
    """Run the engine on target_path and return a ScanContext for validators.

    The loader never downloads collections. When a session venv is available,
    pass its site-packages as ``dependency_dir`` so the loader can resolve
    external collection definitions.

    Args:
        target_path: Path to playbook file, taskfile, or project directory.
        project_root: Root directory for the scan (data dir).
        include_scandata: If True, attach the SingleScan to context for native validator.
        dependency_dir: Pre-installed dependency directory (e.g. session venv
            site-packages).  The loader reads from this path but never writes to it.
        include_test_contents: If True, include test directories in the scan.

    Returns:
        ScanContext with hierarchy_payload and optionally scandata.

    Raises:
        FileNotFoundError: If target_path does not exist.

    """
    root_dir = project_root or os.path.expanduser("~/.apme-data")
    loader = AnsibleProjectLoader(
        root_dir=root_dir,
        silent=True,
    )
    path = Path(target_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Target path does not exist: {target_path}")
    if path.is_file():
        name = str(path)
        base_dir = str(path.parent)
        scan_type = "playbook"
    else:
        name = str(path)
        base_dir = str(path)
        scan_type = "project"

    logger.info("Engine: loader start (%s, type=%s)", Path(name).name, scan_type)
    t0 = time.monotonic()
    scandata = loader.load(
        type=scan_type,
        name=name,
        path=name,
        base_dir=base_dir,
        dependency_dir=dependency_dir,
        skip_dependency=False,
        load_all_taskfiles=True,
        include_test_contents=include_test_contents,
    )
    engine_total_ms = (time.monotonic() - t0) * 1000
    logger.info("Engine: loader done (%.0fms)", engine_total_ms)
    diag = _extract_engine_diagnostics(scandata, engine_total_ms)

    if not scandata or not getattr(scandata, "hierarchy_payload", None):
        return ScanContext(
            hierarchy_payload={},
            scandata=scandata if include_scandata else None,
            root_dir=root_dir,
            engine_diagnostics=diag,
        )
    return ScanContext(
        hierarchy_payload=scandata.hierarchy_payload,
        scandata=scandata if include_scandata else None,
        root_dir=root_dir,
        engine_diagnostics=diag,
    )


def _extract_engine_diagnostics(scandata: object, engine_total_ms: float) -> EngineDiagnostics:
    """Pull per-phase elapsed times from the scanner's time_records.

    Args:
        scandata: Scanner result object with findings metadata.
        engine_total_ms: Total engine wall-clock time in milliseconds.

    Returns:
        EngineDiagnostics populated from time_records.

    """
    diag = EngineDiagnostics(total_ms=engine_total_ms)
    if not scandata:
        return diag

    tr = {}
    if hasattr(scandata, "findings") and scandata.findings:
        tr = getattr(scandata.findings, "metadata", {}).get("time_records", {})

    def _ms(key: str) -> float:
        return float(tr.get(key, {}).get("elapsed", 0.0)) * 1000

    diag.parse_ms = _ms("target_load") + _ms("prm_load") + _ms("metadata_load")
    diag.annotate_ms = 0.0
    diag.tree_build_ms = _ms("graph_construction")

    cg = getattr(scandata, "content_graph", None)
    if cg is not None:
        diag.graph_nodes_built = cg.node_count()

    root_defs = getattr(scandata, "root_definitions", None)
    if root_defs:
        diag.files_scanned = len(root_defs)

    return diag
