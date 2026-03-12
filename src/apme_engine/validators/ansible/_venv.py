"""Venv resolution and collection environment helpers for ansible validator rules."""

import os
import shutil
from pathlib import Path

SUPPORTED_VERSIONS = ["2.18", "2.19", "2.20"]
DEFAULT_VERSION = "2.20"


def prebuilt_venvs_root() -> Path | None:
    root = os.environ.get("APME_ANSIBLE_VENVS_ROOT", "").strip()
    if root:
        p = Path(root)
        if p.is_dir():
            return p
    return None


def find_prebuilt_venv(version: str) -> Path | None:
    root = prebuilt_venvs_root()
    if root is None:
        return None
    parts = version.split(".")
    major_minor = ".".join(parts[:2]) if len(parts) >= 2 else version
    venv = root / major_minor
    if venv.is_dir() and (venv / "bin" / "ansible-playbook").is_file():
        return venv
    return None


def resolve_venv_root(version: str) -> Path | None:
    """Return the venv root directory for a given version, or None."""
    venv = find_prebuilt_venv(version)
    if venv is not None:
        return venv
    which = shutil.which("ansible-playbook")
    if which:
        bin_dir = Path(which).parent
        candidate = bin_dir.parent
        if (candidate / "pyvenv.cfg").is_file():
            return candidate
    return None


def resolve_ansible_playbook(version: str) -> Path | None:
    """Find ansible-playbook for a given version: pre-built venv first, then system PATH."""
    venv = find_prebuilt_venv(version)
    if venv is not None:
        return venv / "bin" / "ansible-playbook"
    which = shutil.which("ansible-playbook")
    if which:
        return Path(which)
    return None


def setup_collections_env(collection_specs: list[str], cache_root: Path) -> dict[str, str] | None:
    """Build ANSIBLE_COLLECTIONS_PATH pointing at the cache so ansible finds collections."""
    if not collection_specs:
        return None
    from apme_engine.collection_cache.config import galaxy_cache_dir, github_cache_dir

    paths = []
    galaxy = galaxy_cache_dir(cache_root)
    if galaxy.is_dir():
        paths.append(str(galaxy))
    github = github_cache_dir(cache_root)
    if github.is_dir():
        for org_dir in github.iterdir():
            if org_dir.is_dir():
                paths.append(str(org_dir))
    if paths:
        return {"ANSIBLE_COLLECTIONS_PATH": ":".join(paths)}
    return None
