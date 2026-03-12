"""Health check for APME services: Primary, Native, OPA, Ansible, Cache maintainer (all gRPC)."""

import os
import time
from collections.abc import Callable
from typing import Any

import grpc

from apme.v1 import cache_pb2_grpc, common_pb2, primary_pb2_grpc, validate_pb2_grpc


def _derive_addresses(primary_addr: str) -> dict[str, str]:
    """From primary host:port derive default addresses for all services."""
    if ":" in primary_addr:
        host, _ = primary_addr.rsplit(":", 1)
    else:
        host = primary_addr
    return {
        "primary": primary_addr,
        "native": f"{host}:50055",
        "opa": f"{host}:50054",
        "ansible": f"{host}:50053",
        "cache_maintainer": f"{host}:50052",
    }


def check_grpc_health(addr: str, stub_factory: Callable[..., Any], timeout: float = 5.0) -> dict[str, Any]:
    """Call Health RPC on a gRPC service; return {ok, status, error, latency_ms}."""
    start = time.perf_counter()
    try:
        channel = grpc.insecure_channel(addr)
        stub = stub_factory(channel)
        req = common_pb2.HealthRequest()
        resp = stub.Health(req, timeout=timeout)
        channel.close()
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "ok": (resp.status or "").strip().lower() == "ok",
            "status": resp.status or "ok",
            "error": None,
            "latency_ms": round(elapsed_ms, 2),
        }
    except grpc.RpcError as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "ok": False,
            "status": None,
            "error": e.details() or str(e.code()),
            "latency_ms": round(elapsed_ms, 2),
        }
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "ok": False,
            "status": None,
            "error": str(e),
            "latency_ms": round(elapsed_ms, 2),
        }


def run_health_checks(
    primary_addr: str,
    native_addr: str | None = None,
    opa_addr: str | None = None,
    ansible_addr: str | None = None,
    cache_addr: str | None = None,
    timeout: float = 5.0,
    # Legacy parameter kept for backward compatibility (ignored)
    opa_url: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Run all health checks. Addresses not provided are derived from primary_addr."""
    defaults = _derive_addresses(primary_addr)
    native_addr = native_addr or os.environ.get("NATIVE_GRPC_ADDRESS") or defaults["native"]
    opa_addr = opa_addr or os.environ.get("OPA_GRPC_ADDRESS") or defaults["opa"]
    ansible_addr = ansible_addr or os.environ.get("ANSIBLE_GRPC_ADDRESS") or defaults["ansible"]
    cache_addr = cache_addr or os.environ.get("APME_CACHE_GRPC_ADDRESS") or defaults["cache_maintainer"]

    results = {}
    results["primary"] = check_grpc_health(primary_addr, primary_pb2_grpc.PrimaryStub, timeout)
    results["native"] = check_grpc_health(native_addr, validate_pb2_grpc.ValidatorStub, timeout)
    results["opa"] = check_grpc_health(opa_addr, validate_pb2_grpc.ValidatorStub, timeout)
    results["ansible"] = check_grpc_health(ansible_addr, validate_pb2_grpc.ValidatorStub, timeout)
    results["cache_maintainer"] = check_grpc_health(cache_addr, cache_pb2_grpc.CacheMaintainerStub, timeout)
    return results
