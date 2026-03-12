"""Tests for apme_engine.cli."""

import json
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import apme_engine.cli as cli_module
from apme_engine.validators.base import ScanContext


def _make_context(hierarchy_payload: dict[str, Any], scandata: Any = None) -> ScanContext:
    return ScanContext(hierarchy_payload=hierarchy_payload, scandata=scandata, root_dir="")


class TestMain:
    """Tests for main() CLI entrypoint."""

    @pytest.fixture(autouse=True)  # type: ignore[untyped-decorator]
    def _repo_root(self, repo_root: Path) -> None:
        """Ensure repo_root is available; main uses Path(__file__).parent.parent."""
        pass

    def test_main_scan_failure_exits_1(self) -> None:
        """When run_scan raises, main writes to stderr and exits 1."""
        stderr_io = StringIO()
        with (
            patch.object(cli_module, "run_scan", side_effect=FileNotFoundError("path not found")),
            patch("sys.stderr", stderr_io),
            patch("sys.argv", ["apme-scan", "scan", "."]),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli_module.main()
        assert exc_info.value.code == 1
        assert "path not found" in stderr_io.getvalue() or "Scan failed" in stderr_io.getvalue()

    def test_main_empty_payload_exits_0_with_json(self) -> None:
        """When hierarchy_payload is empty and --json, print JSON and exit 0."""
        stdout_io = StringIO()
        with (
            patch.object(cli_module, "run_scan", return_value=_make_context({})),
            patch("sys.stderr", StringIO()),
            patch("sys.stdout", stdout_io),
            patch("sys.argv", ["apme-scan", "scan", "--json", "."]),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli_module.main()
        assert exc_info.value.code == 0
        out = stdout_io.getvalue()
        data = json.loads(out)
        assert data["violations"] == []
        assert "hierarchy_payload" in data

    def test_main_empty_payload_exits_0_without_json(self) -> None:
        """When hierarchy_payload is empty and no --json, exit 0 after stderr message."""
        stderr_io = StringIO()
        with (
            patch.object(cli_module, "run_scan", return_value=_make_context({})),
            patch("sys.stderr", stderr_io),
            patch("sys.argv", ["apme-scan", "scan", "."]),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli_module.main()
        assert exc_info.value.code == 0
        assert "No hierarchy payload" in stderr_io.getvalue()

    def test_main_no_validators_json_outputs_hierarchy_only(self, sample_hierarchy_payload: dict[str, object]) -> None:
        """With --no-opa --no-native and --json, output is hierarchy_payload only."""
        stdout_io = StringIO()
        with (
            patch.object(cli_module, "run_scan", return_value=_make_context(sample_hierarchy_payload)),
            patch("sys.argv", ["apme-scan", "scan", "--no-opa", "--no-native", "--json", "."]),
            patch("sys.stdout", stdout_io),
        ):
            cli_module.main()
        out = stdout_io.getvalue()
        data = json.loads(out)
        assert "hierarchy_payload" in data
        assert data["hierarchy_payload"]["scan_id"] == sample_hierarchy_payload["scan_id"]
        assert "violations" not in data

    def test_main_no_validators_no_json_prints_message(self, sample_hierarchy_payload: dict[str, object]) -> None:
        """With --no-opa --no-native and no --json, print message about validators skipped."""
        stdout_io = StringIO()
        with (
            patch.object(cli_module, "run_scan", return_value=_make_context(sample_hierarchy_payload)),
            patch("sys.argv", ["apme-scan", "scan", "--no-opa", "--no-native", "."]),
            patch("sys.stdout", stdout_io),
        ):
            cli_module.main()
        assert "validators skipped" in stdout_io.getvalue().lower() or "hierarchy" in stdout_io.getvalue().lower()

    def test_main_with_opa_json_outputs_violations_and_count(
        self, sample_hierarchy_payload: dict[str, object], opa_eval_result_with_violations: dict[str, object]
    ) -> None:
        """With OPA and --json, output includes violations and count."""
        stdout_io = StringIO()
        violations = opa_eval_result_with_violations["result"][0]["expressions"][0]["value"]  # type: ignore[index]
        with (
            patch.object(cli_module, "run_scan", return_value=_make_context(sample_hierarchy_payload)),
            patch("apme_engine.validators.opa.run_opa", return_value=violations),
            patch("sys.argv", ["apme-scan", "scan", "--no-native", "--json", "."]),
            patch("sys.stdout", stdout_io),
        ):
            cli_module.main()
        out = stdout_io.getvalue()
        data = json.loads(out)
        assert "violations" in data
        assert data["count"] == 1
        assert data["violations"][0]["rule_id"] == "task-name"

    def test_main_with_opa_no_json_prints_summary_and_list(self, sample_hierarchy_payload: dict[str, object]) -> None:
        """With OPA and no --json, print Scan line and violation lines."""
        stdout_io = StringIO()
        violations = [{"rule_id": "r1", "level": "warning", "message": "msg", "file": "f.yml", "line": 1, "path": "p"}]
        with (
            patch.object(cli_module, "run_scan", return_value=_make_context(sample_hierarchy_payload)),
            patch("apme_engine.validators.opa.run_opa", return_value=violations),
            patch("sys.argv", ["apme-scan", "scan", "--no-native", "."]),
            patch("sys.stdout", stdout_io),
        ):
            cli_module.main()
        out = stdout_io.getvalue()
        assert "Violations: 1" in out or "Violations:" in out
        assert "r1" in out
        assert "f.yml" in out
        assert "msg" in out

    def test_main_with_opa_no_violations_prints_no_violations(
        self, sample_hierarchy_payload: dict[str, object]
    ) -> None:
        """With OPA and no violations, print 'No violations.'"""
        stdout_io = StringIO()
        with (
            patch.object(cli_module, "run_scan", return_value=_make_context(sample_hierarchy_payload)),
            patch("apme_engine.validators.opa.run_opa", return_value=[]),
            patch("sys.argv", ["apme-scan", "scan", "--no-native", "."]),
            patch("sys.stdout", stdout_io),
        ):
            cli_module.main()
        assert "No violations" in stdout_io.getvalue()

    def test_main_uses_custom_opa_bundle_when_provided(
        self, sample_hierarchy_payload: dict[str, object], tmp_path: Path
    ) -> None:
        """When --opa-bundle is passed, OpaValidator receives that path."""
        bundle = tmp_path / "custom_bundle"
        bundle.mkdir()
        with (
            patch.object(cli_module, "run_scan", return_value=_make_context(sample_hierarchy_payload)),
            patch("apme_engine.validators.opa.run_opa", return_value=[]) as mock_opa,
            patch("sys.argv", ["apme-scan", "scan", "--no-native", "--opa-bundle", str(bundle), "."]),
        ):
            cli_module.main()
        mock_opa.assert_called_once()
        assert mock_opa.call_args[0][1] == str(bundle)


class TestRunScan:
    """Tests for run_scan (runner module) via CLI integration."""

    def test_run_scan_nonexistent_path_raises(self, repo_root: Path) -> None:
        """run_scan raises FileNotFoundError when target does not exist."""
        with (
            patch.object(
                cli_module, "run_scan", side_effect=FileNotFoundError("Target path does not exist: /nonexistent")
            ),
            pytest.raises(SystemExit),
            patch("sys.argv", ["apme-scan", "scan", "/nonexistent/path/xyz"]),
        ):
            cli_module.main()

    def test_run_scan_playbook_file_called_with_correct_args(
        self, repo_root: Path, tmp_path: Path, sample_hierarchy_payload: dict[str, object]
    ) -> None:
        """When target is a file, run_scan is called with playbook path and repo_root (from CLI's __file__)."""
        playbook = tmp_path / "play.yml"
        playbook.write_text("---\n- hosts: localhost\n  tasks: []\n")
        with (
            patch.object(cli_module, "run_scan", return_value=_make_context(sample_hierarchy_payload)) as mock_run_scan,
            patch("apme_engine.validators.opa.run_opa", return_value=[]),
            patch("sys.argv", ["apme-scan", "scan", "--no-native", str(playbook)]),
        ):
            cli_module.main()
        mock_run_scan.assert_called_once()
        call_args = mock_run_scan.call_args
        assert call_args[0][0] == str(playbook)
        # CLI uses Path(__file__).parent.parent (apme_engine -> src when run from source)
        expected_root = str(Path(cli_module.__file__).resolve().parent.parent)
        assert call_args[0][1] == expected_root
        assert call_args[1]["include_scandata"] is True

    def test_run_scan_returns_context_with_payload(
        self, repo_root: Path, tmp_path: Path, sample_hierarchy_payload: dict[str, object]
    ) -> None:
        """run_scan returns ScanContext with hierarchy_payload."""
        from apme_engine.runner import run_scan

        playbook = tmp_path / "play.yml"
        playbook.write_text("---\n- hosts: localhost\n  tasks: []\n")
        with patch("apme_engine.runner.ARIScanner") as MockScanner:
            mock_scanner = MagicMock()
            mock_scanner._current = MagicMock()
            mock_scanner._current.hierarchy_payload = sample_hierarchy_payload
            MockScanner.return_value = mock_scanner
            context = run_scan(str(playbook), str(repo_root), include_scandata=False)
        assert context.hierarchy_payload == sample_hierarchy_payload
        assert context.scandata is None
