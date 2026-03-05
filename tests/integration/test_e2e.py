"""End-to-end integration test: rebuild containers, start pod, run scan, assert violations.

Requires Podman and built images. Mark with ``@pytest.mark.integration`` so it
can be skipped in normal ``pytest`` runs (use ``pytest -m integration``).

Options via environment variables:
    APME_E2E_SKIP_BUILD=1      skip image rebuild
    APME_E2E_SKIP_TEARDOWN=1   leave the pod running after the test
"""

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
POD_NAME = "apme-pod"
CLI_IMAGE = "apme-cli:latest"
PRIMARY_ADDR = "127.0.0.1:50051"
POD_STARTUP_TIMEOUT = 90
SERVICE_SETTLE_SECONDS = 5


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def _podman(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return _run(["podman", *args], check=check)


def _pod_status() -> str:
    r = _podman("pod", "list", "--filter", f"name={POD_NAME}", "--format", "{{.Status}}", check=False)
    return r.stdout.strip()


def _container_logs(name: str) -> str:
    r = _podman("logs", f"{POD_NAME}-{name}", check=False)
    return r.stdout + r.stderr


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pod():
    """Build images (unless skipped), start the pod, yield, then tear down."""
    skip_build = os.environ.get("APME_E2E_SKIP_BUILD", "0") == "1"
    skip_teardown = os.environ.get("APME_E2E_SKIP_TEARDOWN", "0") == "1"

    if not skip_build:
        result = _run(["bash", str(REPO_ROOT / "containers" / "podman" / "build.sh")], cwd=str(REPO_ROOT))
        assert result.returncode == 0, f"Image build failed:\n{result.stderr}"

    _podman("pod", "rm", "-f", POD_NAME, check=False)
    result = _run(
        ["podman", "play", "kube", str(REPO_ROOT / "containers" / "podman" / "pod.yaml")],
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"Pod creation failed:\n{result.stderr}"

    deadline = time.time() + POD_STARTUP_TIMEOUT
    while time.time() < deadline:
        if _pod_status() == "Running":
            break
        time.sleep(1)
    else:
        logs = _podman("pod", "logs", POD_NAME, check=False)
        pytest.fail(f"Pod did not reach Running within {POD_STARTUP_TIMEOUT}s.\n{logs.stdout}\n{logs.stderr}")

    time.sleep(SERVICE_SETTLE_SECONDS)
    yield

    if not skip_teardown:
        _podman("pod", "rm", "-f", POD_NAME, check=False)


@pytest.fixture(scope="module")
def scan_result(pod) -> dict:
    """Run a scan of the test playbook via the CLI container and return parsed JSON."""
    test_dir = str(REPO_ROOT / "tests" / "integration")
    r = _run([
        "podman", "run", "--rm", "--pod", POD_NAME,
        "-v", f"{test_dir}:/workspace:ro,Z",
        "-w", "/workspace",
        "-e", f"APME_PRIMARY_ADDRESS={PRIMARY_ADDR}",
        "--entrypoint", "apme-scan",
        CLI_IMAGE,
        "scan", "--json", ".",
    ])
    assert r.returncode == 0, f"Scan failed (rc={r.returncode}):\n{r.stdout}\n{r.stderr}"
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"Scan output is not valid JSON:\n{r.stdout}")


def _violation_rule_ids(scan_result: dict) -> set[str]:
    return {v.get("rule_id", "") for v in scan_result.get("violations", [])}


# ---------------------------------------------------------------------------
# Phase 3: Health check
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestHealthCheck:
    def test_overall_ok(self, pod):
        r = _run([
            "podman", "run", "--rm", "--pod", POD_NAME,
            "-e", f"APME_PRIMARY_ADDRESS={PRIMARY_ADDR}",
            "--entrypoint", "apme-scan",
            CLI_IMAGE,
            "health-check", "--primary-addr", PRIMARY_ADDR,
        ])
        combined = r.stdout + r.stderr
        assert "overall: ok" in combined, f"Health check did not report ok:\n{combined}"


# ---------------------------------------------------------------------------
# Phase 4+5: Scan and assert expected violations
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestScanViolations:
    def test_violations_returned(self, scan_result):
        count = scan_result.get("count", 0)
        assert count > 0, f"Expected >0 violations, got {count}"

    # OPA rules
    @pytest.mark.parametrize("rule_id,desc", [
        ("L007", "shell when command suffices"),
        ("L010", "ignore_errors without register"),
        ("L021", "missing explicit mode on file/copy"),
        ("L025", "name not starting uppercase"),
        ("R118", "inbound transfer (annotation-based)"),
    ])
    def test_opa_rule(self, scan_result, rule_id, desc):
        assert rule_id in _violation_rule_ids(scan_result), f"{rule_id} ({desc}) not found"

    # Native rules
    @pytest.mark.parametrize("rule_id,desc", [
        ("native:L028", "task without name"),
        ("native:L029", "command instead of shell"),
        ("native:L046", "free-form args"),
    ])
    def test_native_rule(self, scan_result, rule_id, desc):
        assert rule_id in _violation_rule_ids(scan_result), f"{rule_id} ({desc}) not found"

    # Modernize rules
    def test_m001_fqcn_resolution(self, scan_result):
        assert "M001" in _violation_rule_ids(scan_result), "M001 (FQCN resolution) not found"

    # Ansible validator rules
    @pytest.mark.parametrize("rule_id,desc", [
        ("L058", "argspec validation - docstring"),
        ("L059", "argspec validation - mock/patch"),
    ])
    def test_ansible_rule(self, scan_result, rule_id, desc):
        assert rule_id in _violation_rule_ids(scan_result), f"{rule_id} ({desc}) not found"


# ---------------------------------------------------------------------------
# Phase 6: No duplicates
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestNoDuplicates:
    def test_no_duplicate_violations(self, scan_result):
        seen: set[tuple] = set()
        dups: list[tuple] = []
        for v in scan_result.get("violations", []):
            line = v.get("line")
            if isinstance(line, list):
                line = tuple(line)
            key = (v.get("rule_id", ""), v.get("file", ""), line)
            if key in seen:
                dups.append(key)
            seen.add(key)
        assert len(dups) == 0, f"Found {len(dups)} duplicate(s): {dups}"


# ---------------------------------------------------------------------------
# Phase 7-9: Container logs
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestContainerLogs:
    def test_primary_logged_opa_count(self, scan_result):
        logs = _container_logs("primary")
        assert "Opa=" in logs, f"Primary did not log OPA count:\n{logs[-500:]}"

    def test_primary_logged_native_count(self, scan_result):
        logs = _container_logs("primary")
        assert "Native=" in logs, f"Primary did not log Native count:\n{logs[-500:]}"

    def test_opa_wrapper_logged(self, scan_result):
        logs = _container_logs("opa")
        assert "OPA returned" in logs, f"OPA wrapper did not log:\n{logs[-500:]}"

    def test_native_validator_logged(self, scan_result):
        logs = _container_logs("native")
        assert "Native validator returned" in logs, f"Native did not log:\n{logs[-500:]}"

    def test_ansible_introspection(self, scan_result):
        logs = _container_logs("ansible")
        assert "introspecting" in logs, f"Ansible did not run introspection:\n{logs[-500:]}"

    def test_ansible_argspec(self, scan_result):
        logs = _container_logs("ansible")
        assert "argspec" in logs, f"Ansible did not run argspec:\n{logs[-500:]}"


# ---------------------------------------------------------------------------
# Phase 10: Gitleaks validator (container-level)
# ---------------------------------------------------------------------------

SECRETS_FIXTURE = REPO_ROOT / "tests" / "integration" / "test_secrets_playbook.yml"


@pytest.mark.integration
class TestGitleaks:
    def test_gitleaks_container_healthy(self, pod):
        r = _run([
            "podman", "run", "--rm", "--pod", POD_NAME,
            "-e", f"APME_PRIMARY_ADDRESS={PRIMARY_ADDR}",
            "--entrypoint", "apme-scan",
            CLI_IMAGE,
            "health-check", "--primary-addr", PRIMARY_ADDR,
        ])
        combined = r.stdout + r.stderr
        assert "gitleaks" in combined.lower() or "overall: ok" in combined, \
            f"Gitleaks not reported in health check:\n{combined}"

    def test_gitleaks_logged(self, scan_result):
        logs = _container_logs("gitleaks")
        assert "Gitleaks validator" in logs, f"Gitleaks did not log:\n{logs[-500:]}"

    def test_primary_logged_gitleaks_count(self, scan_result):
        logs = _container_logs("primary")
        assert "Gitleaks=" in logs, f"Primary did not log Gitleaks count:\n{logs[-500:]}"


# ---------------------------------------------------------------------------
# Phase 11: Format subcommand (container-level)
# ---------------------------------------------------------------------------

FORMAT_FIXTURE = REPO_ROOT / "tests" / "integration" / "test_format_playbook.yml"


@pytest.mark.integration
class TestFormat:
    def test_format_check_detects_issues(self, pod):
        """format --check on messy fixture exits 1."""
        test_dir = str(FORMAT_FIXTURE.parent)
        r = _run([
            "podman", "run", "--rm", "--pod", POD_NAME,
            "-v", f"{test_dir}:/workspace:ro,Z",
            "-w", "/workspace",
            "--entrypoint", "apme-scan",
            CLI_IMAGE,
            "format", "--check", "test_format_playbook.yml",
        ])
        assert r.returncode == 1, f"Expected exit 1 for messy file:\n{r.stdout}\n{r.stderr}"

    def test_format_diff_shows_transforms(self, pod):
        """format (no --apply) shows unified diff with expected transforms."""
        test_dir = str(FORMAT_FIXTURE.parent)
        r = _run([
            "podman", "run", "--rm", "--pod", POD_NAME,
            "-v", f"{test_dir}:/workspace:ro,Z",
            "-w", "/workspace",
            "--entrypoint", "apme-scan",
            CLI_IMAGE,
            "format", "test_format_playbook.yml",
        ])
        assert r.returncode == 0
        assert "@@" in r.stdout or "---" in r.stdout, \
            f"Expected unified diff output:\n{r.stdout[:500]}"

    def test_format_apply_then_check_passes(self, pod, tmp_path):
        """format --apply writes file; subsequent --check exits 0."""
        import shutil
        work = tmp_path / "fmt_test"
        work.mkdir()
        shutil.copy2(FORMAT_FIXTURE, work / "play.yml")
        r = _run([
            "podman", "run", "--rm", "--pod", POD_NAME,
            "-v", f"{work}:/workspace:Z",
            "-w", "/workspace",
            "--entrypoint", "apme-scan",
            CLI_IMAGE,
            "format", "--apply", "play.yml",
        ])
        assert r.returncode == 0, f"format --apply failed:\n{r.stderr}"

        r2 = _run([
            "podman", "run", "--rm", "--pod", POD_NAME,
            "-v", f"{work}:/workspace:ro,Z",
            "-w", "/workspace",
            "--entrypoint", "apme-scan",
            CLI_IMAGE,
            "format", "--check", "play.yml",
        ])
        assert r2.returncode == 0, f"format --check failed after --apply:\n{r2.stderr}"
