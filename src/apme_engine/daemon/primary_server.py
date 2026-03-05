"""Primary daemon: gRPC server that runs engine then fans out to all validators via unified Validator contract."""

import json
import os
import sys
import tempfile
from concurrent import futures
from pathlib import Path

import grpc
import jsonpickle
from apme.v1 import primary_pb2, primary_pb2_grpc, validate_pb2, validate_pb2_grpc, common_pb2

from apme_engine.runner import run_scan
from apme_engine.daemon.violation_convert import violation_proto_to_dict


def _sort_violations(violations: list[dict]) -> list[dict]:
    def key(v):
        f = v.get("file") or ""
        line = v.get("line")
        if isinstance(line, (list, tuple)) and line:
            line = line[0]
        if not isinstance(line, (int, float)):
            line = 0
        return (f, line)
    return sorted(violations, key=key)


def _deduplicate_violations(violations: list[dict]) -> list[dict]:
    """Remove duplicate violations sharing the same (rule_id, file, line)."""
    seen: set[tuple] = set()
    out: list[dict] = []
    for v in violations:
        line = v.get("line")
        if isinstance(line, (list, tuple)):
            line = tuple(line)
        key = (v.get("rule_id", ""), v.get("file", ""), line)
        if key not in seen:
            seen.add(key)
            out.append(v)
    return out


def _write_chunked_fs(project_root: str, files: list) -> Path:
    """Write request.files into a temp directory; return path to that directory."""
    tmp = Path(tempfile.mkdtemp(prefix="apme_primary_"))
    for f in files:
        path = tmp / f.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f.content)
    return tmp


def _call_validator(address: str, request: validate_pb2.ValidateRequest, timeout: int = 60) -> list[dict]:
    """Call any validator over gRPC using the unified Validator service; return violation dicts."""
    channel = grpc.insecure_channel(address)
    stub = validate_pb2_grpc.ValidatorStub(channel)
    try:
        resp = stub.Validate(request, timeout=timeout)
        return [violation_proto_to_dict(v) for v in resp.violations]
    except grpc.RpcError as e:
        sys.stderr.write(f"Validator at {address} failed: {e}\n")
        return []
    finally:
        channel.close()


VALIDATOR_ENV_VARS = {
    "native": "NATIVE_GRPC_ADDRESS",
    "opa": "OPA_GRPC_ADDRESS",
    "ansible": "ANSIBLE_GRPC_ADDRESS",
    "gitleaks": "GITLEAKS_GRPC_ADDRESS",
}


class PrimaryServicer(primary_pb2_grpc.PrimaryServicer):
    def Scan(self, request, context):
        scan_id = request.scan_id or ""
        violations: list[dict] = []
        temp_dir = None

        try:
            sys.stderr.write(f"Scan {scan_id}: received {len(request.files)} file(s)\n")
            sys.stderr.flush()

            if not request.files:
                return primary_pb2.ScanResponse(
                    scan_id=scan_id,
                    violations=[],
                )
            temp_dir = _write_chunked_fs(request.project_root or "project", request.files)
            target = str(temp_dir)
            project_root = target
            context_obj = run_scan(target, project_root, include_scandata=True)

            if not context_obj.hierarchy_payload:
                sys.stderr.write(f"Scan {scan_id}: no hierarchy payload produced\n")
                sys.stderr.flush()
                return primary_pb2.ScanResponse(scan_id=scan_id, violations=[])

            opts = request.options if request.HasField("options") else None
            validate_request = validate_pb2.ValidateRequest(
                project_root=request.project_root or "",
                files=list(request.files),
                hierarchy_payload=json.dumps(context_obj.hierarchy_payload).encode(),
                scandata=jsonpickle.encode(context_obj.scandata).encode(),
                ansible_core_version=opts.ansible_core_version if opts else "",
                collection_specs=list(opts.collection_specs) if opts else [],
            )

            counts: dict[str, int] = {}
            validator_tasks = {}
            with futures.ThreadPoolExecutor(max_workers=len(VALIDATOR_ENV_VARS)) as pool:
                for name, env_var in VALIDATOR_ENV_VARS.items():
                    addr = os.environ.get(env_var)
                    if not addr:
                        counts[name] = 0
                        continue
                    validator_tasks[pool.submit(_call_validator, addr, validate_request)] = name

                for fut in futures.as_completed(validator_tasks):
                    name = validator_tasks[fut]
                    result = fut.result()
                    counts[name] = len(result)
                    violations.extend(result)

            parts = " ".join(f"{n.title()}={counts[n]}" for n in VALIDATOR_ENV_VARS)
            sys.stderr.write(f"Scan {scan_id}: {parts} Total={len(violations)}\n")
            sys.stderr.flush()

            violations = _deduplicate_violations(_sort_violations(violations))
            from apme_engine.daemon.violation_convert import violation_dict_to_proto
            proto_violations = [violation_dict_to_proto(v) for v in violations]

            return primary_pb2.ScanResponse(
                violations=proto_violations,
                scan_id=scan_id,
            )
        except Exception as e:
            import traceback
            sys.stderr.write(f"Scan {scan_id} failed: {e}\n")
            traceback.print_exc(file=sys.stderr)
            sys.stderr.flush()
            raise
        finally:
            if temp_dir is not None and temp_dir.is_dir():
                import shutil
                try:
                    shutil.rmtree(temp_dir)
                except OSError:
                    pass

    def Format(self, request, context):
        from apme_engine.formatter import format_content

        sys.stderr.write(f"Format: received {len(request.files)} file(s)\n")
        sys.stderr.flush()

        diffs = []
        for f in request.files:
            if not f.path.endswith((".yml", ".yaml")):
                continue
            try:
                text = f.content.decode("utf-8")
            except UnicodeDecodeError:
                continue
            result = format_content(text, filename=f.path)
            if result.changed:
                diffs.append(primary_pb2.FileDiff(
                    path=f.path,
                    original=f.content,
                    formatted=result.formatted.encode("utf-8"),
                    diff=result.diff,
                ))

        sys.stderr.write(f"Format: {len(diffs)} file(s) changed\n")
        sys.stderr.flush()
        return primary_pb2.FormatResponse(diffs=diffs)

    def Health(self, request, context):
        return common_pb2.HealthResponse(status="ok")


def serve(listen_address: str = "0.0.0.0:50051"):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    primary_pb2_grpc.add_PrimaryServicer_to_server(PrimaryServicer(), server)
    if ":" in listen_address:
        _, _, port = listen_address.rpartition(":")
        server.add_insecure_port(f"[::]:{port}")
    else:
        server.add_insecure_port(listen_address)
    return server
