"""Build a ScanRequest from a local path (chunked filesystem)."""

import os
from pathlib import Path

from apme.v1.common_pb2 import File
from apme.v1.primary_pb2 import ScanOptions, ScanRequest

# Skip these dirs when walking (same kind of ignores as many linters)
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".tox", "htmlcov"}

# Max file size to include (bytes); skip binary-ish or huge files
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MiB

# Extensions we care about for Ansible (include these; exclude or skip binary)
TEXT_EXTENSIONS = {
    ".yml",
    ".yaml",
    ".json",
    ".j2",
    ".jinja2",
    ".md",
    ".py",
    ".sh",
    ".cfg",
    ".ini",
    ".toml",
    ".yml.sample",
    ".yaml.sample",
    ".tf",
    ".tfvars",
}


def _should_include(path: Path, root: Path) -> bool:
    if not path.is_file():
        return False
    try:
        if path.stat().st_size > MAX_FILE_SIZE:
            return False
    except OSError:
        return False
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    parts = rel.parts
    if any(p in SKIP_DIRS for p in parts):
        return False
    # Include known text extensions; include files with no extension (e.g. playbook)
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return True
    if path.name in ("playbook", "main", "meta", "handlers", "tasks", "vars", "defaults"):
        return True
    # Include small text files under roles/ and playbooks/
    return bool("roles" in parts or "playbooks" in parts or suffix in (".yml", ".yaml", ".j2"))


def build_scan_request(
    target_path: str | Path,
    scan_id: str | None = None,
    project_root_name: str = "project",
    ansible_core_version: str | None = None,
    collection_specs: list[str] | None = None,
) -> ScanRequest:
    """
    Walk target_path (file or directory) and build a ScanRequest with chunked files.
    Paths in File messages are relative to the project root (target_path if dir, else parent).
    """
    target = Path(target_path).resolve()
    if not target.exists():
        raise FileNotFoundError(f"Target does not exist: {target_path}")

    if target.is_file():
        root = target.parent
        to_visit = [target]
    else:
        root = target
        to_visit = []
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in filenames:
                to_visit.append(Path(dirpath) / name)

    files = []
    for path in to_visit:
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if not _should_include(path, root):
            continue
        try:
            content = path.read_bytes()
        except (OSError, UnicodeDecodeError):
            continue
        # Skip if looks binary
        if b"\x00" in content[:8192]:
            continue
        files.append(File(path=str(rel), content=content))

    options = ScanOptions()
    if ansible_core_version:
        options.ansible_core_version = ansible_core_version
    if collection_specs:
        options.collection_specs.extend(collection_specs)

    return ScanRequest(
        scan_id=scan_id or "",
        project_root=project_root_name,
        files=files,
        options=options,
    )
