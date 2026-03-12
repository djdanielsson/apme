"""Tests for apme_engine.opa_client."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from apme_engine.opa_client import run_opa, run_opa_test


class TestRunOpa:
    """Tests for run_opa()."""

    def test_bundle_not_directory_raises(self, tmp_path: Path) -> None:
        """Non-directory bundle path raises FileNotFoundError."""
        not_dir = tmp_path / "file.txt"
        not_dir.write_text("x")
        with pytest.raises(FileNotFoundError, match="is not a directory"):
            run_opa({"hierarchy": []}, str(not_dir))

    def test_bundle_nonexistent_raises(self, tmp_path: Path) -> None:
        """Nonexistent bundle path raises FileNotFoundError."""
        missing = tmp_path / "missing"
        with pytest.raises(FileNotFoundError, match="is not a directory"):
            run_opa({"hierarchy": []}, str(missing))

    def test_opa_not_found_returns_empty_list(self, opa_bundle_path: Path) -> None:
        """When opa command is not found, returns [] and writes to stderr."""
        with (
            patch("apme_engine.opa_client.subprocess.run", side_effect=FileNotFoundError("opa not found")),
            patch("sys.stderr.write") as mock_stderr,
        ):
            result = run_opa({"hierarchy": []}, str(opa_bundle_path))
        assert result == []
        mock_stderr.assert_called_once()
        assert "opa" in mock_stderr.call_args[0][0].lower()

    def test_opa_nonzero_exit_returns_empty_list(
        self, opa_bundle_path: Path, sample_hierarchy_payload: dict[str, object]
    ) -> None:
        """When OPA returns non-zero exit code, returns [] and writes stderr."""
        with patch("apme_engine.opa_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="policy error")
            with patch("sys.stderr.write") as mock_stderr:
                result = run_opa(sample_hierarchy_payload, str(opa_bundle_path))
        assert result == []
        mock_stderr.assert_called_once()
        assert "policy error" in mock_stderr.call_args[0][0]

    def test_opa_invalid_json_returns_empty_list(
        self, opa_bundle_path: Path, sample_hierarchy_payload: dict[str, object]
    ) -> None:
        """When OPA stdout is not valid JSON, returns [] and writes stderr."""
        with patch("apme_engine.opa_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="not json", stderr="")
            with patch("sys.stderr.write") as mock_stderr:
                result = run_opa(sample_hierarchy_payload, str(opa_bundle_path))
        assert result == []
        mock_stderr.assert_called_once()
        assert "invalid JSON" in mock_stderr.call_args[0][0]

    def test_opa_empty_result_returns_empty_list(
        self,
        opa_bundle_path: Path,
        sample_hierarchy_payload: dict[str, object],
        opa_eval_result_empty: dict[str, object],
    ) -> None:
        """When OPA result has no expressions, returns []."""
        with patch("apme_engine.opa_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps({"result": []}), stderr="")
            result = run_opa(sample_hierarchy_payload, str(opa_bundle_path))
        assert result == []

    def test_opa_value_none_returns_empty_list(
        self, opa_bundle_path: Path, sample_hierarchy_payload: dict[str, object]
    ) -> None:
        """When expressions[0].expressions[0].value is None, returns []."""
        with patch("apme_engine.opa_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({"result": [{"expressions": [{"value": None}]}]}),
                stderr="",
            )
            result = run_opa(sample_hierarchy_payload, str(opa_bundle_path))
        assert result == []

    def test_opa_value_not_list_returns_empty_list(
        self, opa_bundle_path: Path, sample_hierarchy_payload: dict[str, object]
    ) -> None:
        """When value is not a list (e.g. object), returns []."""
        with patch("apme_engine.opa_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({"result": [{"expressions": [{"value": {"foo": "bar"}}]}]}),
                stderr="",
            )
            result = run_opa(sample_hierarchy_payload, str(opa_bundle_path))
        assert result == []

    def test_opa_success_returns_violations_list(
        self,
        opa_bundle_path: Path,
        sample_hierarchy_payload: dict[str, object],
        opa_eval_result_with_violations: dict[str, object],
    ) -> None:
        """When OPA returns valid result with violations, returns that list."""
        with patch("apme_engine.opa_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(opa_eval_result_with_violations),
                stderr="",
            )
            result = run_opa(sample_hierarchy_payload, str(opa_bundle_path))
        assert len(result) == 1
        assert result[0]["rule_id"] == "task-name"
        assert result[0]["level"] == "warning"
        assert result[0]["file"] == "/examples/pb.yml"
        assert result[0]["line"] == 5

    def test_opa_success_empty_violations(
        self,
        opa_bundle_path: Path,
        sample_hierarchy_payload: dict[str, object],
        opa_eval_result_empty: dict[str, object],
    ) -> None:
        """When OPA returns valid result with empty value list, returns []."""
        with patch("apme_engine.opa_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(opa_eval_result_empty),
                stderr="",
            )
            result = run_opa(sample_hierarchy_payload, str(opa_bundle_path))
        assert result == []

    def test_opa_custom_entrypoint(
        self,
        opa_bundle_path: Path,
        sample_hierarchy_payload: dict[str, object],
        opa_eval_result_empty: dict[str, object],
    ) -> None:
        """run_opa passes custom entrypoint to opa eval."""
        with patch("apme_engine.opa_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(opa_eval_result_empty), stderr="")
            run_opa(sample_hierarchy_payload, str(opa_bundle_path), entrypoint="data.custom.violations")
        call_args = mock_run.call_args[0][0]
        assert "data.custom.violations" in call_args

    def test_opa_input_passed_via_stdin(
        self,
        opa_bundle_path: Path,
        sample_hierarchy_payload: dict[str, object],
        opa_eval_result_empty: dict[str, object],
    ) -> None:
        """Input JSON is passed to opa via stdin."""
        with patch("apme_engine.opa_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(opa_eval_result_empty), stderr="")
            run_opa(sample_hierarchy_payload, str(opa_bundle_path))
        kwargs = mock_run.call_args[1]
        assert kwargs["input"] == json.dumps(sample_hierarchy_payload)


class TestRunOpaTest:
    """Tests for run_opa_test() — runs OPA Rego unit tests in the bundle."""

    def test_opa_bundle_rego_tests_pass(self, opa_bundle_path: Path) -> None:
        """Run `opa test . -v` in the bundle (Podman or local opa). All Rego tests must pass."""
        success, stdout, stderr = run_opa_test(opa_bundle_path)
        if not success and "not found" in stderr.lower():
            pytest.skip("podman and opa not available; install one to run OPA bundle tests")
        assert success, f"OPA Rego tests failed.\nstdout:\n{stdout}\nstderr:\n{stderr}"

    def test_run_opa_test_bundle_not_directory_raises(self, tmp_path: Path) -> None:
        """Non-directory bundle path raises FileNotFoundError."""
        not_dir = tmp_path / "file.txt"
        not_dir.write_text("x")
        with pytest.raises(FileNotFoundError, match="is not a directory"):
            run_opa_test(not_dir)

    def test_run_opa_test_bundle_nonexistent_raises(self, tmp_path: Path) -> None:
        """Nonexistent bundle path raises FileNotFoundError."""
        missing = tmp_path / "missing"
        with pytest.raises(FileNotFoundError, match="is not a directory"):
            run_opa_test(missing)
