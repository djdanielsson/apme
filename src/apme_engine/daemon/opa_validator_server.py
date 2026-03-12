"""OPA validator daemon: async gRPC wrapper over OPA REST API (localhost:8181)."""

import json
import os
import sys
import time
from typing import Any

import grpc
import grpc.aio
import httpx

from apme.v1 import validate_pb2, validate_pb2_grpc
from apme.v1.common_pb2 import HealthResponse, RuleTiming, ValidatorDiagnostics
from apme.v1.validate_pb2 import ValidateResponse
from apme_engine.daemon.violation_convert import violation_dict_to_proto

OPA_REST_URL = os.environ.get("APME_OPA_REST_URL", "http://localhost:8181")
OPA_VIOLATIONS_ENDPOINT = "/v1/data/apme/rules/violations"

_MAX_CONCURRENT_RPCS = int(os.environ.get("APME_OPA_MAX_RPCS", "32"))


class OpaValidatorServicer(validate_pb2_grpc.ValidatorServicer):
    """Async gRPC facade: translates Validate RPCs into OPA REST queries via httpx."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)

    async def Validate(self, request: Any, context: Any) -> validate_pb2.ValidateResponse:
        req_id = request.request_id or ""
        t0 = time.monotonic()
        violations: list[dict[str, Any]] = []
        opa_query_ms = 0.0
        opa_response_size = 0
        try:
            hierarchy_payload: dict[str, Any] = {}
            if request.hierarchy_payload:
                try:
                    hierarchy_payload = json.loads(request.hierarchy_payload)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    sys.stderr.write(f"[req={req_id}] OPA: failed to decode hierarchy_payload\n")
                    return ValidateResponse(violations=[], request_id=req_id)

            url = f"{OPA_REST_URL}{OPA_VIOLATIONS_ENDPOINT}"
            tq = time.monotonic()
            r = await self._client.post(url, json={"input": hierarchy_payload})
            opa_query_ms = (time.monotonic() - tq) * 1000
            opa_response_size = len(r.content)

            if r.status_code != 200:
                sys.stderr.write(f"[req={req_id}] OPA returned HTTP {r.status_code}\n")
                sys.stderr.flush()
                return ValidateResponse(violations=[], request_id=req_id)

            data = r.json()
            result = data.get("result", [])
            violations = result if isinstance(result, list) else []
            total_ms = (time.monotonic() - t0) * 1000
            sys.stderr.write(f"[req={req_id}] OPA: {len(violations)} violation(s) in {total_ms:.1f}ms\n")
            sys.stderr.flush()
        except Exception as e:
            sys.stderr.write(f"[req={req_id}] OPA error: {e}\n")
            sys.stderr.flush()
            return ValidateResponse(violations=[], request_id=req_id)

        total_ms = (time.monotonic() - t0) * 1000

        from collections import Counter

        rule_counts = Counter(v.get("rule_id", "unknown") for v in violations)
        rule_timings = [
            RuleTiming(rule_id="opa_query", elapsed_ms=opa_query_ms, violations=len(violations)),
        ]
        for rid, count in sorted(rule_counts.items()):
            rule_timings.append(RuleTiming(rule_id=rid, elapsed_ms=0.0, violations=count))

        diag = ValidatorDiagnostics(
            validator_name="opa",
            request_id=req_id,
            total_ms=total_ms,
            files_received=len(request.files),
            violations_found=len(violations),
            rule_timings=rule_timings,
            metadata={
                "opa_query_ms": f"{opa_query_ms:.1f}",
                "opa_response_size": str(opa_response_size),
            },
        )

        return ValidateResponse(
            violations=[violation_dict_to_proto(v) for v in violations],
            request_id=req_id,
            diagnostics=diag,
        )

    async def Health(self, request: Any, context: Any) -> HealthResponse:
        try:
            r = await self._client.get(f"{OPA_REST_URL}/health")
            if r.status_code == 200:
                return HealthResponse(status="ok")
            return HealthResponse(status=f"opa unhealthy: HTTP {r.status_code}")
        except Exception as e:
            return HealthResponse(status=f"opa unreachable: {e}")


async def serve(listen: str = "0.0.0.0:50054") -> Any:
    """Create, bind, and start async gRPC server with OPA servicer."""
    server = grpc.aio.server(maximum_concurrent_rpcs=_MAX_CONCURRENT_RPCS)
    validate_pb2_grpc.add_ValidatorServicer_to_server(OpaValidatorServicer(), server)  # type: ignore[no-untyped-call]
    if ":" in listen:
        _, _, port = listen.rpartition(":")
        server.add_insecure_port(f"[::]:{port}")
    else:
        server.add_insecure_port(listen)
    await server.start()
    return server
