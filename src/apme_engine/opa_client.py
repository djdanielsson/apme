"""Run OPA on hierarchy payload and return violations. Uses Podman container or local opa binary."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

OPA_IMAGE = "docker.io/openpolicyagent/opa:latest"


def _run_opa_podman(
    input_str: str,
    bundle_path: Path,
    entrypoint: str,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    """Run OPA via podman run with bundle mounted. Returns CompletedProcess.
    Uses --userns=keep-id and -u root so the container can read the bind mount
    when the OPA image runs as non-root (rootless Podman). :z allows SELinux
    to relabel the mount for container read access.
    """
    bundle_abs = bundle_path.resolve()
    cmd = [
        "podman",
        "run",
        "--rm",
        "-i",
        "--userns=keep-id",
        "-u",
        "root",
        "-v",
        f"{bundle_abs}:/bundle:ro,z",
        OPA_IMAGE,
        "eval",
        "-i",
        "-",
        "-d",
        "/bundle",
        entrypoint,
        "--format",
        "json",
    ]
    return subprocess.run(
        cmd,
        input=input_str,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _run_opa_local(
    input_str: str,
    bundle_path: Path,
    entrypoint: str,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    """Run local opa binary. Returns CompletedProcess."""
    return subprocess.run(
        ["opa", "eval", "-i", "-", "-d", str(bundle_path), entrypoint, "--format", "json"],
        input=input_str,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _run_opa_test_podman(bundle_path: Path, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    """Run `opa test . -v` inside Podman with bundle mounted. Same volume/user flags as eval."""
    bundle_abs = bundle_path.resolve()
    cmd = [
        "podman",
        "run",
        "--rm",
        "--userns=keep-id",
        "-u",
        "root",
        "-v",
        f"{bundle_abs}:/bundle:ro,z",
        OPA_IMAGE,
        "test",
        "/bundle",
        "-v",
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _run_opa_test_local(bundle_path: Path, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    """Run `opa test . -v` using local opa binary with cwd = bundle_path."""
    return subprocess.run(
        ["opa", "test", ".", "-v"],
        cwd=str(bundle_path.resolve()),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def run_opa_test(bundle_path: str | Path, timeout: int = 120) -> tuple[bool, str, str]:
    """
    Run OPA Rego unit tests (`opa test . -v`) in the bundle directory.
    Uses Podman by default; set OPA_USE_PODMAN=0 to use a local opa binary.
    Returns (success, stdout, stderr).
    """
    bundle = Path(bundle_path)
    if not bundle.is_dir():
        raise FileNotFoundError(f"OPA bundle path is not a directory: {bundle_path}")
    use_podman = os.environ.get("OPA_USE_PODMAN", "1").lower() not in ("0", "false", "no")

    out = None
    if use_podman:
        try:
            out = _run_opa_test_podman(bundle, timeout)
        except FileNotFoundError:
            out = None
    if out is None:
        try:
            out = _run_opa_test_local(bundle, timeout)
        except FileNotFoundError:
            return (False, "", "podman and opa not found. Install one or set OPA_USE_PODMAN=1 and install podman.")
    return (out.returncode == 0, out.stdout or "", out.stderr or "")


def run_opa(
    input_data: dict[str, Any], bundle_path: str, entrypoint: str = "data.apme.rules.violations"
) -> list[dict[str, Any]]:
    """
    Run OPA eval with input_data as input and bundle at bundle_path.
    Uses Podman container (openpolicyagent/opa) by default; set OPA_USE_PODMAN=0 to use a local opa binary.
    Returns list of violation objects (each with rule_id, level, message, file, line, path).
    """
    bundle = Path(bundle_path)
    if not bundle.is_dir():
        raise FileNotFoundError(f"OPA bundle path is not a directory: {bundle_path}")
    input_str = json.dumps(input_data)
    timeout = 60
    # Prefer Podman container unless OPA_USE_PODMAN=0 (then use local opa only).
    use_podman = os.environ.get("OPA_USE_PODMAN", "1").lower() not in ("0", "false", "no")

    out = None
    if use_podman:
        try:
            out = _run_opa_podman(input_str, bundle, entrypoint, timeout)
        except FileNotFoundError:
            out = None  # fall back to local opa
    if out is None:
        try:
            out = _run_opa_local(input_str, bundle, entrypoint, timeout)
        except FileNotFoundError:
            if use_podman:
                sys.stderr.write(
                    "podman: command not found. Set OPA_USE_PODMAN=0 to use local opa, or install podman.\n"
                )
            else:
                sys.stderr.write(
                    "opa: command not found. Install OPA or set OPA_USE_PODMAN=1 to use the OPA container.\n"
                )
            return []

    if out.returncode != 0:
        sys.stderr.write(f"OPA eval failed: {out.stderr or out.stdout}\n")
        return []
    try:
        result = json.loads(out.stdout)
    except json.JSONDecodeError:
        sys.stderr.write(f"OPA returned invalid JSON: {out.stdout[:500]}\n")
        return []
    # OPA eval returns { "result": [ { "expressions": [ { "value": [...] } ] } ] }
    expressions = result.get("result", [])
    if not expressions:
        return []
    value = expressions[0].get("expressions", [{}])[0].get("value")
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return []
