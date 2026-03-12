"""Primary daemon: async gRPC server that runs engine then fans out to all validators."""

import asyncio
import contextlib
import json
import os
import shutil
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import grpc
import grpc.aio
import jsonpickle

from apme.v1 import primary_pb2, primary_pb2_grpc, validate_pb2_grpc
from apme.v1.common_pb2 import HealthResponse, ValidatorDiagnostics
from apme.v1.primary_pb2 import FileDiff, FormatResponse, ScanDiagnostics, ScanResponse
from apme.v1.validate_pb2 import ValidateRequest
from apme_engine.daemon.violation_convert import violation_proto_to_dict
from apme_engine.runner import run_scan

_MAX_CONCURRENT_RPCS = int(os.environ.get("APME_PRIMARY_MAX_RPCS", "16"))


@dataclass
class _ValidatorResult:
    violations: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: ValidatorDiagnostics | None = None


def _sort_violations(violations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(v: dict[str, Any]) -> tuple[str, int | float]:
        f = v.get("file") or ""
        line = v.get("line")
        if isinstance(line, (list, tuple)) and line:
            line = line[0]
        if not isinstance(line, (int, float)):
            line = 0
        return (f, line)

    return sorted(violations, key=key)


def _deduplicate_violations(violations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate violations sharing the same (rule_id, file, line)."""
    seen: set[tuple[str, str, Any]] = set()
    out: list[dict[str, Any]] = []
    for v in violations:
        line = v.get("line")
        if isinstance(line, (list, tuple)):
            line = tuple(line)
        key = (v.get("rule_id", ""), v.get("file", ""), line)
        if key not in seen:
            seen.add(key)
            out.append(v)
    return out


def _write_chunked_fs(project_root: str, files: list[Any]) -> Path:
    """Write request.files into a temp directory; return path to that directory."""
    tmp = Path(tempfile.mkdtemp(prefix="apme_primary_"))
    for f in files:
        path = tmp / f.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f.content)
    return tmp


async def _call_validator(
    address: str,
    request: ValidateRequest,
    timeout: int = 60,
) -> _ValidatorResult:
    """Call a validator over async gRPC; return violations + diagnostics."""
    req_id = request.request_id or ""
    channel = grpc.aio.insecure_channel(address)
    stub = validate_pb2_grpc.ValidatorStub(channel)  # type: ignore[no-untyped-call]
    try:
        resp = await stub.Validate(request, timeout=timeout)
        return _ValidatorResult(
            violations=[violation_proto_to_dict(v) for v in resp.violations],
            diagnostics=resp.diagnostics if resp.HasField("diagnostics") else None,
        )
    except grpc.RpcError as e:
        sys.stderr.write(f"[req={req_id}] Validator at {address} failed: {e}\n")
        sys.stderr.flush()
        return _ValidatorResult()
    finally:
        await channel.close(grace=None)


VALIDATOR_ENV_VARS = {
    "native": "NATIVE_GRPC_ADDRESS",
    "opa": "OPA_GRPC_ADDRESS",
    "ansible": "ANSIBLE_GRPC_ADDRESS",
    "gitleaks": "GITLEAKS_GRPC_ADDRESS",
}


class PrimaryServicer(primary_pb2_grpc.PrimaryServicer):
    async def Scan(self, request: Any, context: Any) -> primary_pb2.ScanResponse:
        scan_id = request.scan_id or str(uuid.uuid4())
        violations: list[dict[str, Any]] = []
        temp_dir = None
        scan_t0 = time.monotonic()

        try:
            sys.stderr.write(f"[req={scan_id}] Scan: received {len(request.files)} file(s)\n")
            sys.stderr.flush()

            if not request.files:
                return ScanResponse(scan_id=scan_id, violations=[])

            temp_dir = await asyncio.get_event_loop().run_in_executor(
                None,
                _write_chunked_fs,
                request.project_root or "project",
                list(request.files),
            )
            target = str(temp_dir)
            project_root = target

            engine_t0 = time.monotonic()
            context_obj = await asyncio.get_event_loop().run_in_executor(
                None,
                run_scan,
                target,
                project_root,
                True,
            )
            (time.monotonic() - engine_t0) * 1000

            if not context_obj.hierarchy_payload:
                sys.stderr.write(f"[req={scan_id}] Scan: no hierarchy payload produced\n")
                sys.stderr.flush()
                return ScanResponse(scan_id=scan_id, violations=[])

            opts = request.options if request.HasField("options") else None
            validate_request = ValidateRequest(
                request_id=scan_id,
                project_root=request.project_root or "",
                files=list(request.files),
                hierarchy_payload=json.dumps(context_obj.hierarchy_payload).encode(),
                scandata=jsonpickle.encode(context_obj.scandata).encode(),
                ansible_core_version=opts.ansible_core_version if opts else "",
                collection_specs=list(opts.collection_specs) if opts else [],
            )

            tasks = {}
            for name, env_var in VALIDATOR_ENV_VARS.items():
                addr = os.environ.get(env_var)
                if not addr:
                    continue
                tasks[name] = _call_validator(addr, validate_request)

            validator_diagnostics: list[ValidatorDiagnostics] = []

            fan_out_ms = 0.0
            if tasks:
                fan_t0 = time.monotonic()
                results = await asyncio.gather(*tasks.values(), return_exceptions=True)
                fan_out_ms = (time.monotonic() - fan_t0) * 1000

                counts: dict[str, int] = {}
                for name, result in zip(tasks.keys(), results, strict=False):
                    if isinstance(result, BaseException):
                        sys.stderr.write(f"[req={scan_id}] {name} raised: {result}\n")
                        sys.stderr.flush()
                        counts[name] = 0
                    else:
                        res = result
                        counts[name] = len(res.violations)
                        violations.extend(res.violations)
                        if res.diagnostics:
                            validator_diagnostics.append(res.diagnostics)

                parts = " ".join(f"{n.title()}={counts.get(n, 0)}" for n in VALIDATOR_ENV_VARS)
                sys.stderr.write(f"[req={scan_id}] Scan: {parts} Total={len(violations)}\n")
                sys.stderr.flush()

            violations = _deduplicate_violations(_sort_violations(violations))
            from apme_engine.daemon.violation_convert import violation_dict_to_proto

            proto_violations = [violation_dict_to_proto(v) for v in violations]

            total_ms = (time.monotonic() - scan_t0) * 1000
            ediag = context_obj.engine_diagnostics
            scan_diag = ScanDiagnostics(
                engine_parse_ms=ediag.parse_ms,
                engine_annotate_ms=ediag.annotate_ms,
                engine_total_ms=ediag.total_ms,
                files_scanned=ediag.files_scanned,
                trees_built=ediag.trees_built,
                total_violations=len(violations),
                validators=validator_diagnostics,
                fan_out_ms=fan_out_ms,
                total_ms=total_ms,
            )

            return ScanResponse(
                violations=proto_violations,
                scan_id=scan_id,
                diagnostics=scan_diag,
            )
        except Exception as e:
            import traceback

            sys.stderr.write(f"[req={scan_id}] Scan failed: {e}\n")
            traceback.print_exc(file=sys.stderr)
            sys.stderr.flush()
            raise
        finally:
            if temp_dir is not None and temp_dir.is_dir():
                with contextlib.suppress(OSError):
                    shutil.rmtree(temp_dir)

    async def Format(self, request: Any, context: Any) -> FormatResponse:
        from apme_engine.formatter import format_content

        sys.stderr.write(f"Format: received {len(request.files)} file(s)\n")
        sys.stderr.flush()

        def _do_format(files: list[Any]) -> list[Any]:
            diffs = []
            for f in files:
                if not f.path.endswith((".yml", ".yaml")):
                    continue
                try:
                    text = f.content.decode("utf-8")
                except UnicodeDecodeError:
                    continue
                result = format_content(text, filename=f.path)
                if result.changed:
                    diffs.append(
                        FileDiff(
                            path=f.path,
                            original=f.content,
                            formatted=result.formatted.encode("utf-8"),
                            diff=result.diff,
                        )
                    )
            return diffs

        diffs = await asyncio.get_event_loop().run_in_executor(
            None,
            _do_format,
            list(request.files),
        )

        sys.stderr.write(f"Format: {len(diffs)} file(s) changed\n")
        sys.stderr.flush()
        return FormatResponse(diffs=diffs)

    async def Health(self, request: Any, context: Any) -> HealthResponse:
        return HealthResponse(status="ok")


async def serve(listen_address: str = "0.0.0.0:50051") -> Any:
    server = grpc.aio.server(maximum_concurrent_rpcs=_MAX_CONCURRENT_RPCS)
    primary_pb2_grpc.add_PrimaryServicer_to_server(PrimaryServicer(), server)  # type: ignore[no-untyped-call]
    if ":" in listen_address:
        _, _, port = listen_address.rpartition(":")
        server.add_insecure_port(f"[::]:{port}")
    else:
        server.add_insecure_port(listen_address)
    await server.start()
    return server
