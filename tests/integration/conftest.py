"""Integration test infrastructure: daemon + galaxy proxy lifecycle.

Starts a galaxy proxy (for collection installs) and the local APME daemon
(Primary + Native + OPA + Ansible) when integration-marked tests are
collected, and tears both down in ``pytest_sessionfinish``.

Run with::

    pytest -m integration tests/integration/ -v
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import pytest

LOGGER = logging.getLogger(__name__)

_ENV_KEYS = (
    "APME_DATA_DIR",
    "APME_PRIMARY_ADDRESS",
    "APME_GALAXY_PROXY_URL",
    "OPA_USE_PODMAN",
)


@dataclass
class Infrastructure:
    """Holds daemon and proxy state for restoration on teardown.

    Attributes:
        primary_address: gRPC address of the Primary service.
        data_dir: Temporary directory used for daemon state isolation.
        proxy_process: Galaxy proxy subprocess (terminated on teardown).
        original_env: Snapshot of env vars before daemon start.
    """

    primary_address: str = ""
    data_dir: str = ""
    proxy_process: subprocess.Popen[bytes] | None = None
    original_env: dict[str, str | None] = field(default_factory=dict)


INFRASTRUCTURE: Infrastructure | None = None


def _free_port() -> int:
    """Find a free TCP port on localhost.

    Returns:
        Available port number.
    """
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_for_port(port: int, timeout: float = 15.0) -> bool:
    """Block until a TCP port is accepting connections.

    Args:
        port: Port number to probe.
        timeout: Maximum seconds to wait.

    Returns:
        True if port became reachable, False on timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Start proxy + daemon if integration-marked tests will actually run.

    This hook fires *before* pytest applies ``-m`` deselection, so we must
    check ``markexpr`` ourselves to avoid starting infrastructure when the
    session runs with ``-m 'not integration'`` (the default addopts).

    Args:
        config: Pytest config object.
        items: Collected test items (before marker-based deselection).
    """
    if config.option.collectonly:
        return
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return
    markexpr = getattr(config.option, "markexpr", "") or ""
    if "not integration" in markexpr:
        return
    has_integration = any(item.get_closest_marker("integration") for item in items)
    if has_integration and INFRASTRUCTURE is None:
        _start_infrastructure()


def pytest_sessionfinish(session: pytest.Session) -> None:
    """Stop daemon and proxy, restore environment.

    Args:
        session: Pytest session (unused beyond signature).
    """
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return
    _stop_infrastructure()


def _start_infrastructure() -> None:
    """Start galaxy proxy, then fork the daemon with all validators."""
    global INFRASTRUCTURE  # noqa: PLW0603

    from apme_engine.daemon.launcher import start_daemon

    original_env = {k: os.environ.get(k) for k in _ENV_KEYS}
    data_dir = tempfile.mkdtemp(prefix="apme-integration-")

    proxy_port = _free_port()
    proxy_proc = subprocess.Popen(
        [sys.executable, "-m", "galaxy_proxy.cli", "--host", "127.0.0.1", "--port", str(proxy_port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if not _wait_for_port(proxy_port):
        proxy_proc.terminate()
        proxy_proc.wait(timeout=5)
        stderr = proxy_proc.stderr.read().decode() if proxy_proc.stderr else ""
        pytest.exit(f"Galaxy proxy did not start on port {proxy_port}: {stderr}", returncode=2)
        return

    proxy_url = f"http://127.0.0.1:{proxy_port}"
    LOGGER.warning("Galaxy proxy ready at %s (pid %d)", proxy_url, proxy_proc.pid)

    os.environ["APME_DATA_DIR"] = data_dir
    os.environ["APME_GALAXY_PROXY_URL"] = proxy_url
    os.environ["OPA_USE_PODMAN"] = "0"

    LOGGER.warning("Starting APME daemon (data_dir=%s)", data_dir)

    try:
        state = start_daemon(include_optional=True)
    except RuntimeError as exc:
        proxy_proc.terminate()
        proxy_proc.wait(timeout=5)
        _restore_env(original_env)
        pytest.exit(f"Failed to start daemon: {exc}", returncode=2)
        return

    os.environ["APME_PRIMARY_ADDRESS"] = state.primary
    LOGGER.warning("APME daemon ready at %s (pid %d)", state.primary, state.pid)

    INFRASTRUCTURE = Infrastructure(
        primary_address=state.primary,
        data_dir=data_dir,
        proxy_process=proxy_proc,
        original_env=original_env,
    )


def _stop_infrastructure() -> None:
    """Stop daemon and proxy, restore saved environment variables."""
    global INFRASTRUCTURE  # noqa: PLW0603

    if INFRASTRUCTURE is None:
        return

    from apme_engine.daemon.launcher import stop_daemon

    LOGGER.warning("Stopping APME daemon")
    try:
        stop_daemon()
    except Exception:
        LOGGER.exception("Error stopping daemon")

    if INFRASTRUCTURE.proxy_process is not None:
        LOGGER.warning("Stopping galaxy proxy")
        INFRASTRUCTURE.proxy_process.terminate()
        try:
            INFRASTRUCTURE.proxy_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            INFRASTRUCTURE.proxy_process.kill()

    _restore_env(INFRASTRUCTURE.original_env)
    INFRASTRUCTURE = None


def _restore_env(saved: dict[str, str | None]) -> None:
    """Restore environment variables from a saved snapshot.

    Args:
        saved: Map of env var name to original value (None means unset).
    """
    for key, val in saved.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


@pytest.fixture(scope="session")  # type: ignore[untyped-decorator]
def infrastructure() -> Infrastructure:
    """Provide the daemon infrastructure to tests.

    Returns:
        Infrastructure dataclass with daemon addresses and state.
    """
    assert INFRASTRUCTURE is not None, "Daemon not started. Run with: pytest -m integration"
    return INFRASTRUCTURE


FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "terrible-playbook"


@pytest.fixture(scope="session")  # type: ignore[untyped-decorator]
def fixture_dir() -> Path:
    """Path to the terrible-playbook fixture directory.

    Returns:
        Resolved Path to the fixture.
    """
    return FIXTURE_DIR
