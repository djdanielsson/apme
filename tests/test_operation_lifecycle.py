"""Unit tests for the project operation lifecycle endpoints (findings #13-15)."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from apme_gateway.api.operation_router import operation_events
from apme_gateway.app import create_app
from apme_gateway.operation_registry import get_operation_registry
from apme_gateway.operation_types import OperationState, OperationStatus, Proposal

pytestmark = pytest.mark.usefixtures("gateway_db")


@pytest.fixture  # type: ignore[untyped-decorator]
async def client() -> AsyncIterator[AsyncClient]:
    """Build an async test client for the gateway app.

    Yields:
        AsyncClient: Configured HTTPX client targeting the in-process ASGI app.
    """
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _operation_url(project_id: str, suffix: str) -> str:
    """Build an operation endpoint URL for a project.

    Args:
        project_id: Target project UUID.
        suffix: Endpoint suffix starting with ``/``.

    Returns:
        Full operation endpoint path.
    """
    return f"/api/v1/projects/{project_id}/operation{suffix}"


def _setup_awaiting_approval(
    *,
    project_id: str = "proj-lifecycle-approve",
    scan_id: str = "scan-lifecycle-approve",
    operation_id: str = "op-lifecycle-approve",
) -> OperationState:
    """Register an operation waiting on proposal approval with two offers.

    Args:
        project_id: Owning project UUID.
        scan_id: Engine scan identifier.
        operation_id: Unique operation identifier.

    Returns:
        The registered operation state in ``AWAITING_APPROVAL``.
    """
    registry = get_operation_registry()
    state = registry.create(
        operation_id=operation_id,
        project_id=project_id,
        scan_id=scan_id,
        scan_type="remediate",
    )
    registry.set_proposals(
        operation_id,
        [
            Proposal(id="t1-aaa", rule_id="L001", file="a.yml"),
            Proposal(id="t1-bbb", rule_id="L002", file="b.yml"),
        ],
    )
    assert state.status == OperationStatus.AWAITING_APPROVAL
    return state


async def test_approve_ignores_unknown_ids(client: AsyncClient) -> None:
    """Unknown approve ids are ignored; the future resolves to offered ids only.

    Args:
        client: Async HTTPX test client.
    """
    project_id = "proj-lifecycle-approve"
    state = _setup_awaiting_approval(project_id=project_id)
    resp = await client.post(
        _operation_url(project_id, "/approve"),
        json={"approved_ids": ["t1-aaa", "zzz-unknown"]},
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "approved"}
    assert state.approval_future is not None
    assert state.approval_future.done()
    assert state.approval_future.result() == ["t1-aaa"]


async def test_cancel_active_operation(client: AsyncClient) -> None:
    """Cancel tears down the grpc task and resolves pending futures.

    Args:
        client: Async HTTPX test client.
    """
    project_id = "proj-lifecycle-cancel"
    registry = get_operation_registry()
    state = registry.create(
        operation_id="op-lifecycle-cancel",
        project_id=project_id,
        scan_id="scan-lifecycle-cancel",
        scan_type="remediate",
    )
    registry.transition(state.operation_id, OperationStatus.SCANNING)
    state.grpc_task = asyncio.create_task(asyncio.sleep(60))
    loop = asyncio.get_running_loop()
    state.approval_future = loop.create_future()

    resp = await client.post(_operation_url(project_id, "/cancel"))

    assert resp.status_code == 200
    assert resp.json() == {"status": "cancelled"}
    assert state.status == OperationStatus.CANCELLED
    assert state.grpc_task is not None
    with contextlib.suppress(asyncio.CancelledError):
        await state.grpc_task
    assert state.grpc_task.cancelled()
    assert state.approval_future is not None
    assert state.approval_future.done()
    assert state.approval_future.result() == []


async def test_cancel_terminal_operation_conflicts(client: AsyncClient) -> None:
    """Cancel on a terminal operation returns 409.

    Args:
        client: Async HTTPX test client.
    """
    project_id = "proj-lifecycle-cancel-terminal"
    registry = get_operation_registry()
    state = registry.create(
        operation_id="op-lifecycle-cancel-terminal",
        project_id=project_id,
        scan_id="scan-lifecycle-cancel-terminal",
        scan_type="check",
    )
    registry.transition(state.operation_id, OperationStatus.COMPLETED)
    resp = await client.post(_operation_url(project_id, "/cancel"))
    assert resp.status_code == 409


async def test_cancel_missing_operation_not_found(client: AsyncClient) -> None:
    """Cancel with no operation returns 404.

    Args:
        client: Async HTTPX test client.
    """
    resp = await client.post(_operation_url("proj-lifecycle-missing", "/cancel"))
    assert resp.status_code == 404


async def test_events_terminal_snapshot_then_close(client: AsyncClient) -> None:
    """A terminal operation yields a snapshot and closes immediately.

    Args:
        client: Async HTTPX test client.
    """
    project_id = "proj-lifecycle-events-terminal"
    registry = get_operation_registry()
    state = registry.create(
        operation_id="op-lifecycle-events-terminal",
        project_id=project_id,
        scan_id="scan-lifecycle-events-terminal",
        scan_type="check",
    )
    registry.transition(state.operation_id, OperationStatus.COMPLETED)

    async with client.stream("GET", _operation_url(project_id, "/events")) as resp:
        assert resp.status_code == 200
        body = await resp.aread()

    text = body.decode()
    assert "event: snapshot" in text
    assert OperationStatus.COMPLETED.value in text


async def test_events_missing_operation_not_found(client: AsyncClient) -> None:
    """Event stream with no operation returns 404.

    Args:
        client: Async HTTPX test client.
    """
    async with client.stream("GET", _operation_url("proj-lifecycle-events-missing", "/events")) as resp:
        assert resp.status_code == 404


def _canned_request() -> Request:
    """Build a Request whose disconnect probe always reports connected.

    Returns:
        Starlette request that never reports a client disconnect.
    """

    async def _receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    scope: dict[str, object] = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "server": ("test", 80),
        "scheme": "http",
        "client": ("test", 50000),
    }
    return Request(scope, _receive)


async def test_events_live_delta_then_terminal_close() -> None:
    """A live stream gets snapshot, delta, terminal close, and unsubscribes."""
    project_id = "proj-lifecycle-events-live"
    registry = get_operation_registry()
    state = registry.create(
        operation_id="op-lifecycle-events-live",
        project_id=project_id,
        scan_id="scan-lifecycle-events-live",
        scan_type="remediate",
    )
    registry.transition(state.operation_id, OperationStatus.SCANNING)

    resp = await operation_events(project_id, _canned_request())

    async def _collect() -> list[str]:
        out: list[str] = []
        async for chunk in resp.body_iterator:
            if isinstance(chunk, str):
                out.append(chunk)
            else:
                out.append(bytes(chunk).decode())
        return out

    collect_task = asyncio.create_task(_collect())
    try:
        async with asyncio.timeout(10):
            while not state.sse_subscribers:
                await asyncio.sleep(0.01)
        # Publish straight into the subscriber queue: flipping status first
        # would race the generator's terminal check right after the snapshot.
        state.sse_subscribers[0].put_nowait(
            {
                "event": "status_changed",
                "data": {"status": OperationStatus.CANCELLED.value},
            }
        )
        async with asyncio.timeout(10):
            chunks = await collect_task
    finally:
        if not collect_task.done():
            collect_task.cancel()

    text = "".join(chunks)
    assert "event: snapshot" in text
    assert "status_changed" in text
    assert OperationStatus.CANCELLED.value in text
    assert registry.get(state.operation_id) is not None
    assert registry.get(state.operation_id).sse_subscribers == []  # type: ignore[union-attr]


async def test_events_keepalive_on_queue_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queue timeouts yield keepalives; a terminal message closes the stream.

    Args:
        monkeypatch: Pytest fixture for patching asyncio.wait_for.
    """
    project_id = "proj-lifecycle-events-keepalive"
    registry = get_operation_registry()
    state = registry.create(
        operation_id="op-lifecycle-events-keepalive",
        project_id=project_id,
        scan_id="scan-lifecycle-events-keepalive",
        scan_type="remediate",
    )
    registry.transition(state.operation_id, OperationStatus.SCANNING)

    calls = 0

    async def _fake_wait_for(awaitable: object, timeout: float | None = None) -> object:
        nonlocal calls
        calls += 1
        if asyncio.iscoroutine(awaitable):
            awaitable.close()
        if calls <= 2:
            raise TimeoutError()
        return {
            "event": "status_changed",
            "data": {"status": OperationStatus.CANCELLED.value},
        }

    monkeypatch.setattr(asyncio, "wait_for", _fake_wait_for)
    resp = await operation_events(project_id, _canned_request())
    chunks: list[str] = []
    async for chunk in resp.body_iterator:
        if isinstance(chunk, str):
            chunks.append(chunk)
        else:
            chunks.append(bytes(chunk).decode())

    text = "".join(chunks)
    assert "event: snapshot" in text
    assert text.count(": keepalive") == 2
    assert "status_changed" in text
    assert calls == 3
    assert registry.get(state.operation_id) is not None
    assert registry.get(state.operation_id).sse_subscribers == []  # type: ignore[union-attr]
