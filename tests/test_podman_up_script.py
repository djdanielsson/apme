"""Regression tests for CA bundle injection in ``containers/podman/up.sh``."""

from __future__ import annotations

import json
import os
import re
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
UP_SH = REPO_ROOT / "containers/podman/up.sh"
POD_YAML = REPO_ROOT / "containers/podman/pod.yaml"


def _extract_ca_injection_python(script: str) -> tuple[str, str]:
    """Return the embedded Python CA patcher and its mount path.

    Args:
        script: Full contents of ``containers/podman/up.sh``.

    Returns:
        Tuple of the embedded Python source and the CA mount path.

    Raises:
        AssertionError: If the CA mount path assignment is missing from ``up.sh``.
    """
    mount_match = re.search(r'^  CA_MOUNT_PATH="([^"]+)"$', script, re.MULTILINE)
    if mount_match is None:
        raise AssertionError("CA_MOUNT_PATH assignment not found in up.sh")

    mount_path = mount_match.group(1)
    start = script.index("import json, sys, os")
    end = script.index("print(yaml)") + len("print(yaml)")
    code = script[start:end]
    return code.replace("mount = '$CA_MOUNT_PATH'", f"mount = {mount_path!r}"), mount_path


def _render_ca_injected_pod_yaml() -> tuple[str, str]:
    """Execute the embedded CA patcher against ``pod.yaml``.

    Returns:
        Tuple of rendered pod YAML and the CA mount path used by the script.
    """
    script = UP_SH.read_text(encoding="utf-8")
    code, mount_path = _extract_ca_injection_python(script)
    compile(code, str(UP_SH), "exec")

    old_stdin = sys.stdin
    old_stdout = sys.stdout
    try:
        sys.stdin = StringIO(POD_YAML.read_text(encoding="utf-8"))
        sys.stdout = StringIO()
        with patch.dict(os.environ, {"ABBENAY_CA_BUNDLE": "/tmp/custom-ca.pem"}, clear=True):
            exec(code, {"__name__": "__main__"})
        rendered = sys.stdout.getvalue()
    finally:
        sys.stdin = old_stdin
        sys.stdout = old_stdout

    return rendered, mount_path


def test_up_sh_injects_ca_bundle_into_galaxy_proxy() -> None:
    """Galaxy Proxy receives the same CA env vars and mount as the gateway."""
    rendered, mount_path = _render_ca_injected_pod_yaml()
    quoted_mount = json.dumps(mount_path)
    quoted_ca_path = json.dumps("/tmp/custom-ca.pem")

    galaxy_match = re.search(
        r"    - name: galaxy-proxy\n(?P<body>.*?)(?:\n  volumes:\n)",
        rendered,
        re.DOTALL,
    )
    assert galaxy_match is not None
    galaxy_block = galaxy_match.group("body")
    assert "      env:\n" in galaxy_block

    for env_var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "GIT_SSL_CAINFO"):
        assert f"        - name: {env_var}\n          value: {quoted_mount}" in galaxy_block

    assert (
        "      volumeMounts:\n"
        "        - name: galaxy-ca-bundle\n"
        f"          mountPath: {quoted_mount}\n"
        "          readOnly: true\n"
        "        - name: proxy-cache"
    ) in galaxy_block
    assert (
        f"    - name: galaxy-ca-bundle\n      hostPath:\n        path: {quoted_ca_path}\n        type: File\n"
    ) in rendered
