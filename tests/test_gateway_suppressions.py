"""Unit tests for the gateway suppression endpoints (ADR-055)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from apme_gateway.app import create_app
from apme_gateway.db import close_db, init_db


@pytest.fixture(autouse=True)  # type: ignore[untyped-decorator]
async def _db(tmp_path: Path) -> AsyncIterator[None]:
    """Initialise a fresh DB per test.

    Args:
        tmp_path: Pytest-provided temporary directory.

    Yields:
        None: Test runs between setup and teardown.
    """
    await init_db(str(tmp_path / "test.db"))
    yield
    await close_db()


@pytest.fixture  # type: ignore[untyped-decorator]
async def client() -> AsyncIterator[AsyncClient]:
    """Build an async test client for the gateway app.

    Yields:
        AsyncClient: Client bound to the ASGI app.
    """
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_create_suppression_server_computed_fingerprint(client: AsyncClient) -> None:
    """POST /suppressions computes the canonical fingerprint when original_yaml is provided.

    Args:
        client: Async HTTP test client.
    """
    from apme_engine.fingerprint import compute_fingerprint

    resp = await client.post(
        "/api/v1/suppressions",
        json={
            "rule_id": "L001",
            "original_yaml": "- name: test task\n  debug:\n    msg: hello\n",
            "reason": "Not applicable",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    expected_fp = compute_fingerprint("L001", "- name: test task\n  debug:\n    msg: hello\n")
    assert body["fingerprint_hash"] == expected_fp
    assert body["rule_id"] == "L001"
    assert body["reason"] == "Not applicable"


async def test_create_suppression_client_hash_fallback(client: AsyncClient) -> None:
    """POST /suppressions accepts a pre-computed hash when original_yaml is absent.

    Args:
        client: Async HTTP test client.
    """
    resp = await client.post(
        "/api/v1/suppressions",
        json={
            "rule_id": "L002",
            "fingerprint_hash": "abcdef1234567890" * 4,
            "reason": "Legacy client",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["fingerprint_hash"] == "abcdef1234567890" * 4


async def test_create_suppression_duplicate_returns_409(client: AsyncClient) -> None:
    """POST /suppressions returns 409 on duplicate fingerprint+scope.

    Args:
        client: Async HTTP test client.
    """
    payload = {
        "rule_id": "L001",
        "original_yaml": "- name: dup\n  debug:\n    msg: hi\n",
        "reason": "first",
    }
    resp1 = await client.post("/api/v1/suppressions", json=payload)
    assert resp1.status_code == 201

    resp2 = await client.post("/api/v1/suppressions", json=payload)
    assert resp2.status_code == 409


async def test_create_suppression_requires_hash_or_yaml(client: AsyncClient) -> None:
    """POST /suppressions returns 422 when neither hash nor original_yaml is provided.

    Args:
        client: Async HTTP test client.
    """
    resp = await client.post(
        "/api/v1/suppressions",
        json={"rule_id": "L001", "reason": "nothing"},
    )
    assert resp.status_code == 422


async def test_list_suppressions(client: AsyncClient) -> None:
    """GET /suppressions returns created records.

    Args:
        client: Async HTTP test client.
    """
    await client.post(
        "/api/v1/suppressions",
        json={"rule_id": "L001", "original_yaml": "x: 1\n", "scope": "global", "reason": "a"},
    )
    await client.post(
        "/api/v1/suppressions",
        json={"rule_id": "L002", "original_yaml": "y: 2\n", "scope": "project:abc", "reason": "b"},
    )

    resp = await client.get("/api/v1/suppressions")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp_scoped = await client.get("/api/v1/suppressions?scope=global")
    assert resp_scoped.status_code == 200
    assert len(resp_scoped.json()) == 1


async def test_delete_suppression(client: AsyncClient) -> None:
    """DELETE /suppressions/{id} removes the record.

    Args:
        client: Async HTTP test client.
    """
    create_resp = await client.post(
        "/api/v1/suppressions",
        json={"rule_id": "L001", "original_yaml": "z: 3\n", "reason": "temp"},
    )
    suppression_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/v1/suppressions/{suppression_id}")
    assert del_resp.status_code == 204

    list_resp = await client.get("/api/v1/suppressions")
    assert len(list_resp.json()) == 0


async def test_fingerprint_matches_engine_module(client: AsyncClient) -> None:
    """Server fingerprint is identical to apme_engine.fingerprint.compute_fingerprint.

    Args:
        client: Async HTTP test client.
    """
    from apme_engine.fingerprint import compute_fingerprint

    yaml_content = "- name: Install packages\n  ansible.builtin.dnf:\n    name: httpd\n"
    resp = await client.post(
        "/api/v1/suppressions",
        json={"rule_id": "native:M005", "original_yaml": yaml_content, "reason": "test"},
    )
    assert resp.status_code == 201
    assert resp.json()["fingerprint_hash"] == compute_fingerprint("native:M005", yaml_content)


async def test_create_suppression_invalid_mode_returns_422(client: AsyncClient) -> None:
    """POST /suppressions returns 422 for invalid fingerprint_mode.

    Args:
        client: Async HTTP test client.
    """
    resp = await client.post(
        "/api/v1/suppressions",
        json={
            "rule_id": "L001",
            "original_yaml": "x: 1\n",
            "fingerprint_mode": "bogus",
            "reason": "test",
        },
    )
    assert resp.status_code == 422


async def test_create_suppression_rule_module_without_fqcn_returns_422(client: AsyncClient) -> None:
    """POST /suppressions returns 422 when rule_module mode lacks module_fqcn.

    Args:
        client: Async HTTP test client.
    """
    resp = await client.post(
        "/api/v1/suppressions",
        json={
            "rule_id": "L001",
            "original_yaml": "x: 1\n",
            "fingerprint_mode": "rule_module",
            "reason": "test",
        },
    )
    assert resp.status_code == 422
