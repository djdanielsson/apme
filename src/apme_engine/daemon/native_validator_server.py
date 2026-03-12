"""Native validator daemon: async gRPC server that runs in-tree Python rules on deserialized scandata."""

import asyncio
import json
import os
import sys
import time
from typing import Any

import grpc
import grpc.aio
import jsonpickle

from apme.v1 import validate_pb2, validate_pb2_grpc
from apme.v1.common_pb2 import HealthResponse, RuleTiming, ValidatorDiagnostics
from apme.v1.validate_pb2 import ValidateResponse
from apme_engine.daemon.violation_convert import violation_dict_to_proto
from apme_engine.validators.base import ScanContext
from apme_engine.validators.native import NativeRunResult, NativeValidator

_MAX_CONCURRENT_RPCS = int(os.environ.get("APME_NATIVE_MAX_RPCS", "32"))


def _run_native(hierarchy_payload: dict[str, Any], scandata: Any) -> NativeRunResult:
    """Blocking function: create ScanContext and run NativeValidator with timing."""
    scan_context = ScanContext(
        hierarchy_payload=hierarchy_payload,
        scandata=scandata,
    )
    validator = NativeValidator()
    return validator.run_with_timing(scan_context)


class NativeValidatorServicer(validate_pb2_grpc.ValidatorServicer):
    """Async gRPC adapter: deserializes scandata, runs native rules in executor."""

    async def Validate(self, request: Any, context: Any) -> ValidateResponse:
        req_id = request.request_id or ""
        t0 = time.monotonic()
        try:
            hierarchy_payload: dict[str, Any] = {}
            if request.hierarchy_payload:
                try:
                    hierarchy_payload = json.loads(request.hierarchy_payload)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    sys.stderr.write(f"[req={req_id}] Native: failed to decode hierarchy_payload\n")

            scandata = None
            if request.scandata:
                try:
                    scandata = jsonpickle.decode(request.scandata.decode("utf-8"))
                except Exception as e:
                    sys.stderr.write(f"[req={req_id}] Native: failed to decode scandata: {e}\n")
                    return ValidateResponse(violations=[], request_id=req_id)

            result = await asyncio.get_event_loop().run_in_executor(
                None,
                _run_native,
                hierarchy_payload,
                scandata,
            )
            total_ms = (time.monotonic() - t0) * 1000
            sys.stderr.write(f"[req={req_id}] Native: {len(result.violations)} violation(s) in {total_ms:.1f}ms\n")
            sys.stderr.flush()

            rule_timings = [
                RuleTiming(
                    rule_id=rt.rule_id,
                    elapsed_ms=rt.elapsed_ms,
                    violations=rt.violations,
                )
                for rt in result.rule_timings
            ]
            diag = ValidatorDiagnostics(
                validator_name="native",
                request_id=req_id,
                total_ms=total_ms,
                files_received=len(request.files),
                violations_found=len(result.violations),
                rule_timings=rule_timings,
            )

            return validate_pb2.ValidateResponse(
                violations=[violation_dict_to_proto(v) for v in result.violations],
                request_id=req_id,
                diagnostics=diag,
            )
        except Exception as e:
            import traceback

            sys.stderr.write(f"[req={req_id}] Native error: {e}\n")
            traceback.print_exc(file=sys.stderr)
            sys.stderr.flush()
            return ValidateResponse(violations=[], request_id=req_id)

    async def Health(self, request: Any, context: Any) -> HealthResponse:
        return HealthResponse(status="ok")


async def serve(listen: str = "0.0.0.0:50055") -> Any:
    """Create, bind, and start async gRPC server with Native servicer."""
    server = grpc.aio.server(maximum_concurrent_rpcs=_MAX_CONCURRENT_RPCS)
    validate_pb2_grpc.add_ValidatorServicer_to_server(NativeValidatorServicer(), server)  # type: ignore[no-untyped-call]
    if ":" in listen:
        _, _, port = listen.rpartition(":")
        server.add_insecure_port(f"[::]:{port}")
    else:
        server.add_insecure_port(listen)
    await server.start()
    return server
