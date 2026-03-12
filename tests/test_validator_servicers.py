"""Tests for unified Validator gRPC servicers (OPA wrapper, Native, Ansible migration).

All servicers are now async (grpc.aio), so tests use pytest-asyncio.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import jsonpickle
import pytest

from apme.v1 import common_pb2, validate_pb2


class FakeGrpcContext:
    """Minimal stub for grpc.ServicerContext."""

    def set_code(self, code: object) -> None:
        pass

    def set_details(self, details: object) -> None:
        pass


class TestOpaValidatorServicer:
    async def test_validate_posts_to_opa_rest(self) -> None:
        from apme_engine.daemon.opa_validator_server import OpaValidatorServicer

        hierarchy: dict[str, object] = {"hierarchy": [{"tree_type": "playbook", "nodes": []}]}
        violations = [{"rule_id": "L024", "level": "warning", "message": "m", "file": "f.yml", "line": 1, "path": "p"}]

        request = validate_pb2.ValidateRequest(
            request_id="test-req-1",
            hierarchy_payload=json.dumps(hierarchy).encode(),
        )

        servicer = OpaValidatorServicer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": violations}
        mock_response.content = b'{"result": [{"rule_id": "L024"}]}'

        with patch.object(servicer._client, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            resp = await servicer.Validate(request, FakeGrpcContext())

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["input"] == hierarchy
        assert len(resp.violations) == 1  # type: ignore[attr-defined]
        assert resp.violations[0].rule_id == "L024"  # type: ignore[attr-defined]
        assert resp.request_id == "test-req-1"  # type: ignore[attr-defined]

    async def test_validate_returns_diagnostics(self) -> None:
        from apme_engine.daemon.opa_validator_server import OpaValidatorServicer

        hierarchy: dict[str, object] = {"hierarchy": []}
        violations = [
            {"rule_id": "L024", "level": "warning", "message": "m1", "file": "a.yml", "line": 1, "path": ""},
            {"rule_id": "L024", "level": "warning", "message": "m2", "file": "a.yml", "line": 5, "path": ""},
            {"rule_id": "L007", "level": "warning", "message": "m3", "file": "b.yml", "line": 3, "path": ""},
        ]

        request = validate_pb2.ValidateRequest(
            request_id="diag-opa-1",
            hierarchy_payload=json.dumps(hierarchy).encode(),
        )
        servicer = OpaValidatorServicer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": violations}
        mock_response.content = b'{"result": []}'

        with patch.object(servicer._client, "post", new_callable=AsyncMock, return_value=mock_response):
            resp = await servicer.Validate(request, FakeGrpcContext())

        assert resp.HasField("diagnostics")  # type: ignore[attr-defined]
        diag = resp.diagnostics  # type: ignore[attr-defined]
        assert diag.validator_name == "opa"
        assert diag.request_id == "diag-opa-1"
        assert diag.violations_found == 3
        assert diag.total_ms > 0
        assert "opa_query_ms" in diag.metadata
        assert "opa_response_size" in diag.metadata

        rule_ids = [rt.rule_id for rt in diag.rule_timings]
        assert "opa_query" in rule_ids
        assert "L007" in rule_ids
        assert "L024" in rule_ids
        l024_timing = next(rt for rt in diag.rule_timings if rt.rule_id == "L024")
        assert l024_timing.violations == 2

    async def test_validate_empty_payload_returns_empty(self) -> None:
        from apme_engine.daemon.opa_validator_server import OpaValidatorServicer

        request = validate_pb2.ValidateRequest(request_id="test-req-2")
        servicer = OpaValidatorServicer()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_response.content = b'{"result": []}'

        with patch.object(servicer._client, "post", new_callable=AsyncMock, return_value=mock_response):
            resp = await servicer.Validate(request, FakeGrpcContext())
        assert len(resp.violations) == 0  # type: ignore[attr-defined]
        assert resp.request_id == "test-req-2"  # type: ignore[attr-defined]
        assert resp.HasField("diagnostics")  # type: ignore[attr-defined]
        assert resp.diagnostics.violations_found == 0  # type: ignore[attr-defined]

    async def test_validate_opa_http_error_returns_empty(self) -> None:
        from apme_engine.daemon.opa_validator_server import OpaValidatorServicer

        request = validate_pb2.ValidateRequest(
            request_id="test-req-3",
            hierarchy_payload=json.dumps({"hierarchy": []}).encode(),
        )
        mock_response = MagicMock()
        mock_response.status_code = 500

        servicer = OpaValidatorServicer()
        with patch.object(servicer._client, "post", new_callable=AsyncMock, return_value=mock_response):
            resp = await servicer.Validate(request, FakeGrpcContext())
        assert len(resp.violations) == 0  # type: ignore[attr-defined]

    async def test_health_opa_up(self) -> None:
        from apme_engine.daemon.opa_validator_server import OpaValidatorServicer

        mock_response = MagicMock()
        mock_response.status_code = 200

        servicer = OpaValidatorServicer()
        with patch.object(servicer._client, "get", new_callable=AsyncMock, return_value=mock_response):
            resp = await servicer.Health(common_pb2.HealthRequest(), FakeGrpcContext())
        assert resp.status == "ok"

    async def test_health_opa_down(self) -> None:
        from apme_engine.daemon.opa_validator_server import OpaValidatorServicer

        servicer = OpaValidatorServicer()
        with patch.object(servicer._client, "get", new_callable=AsyncMock, side_effect=ConnectionError("refused")):
            resp = await servicer.Health(common_pb2.HealthRequest(), FakeGrpcContext())
        assert "unreachable" in resp.status


class TestNativeValidatorServicer:
    async def test_validate_deserializes_scandata_and_runs(self) -> None:
        from apme_engine.daemon.native_validator_server import NativeValidatorServicer
        from apme_engine.validators.native import NativeRuleTiming, NativeRunResult

        mock_scandata = type("Scandata", (), {"contexts": []})()
        hierarchy: dict[str, object] = {"hierarchy": []}
        request = validate_pb2.ValidateRequest(
            request_id="native-1",
            hierarchy_payload=json.dumps(hierarchy).encode(),
            scandata=jsonpickle.encode(mock_scandata).encode(),
        )

        mock_result = NativeRunResult(
            violations=[
                {
                    "rule_id": "native:L028",
                    "level": "warning",
                    "message": "no name",
                    "file": "f.yml",
                    "line": 5,
                    "path": "p",
                },
            ],
            rule_timings=[
                NativeRuleTiming(rule_id="L028", elapsed_ms=3.5, violations=1),
            ],
        )

        servicer = NativeValidatorServicer()
        with patch("apme_engine.daemon.native_validator_server._run_native", return_value=mock_result):
            resp = await servicer.Validate(request, FakeGrpcContext())

        assert len(resp.violations) == 1  # type: ignore[attr-defined]
        assert resp.violations[0].rule_id == "native:L028"  # type: ignore[attr-defined]
        assert resp.request_id == "native-1"  # type: ignore[attr-defined]

    async def test_validate_returns_diagnostics(self) -> None:
        from apme_engine.daemon.native_validator_server import NativeValidatorServicer
        from apme_engine.validators.native import NativeRuleTiming, NativeRunResult

        mock_scandata = type("Scandata", (), {"contexts": []})()
        request = validate_pb2.ValidateRequest(
            request_id="diag-native-1",
            hierarchy_payload=json.dumps({"hierarchy": []}).encode(),
            scandata=jsonpickle.encode(mock_scandata).encode(),
        )

        mock_result = NativeRunResult(
            violations=[
                {"rule_id": "native:L028", "level": "warning", "message": "m1", "file": "f.yml", "line": 1, "path": ""},
                {"rule_id": "native:L029", "level": "warning", "message": "m2", "file": "f.yml", "line": 3, "path": ""},
            ],
            rule_timings=[
                NativeRuleTiming(rule_id="L028", elapsed_ms=2.1, violations=1),
                NativeRuleTiming(rule_id="L029", elapsed_ms=1.5, violations=1),
            ],
        )

        servicer = NativeValidatorServicer()
        with patch("apme_engine.daemon.native_validator_server._run_native", return_value=mock_result):
            resp = await servicer.Validate(request, FakeGrpcContext())

        assert resp.HasField("diagnostics")  # type: ignore[attr-defined]
        diag = resp.diagnostics  # type: ignore[attr-defined]
        assert diag.validator_name == "native"
        assert diag.request_id == "diag-native-1"
        assert diag.violations_found == 2
        assert diag.total_ms > 0
        assert len(diag.rule_timings) == 2
        rule_ids = {rt.rule_id for rt in diag.rule_timings}
        assert rule_ids == {"L028", "L029"}
        l028 = next(rt for rt in diag.rule_timings if rt.rule_id == "L028")
        assert l028.elapsed_ms == pytest.approx(2.1)
        assert l028.violations == 1

    async def test_validate_no_scandata_returns_empty(self) -> None:
        from apme_engine.daemon.native_validator_server import NativeValidatorServicer
        from apme_engine.validators.native import NativeRunResult

        request = validate_pb2.ValidateRequest(
            request_id="native-2",
            hierarchy_payload=json.dumps({}).encode(),
        )
        servicer = NativeValidatorServicer()

        mock_result = NativeRunResult(violations=[], rule_timings=[])
        with patch("apme_engine.daemon.native_validator_server._run_native", return_value=mock_result):
            resp = await servicer.Validate(request, FakeGrpcContext())
        assert len(resp.violations) == 0  # type: ignore[attr-defined]

    async def test_validate_bad_scandata_returns_empty(self) -> None:
        from apme_engine.daemon.native_validator_server import NativeValidatorServicer

        request = validate_pb2.ValidateRequest(
            request_id="native-3",
            hierarchy_payload=json.dumps({}).encode(),
            scandata=b"not-valid-jsonpickle{{{",
        )
        servicer = NativeValidatorServicer()
        resp = await servicer.Validate(request, FakeGrpcContext())
        assert len(resp.violations) == 0  # type: ignore[attr-defined]

    async def test_health_returns_ok(self) -> None:
        from apme_engine.daemon.native_validator_server import NativeValidatorServicer

        servicer = NativeValidatorServicer()
        resp = await servicer.Health(common_pb2.HealthRequest(), FakeGrpcContext())
        assert resp.status == "ok"


class TestGitleaksValidatorServicerDiagnostics:
    async def test_validate_returns_diagnostics(self) -> None:
        from apme_engine.daemon.gitleaks_validator_server import GitleaksValidatorServicer

        request = validate_pb2.ValidateRequest(
            request_id="diag-gl-1",
            files=[common_pb2.File(path="test.yml", content=b"password: hunter2\n")],
        )

        mock_violations = [
            {"rule_id": "R502", "level": "error", "message": "secret", "file": "test.yml", "line": 1, "path": ""},
        ]

        servicer = GitleaksValidatorServicer()
        with patch("apme_engine.daemon.gitleaks_validator_server._run_scan", return_value=(mock_violations, 1)):
            resp = await servicer.Validate(request, FakeGrpcContext())

        assert resp.HasField("diagnostics")  # type: ignore[attr-defined]
        diag = resp.diagnostics  # type: ignore[attr-defined]
        assert diag.validator_name == "gitleaks"
        assert diag.request_id == "diag-gl-1"
        assert diag.violations_found == 1
        assert diag.total_ms > 0
        assert len(diag.rule_timings) == 1
        assert diag.rule_timings[0].rule_id == "gitleaks_subprocess"
        assert "files_written" in diag.metadata
        assert diag.metadata["files_written"] == "1"

    async def test_validate_empty_files_no_diagnostics(self) -> None:
        from apme_engine.daemon.gitleaks_validator_server import GitleaksValidatorServicer

        request = validate_pb2.ValidateRequest(request_id="diag-gl-2")
        servicer = GitleaksValidatorServicer()
        resp = await servicer.Validate(request, FakeGrpcContext())
        assert len(resp.violations) == 0  # type: ignore[attr-defined]


class TestAnsibleValidatorServicerMigration:
    """Verify Ansible validator now uses the unified Validator service."""

    def test_servicer_extends_validator_servicer(self) -> None:
        from apme_engine.daemon.ansible_validator_server import AnsibleValidatorServicer

        assert hasattr(AnsibleValidatorServicer, "Validate")

    def test_serve_is_async(self) -> None:
        import inspect

        from apme_engine.daemon.ansible_validator_server import serve

        assert inspect.iscoroutinefunction(serve)

    async def test_validate_returns_diagnostics(self) -> None:
        from apme_engine.daemon.ansible_validator_server import AnsibleValidatorServicer, _AnsibleResult
        from apme_engine.validators.ansible import AnsibleRuleTiming, AnsibleRunResult

        request = validate_pb2.ValidateRequest(
            request_id="diag-ans-1",
            ansible_core_version="2.18",
            files=[common_pb2.File(path="playbook.yml", content=b"---\n- hosts: all\n  tasks: []\n")],
        )

        mock_result = _AnsibleResult(
            run_result=AnsibleRunResult(
                violations=[
                    {
                        "rule_id": "L057",
                        "level": "error",
                        "message": "syntax",
                        "file": "playbook.yml",
                        "line": 1,
                        "path": "",
                    },
                ],
                rule_timings=[
                    AnsibleRuleTiming(rule_id="L057", elapsed_ms=120.0, violations=1),
                ],
            ),
            venv_build_ms=850.0,
            ansible_core_version="2.18",
        )

        servicer = AnsibleValidatorServicer()
        with patch("apme_engine.daemon.ansible_validator_server._run_ansible_validate", return_value=mock_result):
            resp = await servicer.Validate(request, FakeGrpcContext())

        assert resp.HasField("diagnostics")  # type: ignore[attr-defined]
        diag = resp.diagnostics  # type: ignore[attr-defined]
        assert diag.validator_name == "ansible"
        assert diag.request_id == "diag-ans-1"
        assert diag.violations_found == 1
        assert diag.total_ms > 0
        assert len(diag.rule_timings) == 1
        assert diag.rule_timings[0].rule_id == "L057"
        assert diag.rule_timings[0].elapsed_ms == pytest.approx(120.0)
        assert diag.metadata["ansible_core_version"] == "2.18"
        assert diag.metadata["venv_build_ms"] == "850.0"


class TestPrimaryFanOut:
    """Verify Primary uses async fan-out for all backends."""

    async def test_call_validator_uses_async_channel(self) -> None:
        from apme_engine.daemon.primary_server import _call_validator

        mock_resp = MagicMock()
        mock_resp.violations = []
        mock_resp.HasField = MagicMock(return_value=False)

        mock_stub = MagicMock()
        mock_stub.Validate = AsyncMock(return_value=mock_resp)

        with patch("apme_engine.daemon.primary_server.grpc.aio.insecure_channel") as mock_channel:
            mock_channel_instance = MagicMock()
            mock_channel_instance.close = AsyncMock()
            mock_channel.return_value = mock_channel_instance
            with patch("apme_engine.daemon.primary_server.validate_pb2_grpc.ValidatorStub", return_value=mock_stub):
                request = validate_pb2.ValidateRequest(request_id="primary-1")
                result = await _call_validator("localhost:50055", request)

        mock_stub.Validate.assert_called_once()
        assert result.violations == []

    async def test_call_validator_captures_diagnostics(self) -> None:
        from apme_engine.daemon.primary_server import _call_validator

        diag = common_pb2.ValidatorDiagnostics(
            validator_name="native",
            total_ms=42.0,
            violations_found=5,
        )
        mock_resp = MagicMock()
        mock_resp.violations = []
        mock_resp.HasField = MagicMock(return_value=True)
        mock_resp.diagnostics = diag

        mock_stub = MagicMock()
        mock_stub.Validate = AsyncMock(return_value=mock_resp)

        with patch("apme_engine.daemon.primary_server.grpc.aio.insecure_channel") as mock_channel:
            mock_channel_instance = MagicMock()
            mock_channel_instance.close = AsyncMock()
            mock_channel.return_value = mock_channel_instance
            with patch("apme_engine.daemon.primary_server.validate_pb2_grpc.ValidatorStub", return_value=mock_stub):
                request = validate_pb2.ValidateRequest(request_id="primary-diag-1")
                result = await _call_validator("localhost:50055", request)

        assert result.diagnostics is not None
        assert result.diagnostics.validator_name == "native"
        assert result.diagnostics.total_ms == 42.0

    def test_primary_no_longer_imports_native_validator(self) -> None:
        """Primary should not import NativeValidator directly (it's in its own container)."""
        import apme_engine.daemon.primary_server as ps

        source = Path(ps.__file__).read_text()
        assert "from apme_engine.validators.native" not in source
        assert "NativeValidator()" not in source

    def test_primary_no_longer_imports_opa_client(self) -> None:
        """Primary should not import opa_client (OPA is behind gRPC now)."""
        import apme_engine.daemon.primary_server as ps

        source = Path(ps.__file__).read_text()
        assert "from apme_engine.opa_client" not in source
        assert "_call_opa" not in source

    def test_primary_propagates_request_id(self) -> None:
        """Primary should set request_id on ValidateRequest."""
        import apme_engine.daemon.primary_server as ps

        source = Path(ps.__file__).read_text()
        assert "request_id=scan_id" in source

    def test_primary_serve_is_async(self) -> None:
        import inspect

        from apme_engine.daemon.primary_server import serve

        assert inspect.iscoroutinefunction(serve)

    def test_primary_aggregates_diagnostics(self) -> None:
        """Primary should collect validator diagnostics into ScanDiagnostics."""
        import apme_engine.daemon.primary_server as ps

        source = Path(ps.__file__).read_text()
        assert "ScanDiagnostics" in source
        assert "validator_diagnostics" in source
        assert "engine_diagnostics" in source


class TestGrpcAioConsistency:
    """Verify all servers use grpc.aio."""

    @pytest.mark.parametrize(
        "module_path",
        [
            "apme_engine.daemon.primary_server",
            "apme_engine.daemon.native_validator_server",
            "apme_engine.daemon.opa_validator_server",
            "apme_engine.daemon.ansible_validator_server",
            "apme_engine.daemon.gitleaks_validator_server",
        ],
    )  # type: ignore[untyped-decorator]
    def test_serve_is_async_coroutine(self, module_path: str) -> None:
        import importlib
        import inspect

        mod = importlib.import_module(str(module_path))
        assert inspect.iscoroutinefunction(mod.serve), f"{module_path}.serve should be async"

    @pytest.mark.parametrize(
        "module_path",
        [
            "apme_engine.daemon.primary_server",
            "apme_engine.daemon.native_validator_server",
            "apme_engine.daemon.opa_validator_server",
            "apme_engine.daemon.ansible_validator_server",
            "apme_engine.daemon.gitleaks_validator_server",
        ],
    )  # type: ignore[untyped-decorator]
    def test_server_uses_grpc_aio(self, module_path: str) -> None:
        import importlib

        mod = importlib.import_module(module_path)
        source = Path(str(mod.__file__)).read_text()
        assert "grpc.aio" in source, f"{module_path} should use grpc.aio"

    @pytest.mark.parametrize(
        "module_path",
        [
            "apme_engine.daemon.native_validator_server",
            "apme_engine.daemon.opa_validator_server",
            "apme_engine.daemon.ansible_validator_server",
            "apme_engine.daemon.gitleaks_validator_server",
        ],
    )  # type: ignore[untyped-decorator]
    def test_validator_echoes_request_id(self, module_path: str) -> None:
        import importlib

        mod = importlib.import_module(module_path)
        source = Path(str(mod.__file__)).read_text()
        assert "request_id" in source, f"{module_path} should handle request_id"

    @pytest.mark.parametrize(
        "module_path",
        [
            "apme_engine.daemon.native_validator_server",
            "apme_engine.daemon.opa_validator_server",
            "apme_engine.daemon.ansible_validator_server",
            "apme_engine.daemon.gitleaks_validator_server",
        ],
    )  # type: ignore[untyped-decorator]
    def test_validator_returns_diagnostics(self, module_path: str) -> None:
        """All validator servicers should populate diagnostics in ValidateResponse."""
        import importlib

        mod = importlib.import_module(str(module_path))
        source = Path(str(mod.__file__ or "")).read_text()
        assert "ValidatorDiagnostics" in source, f"{module_path} should build ValidatorDiagnostics"
        assert "diagnostics=" in source, f"{module_path} should set diagnostics= in response"


class TestRequestIdPropagation:
    """Verify request_id flows through the proto contract."""

    def test_validate_request_has_request_id_field(self) -> None:
        req = validate_pb2.ValidateRequest(request_id="abc-123")
        assert req.request_id == "abc-123"

    def test_validate_response_has_request_id_field(self) -> None:
        resp = validate_pb2.ValidateResponse(request_id="abc-123")
        assert resp.request_id == "abc-123"  # type: ignore[attr-defined]

    def test_validate_response_has_diagnostics_field(self) -> None:
        diag = common_pb2.ValidatorDiagnostics(
            validator_name="test",
            total_ms=10.0,
            violations_found=2,
        )
        resp = validate_pb2.ValidateResponse(
            request_id="abc-123",
            diagnostics=diag,
        )
        assert resp.HasField("diagnostics")  # type: ignore[attr-defined]
        assert resp.diagnostics.validator_name == "test"  # type: ignore[attr-defined]
        assert resp.diagnostics.total_ms == 10.0  # type: ignore[attr-defined]


class TestDiagnosticsProtoMessages:
    """Verify the diagnostics proto messages work correctly."""

    def test_rule_timing(self) -> None:
        rt = common_pb2.RuleTiming(rule_id="L024", elapsed_ms=5.2, violations=3)
        assert rt.rule_id == "L024"
        assert rt.elapsed_ms == pytest.approx(5.2)
        assert rt.violations == 3

    def test_validator_diagnostics(self) -> None:
        rt = common_pb2.RuleTiming(rule_id="L024", elapsed_ms=5.2, violations=3)
        diag = common_pb2.ValidatorDiagnostics(
            validator_name="opa",
            request_id="req-1",
            total_ms=42.0,
            files_received=10,
            violations_found=5,
            rule_timings=[rt],
            metadata={"key": "value"},
        )
        assert diag.validator_name == "opa"
        assert diag.total_ms == pytest.approx(42.0)
        assert len(diag.rule_timings) == 1
        assert diag.metadata["key"] == "value"

    def test_scan_diagnostics(self) -> None:
        from apme.v1 import primary_pb2

        vd = common_pb2.ValidatorDiagnostics(validator_name="native", total_ms=10.0)
        sd = primary_pb2.ScanDiagnostics(
            engine_parse_ms=5.0,
            engine_annotate_ms=8.0,
            engine_total_ms=20.0,
            files_scanned=3,
            trees_built=1,
            total_violations=7,
            validators=[vd],
            fan_out_ms=15.0,
            total_ms=50.0,
        )
        assert sd.engine_parse_ms == pytest.approx(5.0)
        assert sd.engine_total_ms == pytest.approx(20.0)
        assert len(sd.validators) == 1
        assert sd.validators[0].validator_name == "native"
        assert sd.total_ms == pytest.approx(50.0)


class TestCliDiagnosticsDisplay:
    """Verify the CLI diagnostics formatting functions."""

    def test_fmt_ms_sub_1(self) -> None:
        from apme_engine.cli import _fmt_ms

        assert _fmt_ms(0.5) == "<1ms"

    def test_fmt_ms_normal(self) -> None:
        from apme_engine.cli import _fmt_ms

        assert _fmt_ms(42.3) == "42ms"

    def test_fmt_ms_seconds(self) -> None:
        from apme_engine.cli import _fmt_ms

        assert _fmt_ms(1500.0) == "1.5s"

    def test_diag_to_dict(self) -> None:
        from apme.v1 import primary_pb2
        from apme_engine.cli import _diag_to_dict

        vd = common_pb2.ValidatorDiagnostics(
            validator_name="native",
            total_ms=10.5,
            files_received=2,
            violations_found=3,
            rule_timings=[common_pb2.RuleTiming(rule_id="L028", elapsed_ms=4.2, violations=2)],
            metadata={"foo": "bar"},
        )
        sd = primary_pb2.ScanDiagnostics(
            engine_parse_ms=5.0,
            engine_annotate_ms=8.0,
            engine_total_ms=20.0,
            files_scanned=3,
            trees_built=1,
            total_violations=7,
            validators=[vd],
            fan_out_ms=15.0,
            total_ms=50.0,
        )
        result = _diag_to_dict(sd)
        assert result["engine_parse_ms"] == 5.0
        assert result["total_ms"] == 50.0
        assert len(result["validators"]) == 1
        v = result["validators"][0]
        assert v["validator_name"] == "native"
        assert v["total_ms"] == 10.5
        assert len(v["rule_timings"]) == 1
        assert v["rule_timings"][0]["rule_id"] == "L028"
        assert v["metadata"] == {"foo": "bar"}

    def test_print_diagnostics_v_no_crash(self, capsys: pytest.CaptureFixture[str]) -> None:
        from apme.v1 import primary_pb2
        from apme_engine.cli import _print_diagnostics_v

        vd = common_pb2.ValidatorDiagnostics(
            validator_name="native",
            total_ms=10.5,
            violations_found=3,
            rule_timings=[common_pb2.RuleTiming(rule_id="L028", elapsed_ms=4.2, violations=2)],
        )
        sd = primary_pb2.ScanDiagnostics(
            engine_parse_ms=5.0,
            engine_total_ms=20.0,
            validators=[vd],
            fan_out_ms=15.0,
            total_ms=50.0,
        )
        _print_diagnostics_v(sd)
        captured = capsys.readouterr()
        assert "Engine:" in captured.err
        assert "Native" in captured.err
        assert "L028" in captured.err

    def test_print_diagnostics_vv_no_crash(self, capsys: pytest.CaptureFixture[str]) -> None:
        from apme.v1 import primary_pb2
        from apme_engine.cli import _print_diagnostics_vv

        vd = common_pb2.ValidatorDiagnostics(
            validator_name="opa",
            total_ms=25.0,
            violations_found=5,
            rule_timings=[
                common_pb2.RuleTiming(rule_id="opa_query", elapsed_ms=20.0, violations=5),
                common_pb2.RuleTiming(rule_id="L024", elapsed_ms=0.0, violations=3),
            ],
            metadata={"opa_query_ms": "20.0"},
        )
        sd = primary_pb2.ScanDiagnostics(
            engine_parse_ms=5.0,
            engine_annotate_ms=3.0,
            engine_total_ms=20.0,
            files_scanned=4,
            trees_built=2,
            validators=[vd],
            fan_out_ms=25.0,
            total_ms=60.0,
        )
        _print_diagnostics_vv(sd)
        captured = capsys.readouterr()
        assert "Engine:" in captured.err
        assert "Opa" in captured.err
        assert "opa_query" in captured.err
        assert "L024" in captured.err
        assert "metadata:" in captured.err
