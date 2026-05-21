"""Unit tests for ADR-055 fingerprinting and suppression."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from apme_engine.cli._suppressions import (
    Suppression,
    apply_suppressions,
    load_suppressions,
    write_suppressions,
)
from apme_engine.engine.models import ViolationDict
from apme_engine.fingerprint import (
    canonicalize_rule_id,
    compute_fingerprint,
    normalize_yaml,
)


class TestCanonicalizeRuleId:
    """Tests for canonicalize_rule_id."""

    def test_no_prefix(self) -> None:
        """Bare rule ID is returned unchanged."""
        assert canonicalize_rule_id("L046") == "L046"

    def test_native_prefix(self) -> None:
        """Strips native: prefix."""
        assert canonicalize_rule_id("native:L046") == "L046"

    def test_opa_prefix(self) -> None:
        """Strips opa: prefix."""
        assert canonicalize_rule_id("opa:P001") == "P001"

    def test_ansible_prefix(self) -> None:
        """Strips ansible: prefix."""
        assert canonicalize_rule_id("ansible:R001") == "R001"

    def test_gitleaks_prefix(self) -> None:
        """Strips gitleaks: prefix."""
        assert canonicalize_rule_id("gitleaks:SEC001") == "SEC001"

    def test_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace is removed."""
        assert canonicalize_rule_id("  native:L046  ") == "L046"

    def test_unknown_prefix_kept(self) -> None:
        """Non-validator prefixes are preserved."""
        assert canonicalize_rule_id("custom:EXT-001") == "custom:EXT-001"


class TestNormalizeYaml:
    """Tests for normalize_yaml."""

    def test_empty_string(self) -> None:
        """Empty input returns empty string."""
        assert normalize_yaml("") == ""

    def test_whitespace_only(self) -> None:
        """Whitespace-only input returns empty string."""
        assert normalize_yaml("   \n  \n  ") == ""

    def test_strips_comments(self) -> None:
        """YAML comments outside scalars are removed."""
        text = "# This is a comment\nname: Install nginx\n# Another comment\n"
        result = normalize_yaml(text)
        assert "comment" not in result
        assert "Install nginx" in result

    def test_preserves_values(self) -> None:
        """Scalar values are preserved verbatim."""
        text = "name: Install nginx\nansible.builtin.shell: apt install nginx\n"
        result = normalize_yaml(text)
        assert "Install nginx" in result
        assert "apt install nginx" in result

    def test_block_scalar_literal(self) -> None:
        """Block scalar (|) bodies are preserved including comment-like lines."""
        text = "script: |\n  #!/bin/bash\n  # This is runtime content\n  echo hello\n"
        result = normalize_yaml(text)
        assert "# This is runtime content" in result
        assert "echo hello" in result

    def test_block_scalar_folded(self) -> None:
        """Folded scalar (>) bodies are preserved."""
        text = "msg: >\n  This is a long\n  message that spans\n  multiple lines\n"
        result = normalize_yaml(text)
        assert "long" in result
        assert "message" in result

    def test_jinja2_expression(self) -> None:
        """Jinja2 expressions in values are preserved."""
        text = 'name: "{{ item.name }}"\nwhen: item.enabled\n'
        result = normalize_yaml(text)
        assert "{{ item.name }}" in result
        assert "item.enabled" in result

    def test_comment_like_in_scalar(self) -> None:
        """Hash characters inside scalar values are not stripped."""
        text = 'msg: "Use # to indicate a comment in YAML"\n'
        result = normalize_yaml(text)
        assert "# to indicate" in result

    def test_does_not_reorder_keys(self) -> None:
        """Key order is preserved (no alphabetical sorting)."""
        text = "zebra: 1\nalpha: 2\nmiddle: 3\n"
        result = normalize_yaml(text)
        lines = [line for line in result.split("\n") if line.strip()]
        keys = [line.split(":")[0] for line in lines]
        assert keys == ["zebra", "alpha", "middle"]

    def test_crlf_normalized_to_lf(self) -> None:
        """CRLF line endings are converted to LF."""
        text = "name: test\r\nvalue: foo\r\n"
        result = normalize_yaml(text)
        assert "\r" not in result

    def test_blank_line_collapse(self) -> None:
        """Runs of blank lines are collapsed."""
        text = "name: test\n\n\n\n\nvalue: foo\n"
        result = normalize_yaml(text)
        assert "\n\n\n" not in result

    def test_multiline_string_value(self) -> None:
        """Quoted multiline string values are preserved."""
        text = 'command: "echo hello && echo world"\n'
        result = normalize_yaml(text)
        assert "echo hello" in result
        assert "echo world" in result


