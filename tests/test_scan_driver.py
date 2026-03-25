"""Unit tests for the gateway project scan driver (ADR-037)."""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apme_gateway.scan.driver import clone_repo, derive_session_id, run_project_scan


def test_derive_session_id_deterministic() -> None:
    """Same project ID always produces the same session ID."""
    sid1 = derive_session_id("project-abc")
    sid2 = derive_session_id("project-abc")
    assert sid1 == sid2
    assert len(sid1) == 16


def test_derive_session_id_different_projects() -> None:
    """Different project IDs produce different session IDs."""
    sid1 = derive_session_id("project-a")
    sid2 = derive_session_id("project-b")
    assert sid1 != sid2


@pytest.mark.asyncio  # type: ignore[untyped-decorator]
async def test_clone_repo_success() -> None:
    """Verify clone_repo succeeds when git returns 0."""
    with patch("apme_gateway.scan.driver.asyncio.get_running_loop") as mock_loop:
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        mock_loop.return_value.run_in_executor = AsyncMock(return_value=result)

        with tempfile.TemporaryDirectory() as td:
            dest = os.path.join(td, "repo")
            await clone_repo("https://github.com/test/repo.git", "main", dest)


@pytest.mark.asyncio  # type: ignore[untyped-decorator]
async def test_clone_repo_failure() -> None:
    """Verify clone_repo raises RuntimeError when git fails."""
    with patch("apme_gateway.scan.driver.asyncio.get_running_loop") as mock_loop:
        result = MagicMock()
        result.returncode = 128
        result.stderr = "fatal: repository not found"
        mock_loop.return_value.run_in_executor = AsyncMock(return_value=result)

        with tempfile.TemporaryDirectory() as td:
            dest = os.path.join(td, "repo")
            with pytest.raises(RuntimeError, match="git clone failed"):
                await clone_repo("https://github.com/bad/repo.git", "main", dest)


async def _async_iter(
    items: list[object],
) -> AsyncIterator[object]:
    """Wrap items into an async iterator for mocking gRPC streams.

    Args:
        items: Objects to yield.

    Yields:
        object: Each item in sequence.
    """
    for item in items:
        yield item


@pytest.mark.asyncio  # type: ignore[untyped-decorator]
async def test_run_project_scan_full_flow() -> None:
    """Verify run_project_scan clones, chunks, and streams to Primary."""
    mock_chunks = [MagicMock()]

    progress_events: list[object] = []

    async def track_progress(event: object) -> None:
        progress_events.append(event)

    with (
        patch("apme_gateway.scan.driver.clone_repo", new_callable=AsyncMock) as mock_clone,
        patch("apme_gateway.scan.driver.yield_scan_chunks", return_value=mock_chunks),
        patch("apme_gateway.scan.driver.grpc.aio.insecure_channel") as mock_channel_cls,
    ):
        mock_result = MagicMock()
        mock_result.summary.total = 5
        mock_result.summary.auto_fixable = 2

        mock_event = MagicMock()
        mock_event.HasField.return_value = True
        mock_event.result = mock_result

        mock_stub = MagicMock()
        mock_stub.ScanStream.return_value = _async_iter([mock_event])

        mock_channel = MagicMock()
        mock_channel.close = AsyncMock()
        mock_channel_cls.return_value = mock_channel

        with patch(
            "apme_gateway.scan.driver.primary_pb2_grpc.PrimaryStub",
            return_value=mock_stub,
        ):
            scan_id, result = await run_project_scan(
                project_id="test-proj",
                repo_url="https://github.com/test/repo.git",
                branch="main",
                primary_address="127.0.0.1:50051",
                progress_callback=track_progress,
            )

        mock_clone.assert_called_once()
        assert scan_id is not None
        assert len(scan_id) == 32
        assert result is not None
