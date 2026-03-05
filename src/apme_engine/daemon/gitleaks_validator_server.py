"""Gitleaks validator daemon: gRPC server that writes files to a temp dir,
runs gitleaks detect, and returns violations."""

import shutil
import sys
import tempfile
from concurrent import futures
from pathlib import Path

import grpc
from apme.v1 import validate_pb2, validate_pb2_grpc, common_pb2

from apme_engine.daemon.violation_convert import violation_dict_to_proto
from apme_engine.validators.gitleaks.scanner import run_gitleaks


class GitleaksValidatorServicer(validate_pb2_grpc.ValidatorServicer):
    """gRPC adapter: writes received files to temp dir, runs gitleaks, returns violations."""

    def Validate(self, request, context):
        temp_dir = None
        try:
            if not request.files:
                return validate_pb2.ValidateResponse(violations=[])

            temp_dir = Path(tempfile.mkdtemp(prefix="apme_gitleaks_"))
            yaml_count = 0
            for f in request.files:
                if not f.path.endswith((".yml", ".yaml", ".cfg", ".ini", ".conf", ".env", ".py", ".sh", ".json")):
                    continue
                out = temp_dir / f.path
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(f.content)
                yaml_count += 1

            sys.stderr.write(f"Gitleaks validator: scanning {yaml_count} file(s)\n")
            sys.stderr.flush()

            violations = run_gitleaks(temp_dir)
            sys.stderr.write(f"Gitleaks validator returned {len(violations)} finding(s)\n")
            sys.stderr.flush()

            return validate_pb2.ValidateResponse(
                violations=[violation_dict_to_proto(v) for v in violations]
            )
        except Exception as e:
            import traceback
            sys.stderr.write(f"Gitleaks validator error: {e}\n")
            traceback.print_exc(file=sys.stderr)
            sys.stderr.flush()
            return validate_pb2.ValidateResponse(violations=[])
        finally:
            if temp_dir is not None and temp_dir.is_dir():
                try:
                    shutil.rmtree(temp_dir)
                except OSError:
                    pass

    def Health(self, request, context):
        from apme_engine.validators.gitleaks.scanner import GITLEAKS_BIN
        import subprocess
        try:
            proc = subprocess.run(
                [GITLEAKS_BIN, "version"],
                capture_output=True, text=True, timeout=5,
            )
            if proc.returncode == 0:
                version = proc.stdout.strip()
                return common_pb2.HealthResponse(status=f"ok (gitleaks {version})")
            return common_pb2.HealthResponse(status=f"gitleaks exited {proc.returncode}")
        except FileNotFoundError:
            return common_pb2.HealthResponse(status="gitleaks binary not found")
        except Exception as e:
            return common_pb2.HealthResponse(status=f"gitleaks health error: {e}")


def serve(listen: str = "0.0.0.0:50056"):
    """Create and return a gRPC server with Gitleaks servicer (caller must start it)."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    validate_pb2_grpc.add_ValidatorServicer_to_server(GitleaksValidatorServicer(), server)
    if ":" in listen:
        _, _, port = listen.rpartition(":")
        server.add_insecure_port(f"[::]:{port}")
    else:
        server.add_insecure_port(listen)
    return server