class TestComputeFingerprint:
    """Tests for compute_fingerprint."""

    def test_full_mode_basic(self) -> None:
        """Full mode produces a valid 64-char hex digest."""
        fp = compute_fingerprint(
            "L046",
            "name: Install nginx\nansible.builtin.shell: apt install nginx\n",
        )
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)

    def test_full_mode_deterministic(self) -> None:
        """Same inputs always produce the same fingerprint."""
        yaml_text = "name: Install nginx\nansible.builtin.shell: apt install nginx\n"
        fp1 = compute_fingerprint("L046", yaml_text)
        fp2 = compute_fingerprint("L046", yaml_text)
        assert fp1 == fp2

    def test_different_content_different_fingerprint(self) -> None:
        """Different YAML content produces different fingerprints."""
        fp1 = compute_fingerprint("L046", "ansible.builtin.shell: apt install nginx\n")
        fp2 = compute_fingerprint("L046", "ansible.builtin.shell: rm -rf /data\n")
        assert fp1 != fp2

    def test_different_rule_different_fingerprint(self) -> None:
        """Different rule IDs produce different fingerprints for same content."""
        yaml_text = "name: test\n"
        fp1 = compute_fingerprint("L046", yaml_text)
        fp2 = compute_fingerprint("L047", yaml_text)
        assert fp1 != fp2

    def test_comment_does_not_affect_fingerprint(self) -> None:
        """Adding comments does not change the fingerprint."""
        yaml1 = "name: Install nginx\nansible.builtin.shell: apt install nginx\n"
        yaml2 = "# Comment here\nname: Install nginx\nansible.builtin.shell: apt install nginx\n"
        fp1 = compute_fingerprint("L046", yaml1)
        fp2 = compute_fingerprint("L046", yaml2)
        assert fp1 == fp2

    def test_rule_module_mode(self) -> None:
        """Rule-module mode produces a valid fingerprint."""
        fp = compute_fingerprint(
            "L046",
            "",
            mode="rule_module",
            module_fqcn="ansible.builtin.shell",
        )
        assert len(fp) == 64

    def test_rule_module_mode_different_modules(self) -> None:
        """Different modules produce different fingerprints in rule_module mode."""
        fp1 = compute_fingerprint("L046", "", mode="rule_module", module_fqcn="ansible.builtin.shell")
        fp2 = compute_fingerprint("L046", "", mode="rule_module", module_fqcn="ansible.builtin.command")
        assert fp1 != fp2

    def test_rule_only_mode(self) -> None:
        """Rule-only mode ignores content and module."""
        fp1 = compute_fingerprint("L046", "name: anything\n", mode="rule_only")
        fp2 = compute_fingerprint("L046", "name: something else\n", mode="rule_only")
        assert fp1 == fp2

    def test_rule_only_mode_different_rules(self) -> None:
        """Different rules produce different fingerprints in rule_only mode."""
        fp1 = compute_fingerprint("L046", "", mode="rule_only")
        fp2 = compute_fingerprint("L047", "", mode="rule_only")
        assert fp1 != fp2

    def test_rule_module_mode_empty_fqcn_raises(self) -> None:
        """Rule-module mode with empty module_fqcn raises ValueError."""
        with pytest.raises(ValueError, match="module_fqcn is required"):
            compute_fingerprint("L046", "", mode="rule_module", module_fqcn="")

    def test_rule_module_mode_none_fqcn_raises(self) -> None:
        """Rule-module mode with no module_fqcn raises ValueError."""
        with pytest.raises(ValueError, match="module_fqcn is required"):
            compute_fingerprint("L046", "", mode="rule_module")

    def test_invalid_mode_raises(self) -> None:
        """Invalid mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid fingerprint mode"):
            compute_fingerprint("L046", "name: test\n", mode="bogus")

    def test_canonicalizes_rule_id(self) -> None:
        """Prefixed and bare rule IDs produce the same fingerprint."""
        fp1 = compute_fingerprint("native:L046", "name: test\n")
        fp2 = compute_fingerprint("L046", "name: test\n")
        assert fp1 == fp2


class TestLoadSuppressions:
    """Tests for suppression file loading."""

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        """Missing suppressions file returns empty list.

        Args:
            tmp_path: Pytest temporary directory.
        """
        result = load_suppressions(tmp_path)
        assert result == []

    def test_valid_file(self, tmp_path: Path) -> None:
        """Valid suppressions file is parsed correctly.

        Args:
            tmp_path: Pytest temporary directory.
        """
        fp = "a" * 64
        (tmp_path / ".apme").mkdir()
        data = {
            "version": 1,
            "suppressions": [
                {
                    "fingerprint": fp,
                    "rule_id": "L046",
                    "mode": "full",
                    "reason": "Accepted",
                    "created": "2026-05-21",
                },
            ],
        }
        (tmp_path / ".apme" / "suppressions.yml").write_text(yaml.safe_dump(data))

        result = load_suppressions(tmp_path)
        assert len(result) == 1
        assert result[0].fingerprint == fp
        assert result[0].rule_id == "L046"
        assert result[0].mode == "full"
        assert result[0].reason == "Accepted"

    def test_unquoted_created_date_is_preserved(self, tmp_path: Path) -> None:
        """Unquoted YAML dates are normalized back to ISO strings.

        Args:
            tmp_path: Pytest temporary directory.
        """
        fp = "b" * 64
        (tmp_path / ".apme").mkdir()
        (tmp_path / ".apme" / "suppressions.yml").write_text(
            "\n".join(
                (
                    "version: 1",
                    "suppressions:",
                    f"  - fingerprint: {fp}",
                    "    rule_id: L046",
                    "    created: 2026-05-21",
                    "",
                ),
            ),
        )

        result = load_suppressions(tmp_path)

        assert len(result) == 1
        assert result[0].created == "2026-05-21"

    def test_mode_defaults_to_full(self, tmp_path: Path) -> None:
        """Missing mode field defaults to 'full'.

        Args:
            tmp_path: Pytest temporary directory.
        """
        fp = "b" * 64
        (tmp_path / ".apme").mkdir()
        data = {
            "version": 1,
            "suppressions": [
                {"fingerprint": fp, "rule_id": "L046"},
            ],
        }
        (tmp_path / ".apme" / "suppressions.yml").write_text(yaml.safe_dump(data))

        result = load_suppressions(tmp_path)
        assert result[0].mode == "full"

    def test_invalid_yaml_returns_empty(self, tmp_path: Path) -> None:
        """Malformed YAML returns empty list with warning.

        Args:
            tmp_path: Pytest temporary directory.
        """
        (tmp_path / ".apme").mkdir()
        (tmp_path / ".apme" / "suppressions.yml").write_text("{{invalid yaml")

        result = load_suppressions(tmp_path)
        assert result == []

    def test_missing_fingerprint_skipped(self, tmp_path: Path) -> None:
        """Entries without fingerprint are skipped.

        Args:
            tmp_path: Pytest temporary directory.
        """
        (tmp_path / ".apme").mkdir()
        fp = "c" * 64
        data = {
            "version": 1,
            "suppressions": [
                {"rule_id": "L046"},
                {"fingerprint": fp, "rule_id": "L047"},
            ],
        }
        (tmp_path / ".apme" / "suppressions.yml").write_text(yaml.safe_dump(data))

        result = load_suppressions(tmp_path)
        assert len(result) == 1
        assert result[0].rule_id == "L047"

    def test_invalid_mode_defaults_to_full(self, tmp_path: Path) -> None:
        """Invalid mode value defaults to 'full' with warning.

        Args:
            tmp_path: Pytest temporary directory.
        """
        fp = "d" * 64
        (tmp_path / ".apme").mkdir()
        data = {
            "version": 1,
            "suppressions": [
                {"fingerprint": fp, "rule_id": "L046", "mode": "bogus"},
            ],
        }
        (tmp_path / ".apme" / "suppressions.yml").write_text(yaml.safe_dump(data))

        result = load_suppressions(tmp_path)
        assert result[0].mode == "full"

    def test_unsupported_version_returns_empty(self, tmp_path: Path) -> None:
        """Unsupported version field causes all suppressions to be ignored.

        Args:
            tmp_path: Pytest temporary directory.
        """
        (tmp_path / ".apme").mkdir()
        data = {
            "version": 2,
            "suppressions": [
                {"fingerprint": "a" * 64, "rule_id": "L046"},
            ],
        }
        (tmp_path / ".apme" / "suppressions.yml").write_text(yaml.safe_dump(data))

        result = load_suppressions(tmp_path)
        assert result == []

    def test_invalid_fingerprint_format_skipped(self, tmp_path: Path) -> None:
        """Entries with non-SHA256 fingerprints are skipped during load.

        Args:
            tmp_path: Pytest temporary directory.
        """
        (tmp_path / ".apme").mkdir()
        data = {
            "version": 1,
            "suppressions": [
                {"fingerprint": "short", "rule_id": "L046"},
                {"fingerprint": "a" * 64, "rule_id": "L047"},
            ],
        }
        (tmp_path / ".apme" / "suppressions.yml").write_text(yaml.safe_dump(data))

        result = load_suppressions(tmp_path)
        assert len(result) == 1
        assert result[0].rule_id == "L047"


class TestWriteSuppressions:
    """Tests for writing suppression files."""

    def test_creates_directory_and_file(self, tmp_path: Path) -> None:
        """Creates .apme/ directory and suppressions.yml.

        Args:
            tmp_path: Pytest temporary directory.
        """
        fp = "e" * 64
        entries = [
            Suppression(
                fingerprint=fp,
                rule_id="L046",
                mode="full",
                reason="Test",
                created="2026-05-21",
            ),
        ]
        write_suppressions(tmp_path, entries)

        path = tmp_path / ".apme" / "suppressions.yml"
        assert path.exists()
        data = yaml.safe_load(path.read_text())
        assert data["version"] == 1
        assert len(data["suppressions"]) == 1
        assert data["suppressions"][0]["fingerprint"] == fp

    def test_omits_mode_when_full(self, tmp_path: Path) -> None:
        """Mode 'full' is omitted from output (it's the default).

        Args:
            tmp_path: Pytest temporary directory.
        """
        entries = [Suppression(fingerprint="f" * 64, rule_id="L046", mode="full")]
        write_suppressions(tmp_path, entries)

        data = yaml.safe_load((tmp_path / ".apme" / "suppressions.yml").read_text())
        assert "mode" not in data["suppressions"][0]

    def test_includes_mode_when_not_full(self, tmp_path: Path) -> None:
        """Non-default mode is included in output.

        Args:
            tmp_path: Pytest temporary directory.
        """
        entries = [Suppression(fingerprint="0" * 64, rule_id="L046", mode="rule_module")]
        write_suppressions(tmp_path, entries)

        data = yaml.safe_load((tmp_path / ".apme" / "suppressions.yml").read_text())
        assert data["suppressions"][0]["mode"] == "rule_module"


class TestApplySuppressions:
    """Tests for suppression matching logic."""

    def test_no_suppressions_all_active(self) -> None:
        """With no suppressions, all violations remain active."""
        violations: list[ViolationDict] = [{"rule_id": "L046", "original_yaml": "name: test\n"}]
        result = apply_suppressions(violations, [])
        assert len(result.active) == 1
        assert len(result.suppressed) == 0

    def test_matching_full_fingerprint_suppresses(self) -> None:
        """Violation matching a full-mode suppression is filtered out."""
        yaml_text = "name: Install nginx\nansible.builtin.shell: apt install nginx\n"
        fp = compute_fingerprint("L046", yaml_text)
        violations: list[ViolationDict] = [{"rule_id": "L046", "original_yaml": yaml_text}]
        suppressions = [Suppression(fingerprint=fp, rule_id="L046", mode="full")]

        result = apply_suppressions(violations, suppressions)
        assert len(result.active) == 0
        assert len(result.suppressed) == 1

    def test_non_matching_fingerprint_stays_active(self) -> None:
        """Violation not matching any suppression stays active."""
        violations: list[ViolationDict] = [{"rule_id": "L046", "original_yaml": "name: test\n"}]
        suppressions = [Suppression(fingerprint="0" * 64, rule_id="L046", mode="full")]

        result = apply_suppressions(violations, suppressions)
        assert len(result.active) == 1
        assert len(result.suppressed) == 0

    def test_enforced_rule_cannot_be_suppressed(self) -> None:
        """Enforced rules bypass suppression even when fingerprint matches."""
        yaml_text = "name: test\n"
        fp = compute_fingerprint("L046", yaml_text)
        violations: list[ViolationDict] = [{"rule_id": "L046", "original_yaml": yaml_text}]
        suppressions = [Suppression(fingerprint=fp, rule_id="L046", mode="full")]

        result = apply_suppressions(violations, suppressions, enforced_rules={"L046"})
        assert len(result.active) == 1
        assert len(result.suppressed) == 0

    def test_rule_only_mode_suppresses_any_content(self) -> None:
        """Rule-only mode suppresses all violations for that rule regardless of content."""
        fp = compute_fingerprint("L046", "", mode="rule_only")
        violations: list[ViolationDict] = [
            {"rule_id": "L046", "original_yaml": "name: first\n"},
            {"rule_id": "L046", "original_yaml": "name: second\n"},
        ]
        suppressions = [Suppression(fingerprint=fp, rule_id="L046", mode="rule_only")]

        result = apply_suppressions(violations, suppressions)
        assert len(result.active) == 0
        assert len(result.suppressed) == 2

    def test_rule_module_mode_uses_module_fqcn(self) -> None:
        """Rule-module mode matches on module_fqcn field."""
        fp = compute_fingerprint("L046", "", mode="rule_module", module_fqcn="ansible.builtin.shell")
        violations: list[ViolationDict] = [
            {
                "rule_id": "L046",
                "original_yaml": "name: test\n",
                "module_fqcn": "ansible.builtin.shell",
            },
        ]
        suppressions = [Suppression(fingerprint=fp, rule_id="L046", mode="rule_module")]

        result = apply_suppressions(violations, suppressions)
        assert len(result.active) == 0
        assert len(result.suppressed) == 1

    def test_rule_module_mode_different_module_not_suppressed(self) -> None:
        """Rule-module mode does not suppress violations for a different module."""
        fp = compute_fingerprint("L046", "", mode="rule_module", module_fqcn="ansible.builtin.shell")
        violations: list[ViolationDict] = [
            {
                "rule_id": "L046",
                "original_yaml": "name: test\n",
                "module_fqcn": "ansible.builtin.command",
            },
        ]
        suppressions = [Suppression(fingerprint=fp, rule_id="L046", mode="rule_module")]

        result = apply_suppressions(violations, suppressions)
        assert len(result.active) == 1
        assert len(result.suppressed) == 0

    def test_missing_original_yaml_uses_empty(self) -> None:
        """None original_yaml is treated as empty string for fingerprinting."""
        fp = compute_fingerprint("L046", "")
        violations: list[ViolationDict] = [{"rule_id": "L046", "original_yaml": None}]
        suppressions = [Suppression(fingerprint=fp, rule_id="L046", mode="full")]

        result = apply_suppressions(violations, suppressions)
        assert len(result.suppressed) == 1

    def test_mixed_violations_partitioned_correctly(self) -> None:
        """Suppressed and active violations are separated correctly."""
        yaml1 = "name: suppress me\n"
        yaml2 = "name: keep me\n"
        fp1 = compute_fingerprint("L046", yaml1)
        violations: list[ViolationDict] = [
            {"rule_id": "L046", "original_yaml": yaml1},
            {"rule_id": "L046", "original_yaml": yaml2},
        ]
        suppressions = [Suppression(fingerprint=fp1, rule_id="L046", mode="full")]

        result = apply_suppressions(violations, suppressions)
        assert len(result.active) == 1
        assert len(result.suppressed) == 1
        assert result.active[0]["original_yaml"] == yaml2
