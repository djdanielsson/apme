"""Tests for AI escalation: protocol, batch prompt, patching, engine loop."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from apme_engine.engine.models import ViolationDict
from apme_engine.engine.node_index import NodeIndex
from apme_engine.remediation.abbenay_provider import (
    _build_batch_prompt,
    _extract_code_window,
    _extract_json_object,
    _get_best_practices_for_rule,
    _get_best_practices_for_rules,
    _load_best_practices,
    _parse_batch_response,
    _parse_unit_response,
    discover_abbenay,
)
from apme_engine.remediation.ai_provider import (
    AIPatch,
    AIProposal,
    AIProvider,
    AISkipped,
    _resolve_overlaps,
    apply_patches,
    generate_patch_hunks,
)
from apme_engine.remediation.engine import RemediationEngine, _chunk_violations
from apme_engine.remediation.registry import TransformRegistry

# ---------------------------------------------------------------------------
# Mock AIProvider for testing (batch API)
# ---------------------------------------------------------------------------


class MockAIProvider:
    """Mock AIProvider that returns canned patch lists."""

    def __init__(
        self,
        *,
        patch_results: list[list[AIPatch] | None] | None = None,
        skipped_results: list[list[AISkipped]] | None = None,
    ) -> None:
        """Initialize mock provider.

        Args:
            patch_results: List of patch lists to return in sequence.
                           Each call pops the first item.
            skipped_results: List of skipped lists to return in sequence.
        """
        self._results = list(patch_results or [])
        self._skipped = list(skipped_results or [])
        self.call_count = 0
        self.calls: list[dict[str, object]] = []

    async def propose_fixes(
        self,
        violations: list[ViolationDict],
        file_content: str,
        *,
        model: str | None = None,
        feedback: str | None = None,
    ) -> tuple[list[AIPatch] | None, list[AISkipped]]:
        """Return next canned patch list and skipped entries.

        Args:
            violations: Violations for one file.
            file_content: File content.
            model: Model identifier.
            feedback: Retry feedback.

        Returns:
            Tuple of (patches or None, skipped list).
        """
        self.calls.append(
            {
                "violations": violations,
                "file_content": file_content,
                "model": model,
                "feedback": feedback,
            }
        )
        self.call_count += 1
        patches = self._results.pop(0) if self._results else None
        skipped = self._skipped.pop(0) if self._skipped else []
        return patches, skipped

    async def propose_unit_fixes(
        self,
        violations: list[ViolationDict],
        snippet: str,
        file_path: str,
        line_start: int,
        line_end: int,
        *,
        model: str | None = None,
        feedback: str | None = None,
    ) -> tuple[list[AIPatch] | None, list[AISkipped]]:
        """Delegate to propose_fixes for mock simplicity.

        Args:
            violations: Violations for one unit.
            snippet: Unit snippet.
            file_path: File path.
            line_start: Unit start line.
            line_end: Unit end line.
            model: Model identifier.
            feedback: Retry feedback.

        Returns:
            Tuple of (patches or None, skipped list).
        """
        return await self.propose_fixes(violations, snippet, model=model, feedback=feedback)


# ---------------------------------------------------------------------------
# AIPatch and AIProposal tests
# ---------------------------------------------------------------------------


class TestAIPatch:
    """Tests for the AIPatch dataclass."""

    def test_create_patch(self) -> None:
        """AIPatch fields are set correctly."""
        p = AIPatch(
            rule_id="L026",
            line_start=10,
            line_end=12,
            fixed_lines="    - name: Do stuff\n      ansible.builtin.shell: echo hi\n",
            explanation="Added task name",
            confidence=0.95,
        )
        assert p.rule_id == "L026"
        assert p.line_start == 10
        assert p.line_end == 12
        assert p.diff_hunk == ""

    def test_default_diff_hunk(self) -> None:
        """diff_hunk defaults to empty string."""
        p = AIPatch(
            rule_id="X",
            line_start=1,
            line_end=1,
            fixed_lines="fixed\n",
            explanation="",
            confidence=0.5,
        )
        assert p.diff_hunk == ""


class TestAIProposal:
    """Tests for the updated AIProposal dataclass."""

    def test_rule_ids_property(self) -> None:
        """rule_ids field contains the rules addressed."""
        proposal = AIProposal(
            file="test.yml",
            original_snippet="orig\n",
            fixed_snippet="fixed\n",
            diff="diff",
            rule_ids=["L026", "M001"],
        )
        assert proposal.rule_ids == ["L026", "M001"]

    def test_confidence_field(self) -> None:
        """Confidence field stores the value."""
        proposal = AIProposal(
            file="t.yml",
            original_snippet="a\n",
            fixed_snippet="b\n",
            diff="",
            confidence=0.7,
        )
        assert proposal.confidence == 0.7

    def test_apply_content_based(self) -> None:
        """Apply replaces original snippet in current file content."""
        proposal = AIProposal(
            file="t.yml",
            original_snippet="- shell: hostname\n",
            fixed_snippet="- name: Get hostname\n  ansible.builtin.command: hostname\n",
            diff="",
        )
        content = "---\n- hosts: all\n  tasks:\n    - shell: hostname\n    - debug: msg=hi\n"
        result = proposal.apply(content)
        assert "ansible.builtin.command: hostname" in result
        assert "- shell: hostname" not in result
        assert "debug: msg=hi" in result

    def test_skipped_defaults_to_empty(self) -> None:
        """Skipped defaults to empty list."""
        proposal = AIProposal(
            file="t.yml",
            original_snippet="a\n",
            fixed_snippet="b\n",
            diff="",
        )
        assert proposal.skipped == []

    def test_skipped_populated(self) -> None:
        """Skipped list is preserved on proposal."""
        skipped = [AISkipped("P002", 10, "Cannot fix", "Do it manually")]
        proposal = AIProposal(
            file="t.yml",
            original_snippet="a\n",
            fixed_snippet="b\n",
            diff="",
            skipped=skipped,
        )
        assert len(proposal.skipped) == 1
        assert proposal.skipped[0].rule_id == "P002"


# ---------------------------------------------------------------------------
# apply_patches tests
# ---------------------------------------------------------------------------


class TestApplyPatches:
    """Tests for the apply_patches utility."""

    def test_single_patch(self) -> None:
        """Applies a single line-range patch."""
        content = "line1\nline2\nline3\nline4\n"
        patches = [AIPatch("R1", 2, 3, "new2\nnew3\n", "fix", 0.9)]
        result = apply_patches(content, patches)
        assert result == "line1\nnew2\nnew3\nline4\n"

    def test_multiple_non_overlapping(self) -> None:
        """Applies multiple non-overlapping patches bottom-up."""
        content = "a\nb\nc\nd\ne\n"
        patches = [
            AIPatch("R1", 2, 2, "B\n", "fix b", 0.9),
            AIPatch("R2", 4, 4, "D\n", "fix d", 0.9),
        ]
        result = apply_patches(content, patches)
        assert result == "a\nB\nc\nD\ne\n"

    def test_patch_changes_line_count(self) -> None:
        """Patch can add or remove lines."""
        content = "a\nb\nc\n"
        patches = [AIPatch("R1", 2, 2, "b1\nb2\nb3\n", "expand", 0.9)]
        result = apply_patches(content, patches)
        assert result == "a\nb1\nb2\nb3\nc\n"

    def test_patch_at_end_of_file(self) -> None:
        """Patch can replace the last line."""
        content = "a\nb\nc\n"
        patches = [AIPatch("R1", 3, 3, "C\n", "fix", 0.9)]
        result = apply_patches(content, patches)
        assert result == "a\nb\nC\n"

    def test_empty_patches_returns_original(self) -> None:
        """No patches returns original content unchanged."""
        content = "a\nb\nc\n"
        result = apply_patches(content, [])
        assert result == content

    def test_overlapping_patches_resolved(self) -> None:
        """Overlapping patches are resolved — higher confidence wins."""
        content = "a\nb\nc\nd\ne\n"
        patches = [
            AIPatch("R1", 2, 3, "X\nY\n", "fix1", 0.8),
            AIPatch("R2", 3, 4, "P\nQ\n", "fix2", 0.95),
        ]
        result = apply_patches(content, patches)
        assert "P\n" in result
        assert "Q\n" in result
        assert "X\n" not in result

    def test_adjacent_patches_no_overlap(self) -> None:
        """Adjacent but non-overlapping patches both apply."""
        content = "a\nb\nc\nd\n"
        patches = [
            AIPatch("R1", 1, 1, "A\n", "fix a", 0.9),
            AIPatch("R2", 2, 2, "B\n", "fix b", 0.9),
        ]
        result = apply_patches(content, patches)
        assert result == "A\nB\nc\nd\n"


# ---------------------------------------------------------------------------
# _resolve_overlaps tests
# ---------------------------------------------------------------------------


class TestResolveOverlaps:
    """Tests for the overlap resolution logic."""

    def test_no_overlaps(self) -> None:
        """Non-overlapping patches pass through unchanged."""
        patches = [
            AIPatch("R1", 1, 2, "a\n", "x", 0.9),
            AIPatch("R2", 5, 6, "b\n", "y", 0.9),
        ]
        result = _resolve_overlaps(patches)
        assert len(result) == 2

    def test_overlapping_keeps_higher_confidence(self) -> None:
        """When patches overlap, higher confidence wins."""
        low = AIPatch("R1", 2, 4, "low\n", "low", 0.5)
        high = AIPatch("R2", 3, 5, "high\n", "high", 0.95)
        result = _resolve_overlaps([low, high])
        assert len(result) == 1
        assert result[0].rule_id == "R2"

    def test_overlapping_tie_prefers_broader(self) -> None:
        """On confidence tie, broader patch wins."""
        narrow = AIPatch("R1", 3, 3, "narrow\n", "x", 0.9)
        broad = AIPatch("R2", 2, 5, "broad\n", "y", 0.9)
        result = _resolve_overlaps([narrow, broad])
        assert len(result) == 1
        assert result[0].rule_id == "R2"

    def test_empty_input(self) -> None:
        """Empty list returns empty."""
        assert _resolve_overlaps([]) == []

    def test_three_way_overlap(self) -> None:
        """Three overlapping patches — best one survives."""
        p1 = AIPatch("R1", 1, 3, "a\n", "x", 0.5)
        p2 = AIPatch("R2", 2, 4, "b\n", "y", 0.9)
        p3 = AIPatch("R3", 3, 5, "c\n", "z", 0.7)
        result = _resolve_overlaps([p1, p2, p3])
        assert len(result) == 1
        assert result[0].rule_id == "R2"


# ---------------------------------------------------------------------------
# AISkipped tests
# ---------------------------------------------------------------------------


class TestAISkipped:
    """Tests for the AISkipped dataclass."""

    def test_create_skipped(self) -> None:
        """AISkipped fields are set correctly."""
        s = AISkipped(
            rule_id="P002",
            line=45,
            reason="Cannot determine valid params for custom module.",
            suggestion="Remove 'invalid_param' if not valid.",
        )
        assert s.rule_id == "P002"
        assert s.line == 45
        assert "custom module" in s.reason
        assert "invalid_param" in s.suggestion


# ---------------------------------------------------------------------------
# generate_patch_hunks tests
# ---------------------------------------------------------------------------


class TestGeneratePatchHunks:
    """Tests for generating diff hunks per patch."""

    def test_generates_diff_hunk(self) -> None:
        """Each patch gets a diff_hunk populated."""
        content = "line1\nline2\nline3\n"
        patches = [AIPatch("R1", 2, 2, "LINE2\n", "upper", 0.9)]
        result = generate_patch_hunks(content, patches, "test.yml")
        assert result[0].diff_hunk
        assert "line2" in result[0].diff_hunk
        assert "LINE2" in result[0].diff_hunk

    def test_no_change_empty_hunk(self) -> None:
        """Patch that makes no change produces empty diff."""
        content = "line1\nline2\n"
        patches = [AIPatch("R1", 1, 1, "line1\n", "no change", 0.9)]
        result = generate_patch_hunks(content, patches, "test.yml")
        assert result[0].diff_hunk == ""


# ---------------------------------------------------------------------------
# AIProvider Protocol tests
# ---------------------------------------------------------------------------


class TestAIProviderProtocol:
    """Verify MockAIProvider satisfies the AIProvider protocol."""

    def test_mock_satisfies_protocol(self) -> None:
        """MockAIProvider is structurally compatible with AIProvider."""
        provider: AIProvider = MockAIProvider()
        assert hasattr(provider, "propose_fixes")


# ---------------------------------------------------------------------------
# discover_abbenay tests
# ---------------------------------------------------------------------------


class TestDiscoverAbbenay:
    """Tests for Abbenay daemon auto-discovery."""

    def test_discover_from_xdg(self, tmp_path: Path) -> None:
        """Discovers socket via XDG_RUNTIME_DIR.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        sock_dir = tmp_path / "abbenay"
        sock_dir.mkdir()
        sock_file = sock_dir / "daemon.sock"
        sock_file.touch()

        with patch.dict(os.environ, {"XDG_RUNTIME_DIR": str(tmp_path)}):
            result = discover_abbenay()

        assert result == f"unix://{sock_file}"

    def test_discover_from_tmp(self, tmp_path: Path) -> None:
        """Falls back to /tmp/abbenay/daemon.sock when XDG and /run/user paths miss.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        sock_dir = tmp_path / "abbenay"
        sock_dir.mkdir(parents=True)
        sock_file = sock_dir / "daemon.sock"
        sock_file.touch()

        orig_path = Path

        def _path_factory(*args: object, **kwargs: object) -> Path:
            if args == ("/tmp/abbenay/daemon.sock",):
                return sock_file
            if (
                len(args) == 1
                and isinstance(args[0], str)
                and "/run/user/" in args[0]
                and args[0].endswith("/abbenay/daemon.sock")
            ):
                return orig_path(tmp_path / "no-run-user-sock" / "daemon.sock")
            return orig_path(*args, **kwargs)  # type: ignore[arg-type]

        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "apme_engine.remediation.abbenay_provider.Path",
                side_effect=_path_factory,
            ),
        ):
            result = discover_abbenay()

        assert result == f"unix://{sock_file}"

    def test_discover_returns_none(self, tmp_path: Path) -> None:
        """Returns None when no socket exists.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        orig_path = Path

        def _path_factory(*args: object, **kwargs: object) -> Path:
            if len(args) == 1 and isinstance(args[0], str) and args[0].endswith("/abbenay/daemon.sock"):
                return orig_path(tmp_path / "missing" / "daemon.sock")
            return orig_path(*args, **kwargs)  # type: ignore[arg-type]

        with (
            patch.dict(os.environ, {"XDG_RUNTIME_DIR": str(tmp_path)}),
            patch(
                "apme_engine.remediation.abbenay_provider.Path",
                side_effect=_path_factory,
            ),
        ):
            result = discover_abbenay()

        assert result is None


# ---------------------------------------------------------------------------
# Batch prompt building tests
# ---------------------------------------------------------------------------


class TestBatchPromptBuilding:
    """Tests for batch prompt construction."""

    def test_build_batch_prompt_includes_violations(self) -> None:
        """Prompt lists all violations."""
        violations: list[ViolationDict] = [
            {"rule_id": "M001", "message": "Use FQCN", "file": "t.yml", "line": 5},
            {"rule_id": "L026", "message": "No name", "file": "t.yml", "line": 10},
        ]
        prompt = _build_batch_prompt(violations, "- debug: msg=hi\n", "t.yml")
        assert "M001" in prompt
        assert "L026" in prompt
        assert "Use FQCN" in prompt
        assert "No name" in prompt

    def test_build_batch_prompt_includes_file(self) -> None:
        """Prompt includes numbered file content."""
        violations: list[ViolationDict] = [
            {"rule_id": "X", "message": "m", "file": "t.yml", "line": 1},
        ]
        content = "---\n- hosts: all\n  tasks: []\n"
        prompt = _build_batch_prompt(violations, content, "t.yml")
        assert "1: ---" in prompt
        assert "2: - hosts: all" in prompt
        assert "3:   tasks: []" in prompt

    def test_build_batch_prompt_with_feedback(self) -> None:
        """Prompt includes feedback section on retry."""
        violations: list[ViolationDict] = [
            {"rule_id": "X", "message": "m", "file": "t.yml", "line": 1},
        ]
        prompt = _build_batch_prompt(
            violations,
            "content\n",
            "t.yml",
            feedback="Your patches introduced L042",
        )
        assert "Previous Attempt Feedback" in prompt
        assert "L042" in prompt

    def test_build_batch_prompt_best_practices(self) -> None:
        """Best practices include categories for all violations."""
        violations: list[ViolationDict] = [
            {"rule_id": "M001", "message": "FQCN", "file": "t.yml", "line": 1},
            {"rule_id": "L011", "message": "naming", "file": "t.yml", "line": 5},
        ]
        prompt = _build_batch_prompt(violations, "content\n", "t.yml")
        assert "FQCN" in prompt


# ---------------------------------------------------------------------------
# Batch response parsing tests
# ---------------------------------------------------------------------------


class TestBatchResponseParsing:
    """Tests for LLM batch response parsing."""

    def test_parse_valid_response(self) -> None:
        """Parses valid JSON batch response into AIPatch list."""
        response = json.dumps(
            {
                "patches": [
                    {
                        "rule_id": "M001",
                        "line_start": 2,
                        "line_end": 3,
                        "fixed_lines": "    - ansible.builtin.debug:\n        msg: hi\n",
                        "explanation": "Added FQCN",
                        "confidence": 0.95,
                    },
                    {
                        "rule_id": "L026",
                        "line_start": 5,
                        "line_end": 5,
                        "fixed_lines": "    - name: Do stuff\n",
                        "explanation": "Added name",
                        "confidence": 0.9,
                    },
                ]
            }
        )
        content = "\n".join(f"line{i}" for i in range(1, 11)) + "\n"
        patches, skipped = _parse_batch_response(response, content)
        assert patches is not None
        assert len(patches) == 2
        assert patches[0].rule_id == "M001"
        assert patches[1].rule_id == "L026"
        assert skipped == []

    def test_parse_invalid_json(self) -> None:
        """Returns None for invalid JSON."""
        patches, skipped = _parse_batch_response("not json", "content\n")
        assert patches is None
        assert skipped == []

    def test_parse_missing_patches_key(self) -> None:
        """Returns None when 'patches' key is missing and no skipped."""
        response = json.dumps({"explanation": "hi"})
        patches, skipped = _parse_batch_response(response, "content\n")
        assert patches is None
        assert skipped == []

    def test_parse_missing_patches_key_with_skipped(self) -> None:
        """Returns skipped entries even when 'patches' key is absent."""
        response = json.dumps(
            {
                "skipped": [
                    {
                        "rule_id": "R101",
                        "line": 5,
                        "reason": "Cannot fix automatically.",
                        "suggestion": "Review manually.",
                    },
                ],
            }
        )
        patches, skipped = _parse_batch_response(response, "content\n")
        assert patches is None
        assert len(skipped) == 1
        assert skipped[0].rule_id == "R101"

    def test_parse_skips_malformed_entries(self) -> None:
        """Skips entries missing required fields."""
        response = json.dumps(
            {
                "patches": [
                    {"rule_id": "M001"},
                    {
                        "rule_id": "L026",
                        "line_start": 1,
                        "line_end": 1,
                        "fixed_lines": "fixed\n",
                        "explanation": "ok",
                        "confidence": 0.9,
                    },
                ]
            }
        )
        patches, _ = _parse_batch_response(response, "line1\nline2\n")
        assert patches is not None
        assert len(patches) == 1
        assert patches[0].rule_id == "L026"

    def test_parse_skips_invalid_line_range(self) -> None:
        """Skips patches with line range outside file."""
        response = json.dumps(
            {
                "patches": [
                    {
                        "rule_id": "M001",
                        "line_start": 100,
                        "line_end": 105,
                        "fixed_lines": "fixed\n",
                        "explanation": "bad range",
                        "confidence": 0.9,
                    },
                ]
            }
        )
        patches, _ = _parse_batch_response(response, "line1\nline2\n")
        assert patches is None

    def test_parse_strips_markdown_fences(self) -> None:
        """Handles LLM responses wrapped in markdown code fences."""
        inner = json.dumps(
            {
                "patches": [
                    {
                        "rule_id": "M001",
                        "line_start": 1,
                        "line_end": 1,
                        "fixed_lines": "fixed\n",
                        "explanation": "ok",
                        "confidence": 0.9,
                    },
                ]
            }
        )
        wrapped = f"```json\n{inner}\n```"
        patches, _ = _parse_batch_response(wrapped, "line1\n")
        assert patches is not None
        assert len(patches) == 1

    def test_parse_skipped_violations(self) -> None:
        """Parses skipped violations alongside patches."""
        response = json.dumps(
            {
                "patches": [
                    {
                        "rule_id": "L026",
                        "line_start": 1,
                        "line_end": 1,
                        "fixed_lines": "fixed\n",
                        "explanation": "ok",
                        "confidence": 0.9,
                    },
                ],
                "skipped": [
                    {
                        "rule_id": "P002",
                        "line": 10,
                        "reason": "Cannot determine valid params for custom module.",
                        "suggestion": "Remove 'invalid_param' if not a valid argument.",
                    },
                ],
            }
        )
        patches, skipped = _parse_batch_response(response, "line1\nline2\n")
        assert patches is not None
        assert len(patches) == 1
        assert len(skipped) == 1
        assert skipped[0].rule_id == "P002"
        assert skipped[0].line == 10
        assert "custom module" in skipped[0].reason
        assert "invalid_param" in skipped[0].suggestion

    def test_parse_skipped_only(self) -> None:
        """Returns None patches but populated skipped when all skipped."""
        response = json.dumps(
            {
                "patches": [],
                "skipped": [
                    {
                        "rule_id": "R101",
                        "line": 5,
                        "reason": "Parameterized command is intentional.",
                        "suggestion": "Add a comment explaining why this is safe.",
                    },
                ],
            }
        )
        patches, skipped = _parse_batch_response(response, "line1\n")
        assert patches is None
        assert len(skipped) == 1
        assert skipped[0].rule_id == "R101"


# ---------------------------------------------------------------------------
# JSON extraction tests
# ---------------------------------------------------------------------------


class TestExtractJsonObject:
    """Tests for _extract_json_object which handles LLM preamble stripping."""

    def test_clean_json(self) -> None:
        """Parses clean JSON directly."""
        data = _extract_json_object('{"patches": []}')
        assert data == {"patches": []}

    def test_markdown_fences(self) -> None:
        """Strips markdown code fences."""
        data = _extract_json_object('```json\n{"patches": []}\n```')
        assert data == {"patches": []}

    def test_thinking_preamble(self) -> None:
        """Strips reasoning text before the JSON object."""
        text = (
            "Looking at the violations, I need to analyze the task context.\n\n"
            '{"patches": [{"rule_id": "M001", "line_start": 1, "line_end": 1, '
            '"fixed_lines": "fixed\\n", "explanation": "ok", "confidence": 0.9}]}'
        )
        data = _extract_json_object(text)
        assert data is not None
        assert len(data["patches"]) == 1
        assert data["patches"][0]["rule_id"] == "M001"

    def test_trailing_text(self) -> None:
        """Ignores text after the JSON object."""
        text = '{"patches": []} \n\nLet me know if you need anything else.'
        data = _extract_json_object(text)
        assert data == {"patches": []}

    def test_preamble_and_trailing(self) -> None:
        """Strips both preamble and trailing text."""
        text = 'Here is the fix:\n{"skipped": []}\nHope that helps!'
        data = _extract_json_object(text)
        assert data == {"skipped": []}

    def test_nested_braces(self) -> None:
        """Handles nested objects correctly."""
        inner = json.dumps(
            {
                "patches": [
                    {
                        "rule_id": "L026",
                        "line_start": 1,
                        "line_end": 2,
                        "fixed_lines": "- name: test\n",
                        "explanation": "ok",
                        "confidence": 0.9,
                    }
                ]
            }
        )
        text = f"Analysis complete.\n{inner}\nDone."
        data = _extract_json_object(text)
        assert data is not None
        assert data["patches"][0]["rule_id"] == "L026"

    def test_no_json(self) -> None:
        """Returns None when no JSON object is found."""
        assert _extract_json_object("no json here at all") is None

    def test_braces_in_strings(self) -> None:
        """Does not split on braces inside JSON string values."""
        text = '{"patches": [], "note": "use {item} syntax"}'
        data = _extract_json_object(text)
        assert data is not None
        assert data["note"] == "use {item} syntax"

    def test_empty_response(self) -> None:
        """Returns None for empty input."""
        assert _extract_json_object("") is None
        assert _extract_json_object("   ") is None

    def test_end_to_end_with_parse(self) -> None:
        """Full round-trip: preamble + JSON parsed into patches."""
        inner = json.dumps(
            {
                "patches": [
                    {
                        "rule_id": "M001",
                        "line_start": 1,
                        "line_end": 1,
                        "fixed_lines": "- ansible.builtin.debug:\n",
                        "explanation": "FQCN",
                        "confidence": 0.95,
                    }
                ]
            }
        )
        text = f"I need to analyze the violations carefully.\n\n{inner}"
        patches, skipped = _parse_batch_response(text, "line1\n")
        assert patches is not None
        assert len(patches) == 1
        assert patches[0].rule_id == "M001"


# ---------------------------------------------------------------------------
# _parse_unit_response / fixed_snippet tests
# ---------------------------------------------------------------------------


class TestParseUnitResponse:
    """Tests for _parse_unit_response which handles fixed_snippet contract."""

    def test_basic_fix(self) -> None:
        """Parses a clean fixed_snippet response."""
        original = "- shell: hostname\n"
        fixed = "- name: Get hostname\n  ansible.builtin.command: hostname\n  changed_when: false\n"
        response = json.dumps(
            {
                "fixed_snippet": fixed,
                "changes": [
                    {"rule_id": "L024", "explanation": "Added task name", "confidence": 0.95},
                    {"rule_id": "L007", "explanation": "shell->command", "confidence": 0.9},
                ],
                "skipped": [],
            }
        )
        patches, skipped = _parse_unit_response(response, original, 18, 18)
        assert patches is not None
        assert len(patches) == 1
        assert patches[0].line_start == 18
        assert patches[0].line_end == 18
        assert "ansible.builtin.command" in patches[0].fixed_lines
        assert "L024" in patches[0].rule_id
        assert "L007" in patches[0].rule_id
        assert patches[0].confidence > 0.9
        assert skipped == []

    def test_unchanged_snippet_returns_none(self) -> None:
        """Returns None when LLM returns the same snippet."""
        original = "- name: Test\n  debug:\n    msg: hello\n"
        response = json.dumps(
            {
                "fixed_snippet": original,
                "changes": [],
                "skipped": [{"rule_id": "L026", "reason": "Cannot fix"}],
            }
        )
        patches, skipped = _parse_unit_response(response, original, 10, 12)
        assert patches is None
        assert len(skipped) == 1

    def test_missing_fixed_snippet(self) -> None:
        """Returns None when fixed_snippet is missing."""
        response = json.dumps({"changes": [], "skipped": []})
        patches, skipped = _parse_unit_response(response, "content\n", 1, 1)
        assert patches is None

    def test_missing_fixed_snippet_with_skipped(self) -> None:
        """Returns skipped entries even when fixed_snippet is missing."""
        response = json.dumps(
            {
                "skipped": [{"rule_id": "R101", "reason": "Risky"}],
            }
        )
        patches, skipped = _parse_unit_response(response, "content\n", 1, 1)
        assert patches is None
        assert len(skipped) == 1

    def test_invalid_json(self) -> None:
        """Returns None for unparseable response."""
        patches, skipped = _parse_unit_response("not json", "content\n", 1, 1)
        assert patches is None
        assert skipped == []

    def test_with_preamble(self) -> None:
        """Handles LLM preamble before JSON."""
        original = "- debug: msg=hi\n"
        fixed = "- name: Show message\n  ansible.builtin.debug:\n    msg: hi\n"
        inner = json.dumps(
            {
                "fixed_snippet": fixed,
                "changes": [{"rule_id": "L024", "explanation": "Added name", "confidence": 0.95}],
                "skipped": [],
            }
        )
        text = f"Here is the corrected YAML:\n{inner}"
        patches, _ = _parse_unit_response(text, original, 5, 5)
        assert patches is not None
        assert len(patches) == 1

    def test_default_confidence(self) -> None:
        """Uses 0.85 default when changes lack confidence."""
        original = "- shell: echo hi\n"
        response = json.dumps(
            {
                "fixed_snippet": "- name: Echo\n  ansible.builtin.command: echo hi\n",
                "changes": [{"rule_id": "L007", "explanation": "fixed"}],
                "skipped": [],
            }
        )
        patches, _ = _parse_unit_response(response, original, 1, 1)
        assert patches is not None
        assert patches[0].confidence == 0.85


# ---------------------------------------------------------------------------
# Chunk violations tests
# ---------------------------------------------------------------------------


class TestChunkViolations:
    """Tests for violation chunking."""

    def test_no_chunking_needed(self) -> None:
        """Returns single chunk when under limit."""
        violations: list[ViolationDict] = [{"rule_id": f"R{i}"} for i in range(10)]
        chunks = _chunk_violations(violations, 40)
        assert len(chunks) == 1
        assert len(chunks[0]) == 10

    def test_chunking_splits(self) -> None:
        """Splits violations into correct chunk sizes."""
        violations: list[ViolationDict] = [{"rule_id": f"R{i}"} for i in range(100)]
        chunks = _chunk_violations(violations, 40)
        assert len(chunks) == 3
        assert len(chunks[0]) == 40
        assert len(chunks[1]) == 40
        assert len(chunks[2]) == 20


# ---------------------------------------------------------------------------
# Code window and best practices tests (backward compat)
# ---------------------------------------------------------------------------


class TestPromptHelpers:
    """Tests for prompt construction helpers."""

    def test_extract_code_window(self) -> None:
        """Extracts correct window around a line."""
        content = "\n".join(f"line {i}" for i in range(1, 31))
        window, start, end = _extract_code_window(content, 15, context=3)
        assert start == 12
        assert end == 18
        assert "line 15" in window

    def test_extract_code_window_near_start(self) -> None:
        """Handles lines near the start of file."""
        content = "\n".join(f"line {i}" for i in range(1, 11))
        window, start, end = _extract_code_window(content, 2, context=5)
        assert start == 1
        assert "line 1" in window
        assert "line 2" in window


class TestBestPractices:
    """Tests for best practices mapping loading."""

    def test_load_best_practices(self) -> None:
        """Best practices YAML loads successfully."""
        bp = _load_best_practices()
        assert "universal" in bp
        assert "fqcn" in bp
        assert len(bp["universal"]) > 5

    def test_get_best_practices_for_fqcn(self) -> None:
        """Returns FQCN-specific practices for M001."""
        result = _get_best_practices_for_rule("M001")
        assert "FQCN" in result

    def test_get_best_practices_for_unknown_rule(self) -> None:
        """Returns universal practices for unknown rules."""
        result = _get_best_practices_for_rule("UNKNOWN999")
        assert "idempotent" in result.lower() or "YAML" in result

    def test_get_best_practices_for_multiple_rules(self) -> None:
        """Returns combined practices for multiple rule categories."""
        result = _get_best_practices_for_rules(["M001", "L011"])
        assert "FQCN" in result


# ---------------------------------------------------------------------------
# Engine AI escalation tests (batch)
# ---------------------------------------------------------------------------


class TestEngineAIEscalation:
    """Tests for AI escalation in RemediationEngine (unit-level)."""

    @staticmethod
    def _make_node_index(playbook: Path) -> NodeIndex:
        """Build a minimal NodeIndex covering a 2-line task at lines 1-2.

        Args:
            playbook: Path to the playbook file.

        Returns:
            NodeIndex with a single task node.
        """
        payload = {
            "hierarchy": [
                {
                    "nodes": [
                        {"key": "task0", "type": "taskcall", "file": str(playbook), "line": [1, 2]},
                    ]
                }
            ]
        }
        return NodeIndex(payload)

    def _make_patches(
        self,
        rule_id: str = "UNKNOWN_AI",
        line_start: int = 1,
        line_end: int = 2,
        fixed: str = "- name: test\n  ansible.builtin.debug:\n    msg: hi\n",
    ) -> list[AIPatch]:
        """Create test AIPatch list.

        Args:
            rule_id: Rule ID for the patch.
            line_start: Start line.
            line_end: End line.
            fixed: Replacement text.

        Returns:
            Single-element list of AIPatch.
        """
        return [
            AIPatch(
                rule_id=rule_id,
                line_start=line_start,
                line_end=line_end,
                fixed_lines=fixed,
                explanation="Fixed",
                confidence=0.92,
            )
        ]

    def test_engine_skips_ai_when_no_provider(self, tmp_path: Path) -> None:
        """Engine returns empty ai_proposed when no provider set.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        playbook = tmp_path / "play.yml"
        playbook.write_text("- name: test\n  debug: msg=hi\n")

        def scan_fn(paths: list[str]) -> list[ViolationDict]:
            return [
                {
                    "rule_id": "UNKNOWN_AI",
                    "file": str(playbook),
                    "line": 1,
                },
            ]

        reg = TransformRegistry()
        engine = RemediationEngine(reg, scan_fn, max_passes=1)
        report = engine.remediate([str(playbook)], apply=False)

        assert len(report.remaining_ai) == 1
        assert len(report.ai_proposed) == 0

    def test_engine_calls_ai_provider_unit(self, tmp_path: Path) -> None:
        """Engine calls AI provider via unit path with NodeIndex.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        playbook = tmp_path / "play.yml"
        content = "- name: test\n  debug: msg=hi\n"
        playbook.write_text(content)
        node_index = self._make_node_index(playbook)

        def scan_fn(paths: list[str]) -> list[ViolationDict]:
            current = Path(paths[0]).read_text()
            if "ansible.builtin.debug" in current:
                return []
            return [
                {
                    "rule_id": "UNKNOWN_AI",
                    "file": str(playbook),
                    "line": 2,
                },
            ]

        patches = self._make_patches()
        provider = MockAIProvider(patch_results=[patches])
        reg = TransformRegistry()
        engine = RemediationEngine(
            reg,
            scan_fn,
            max_passes=1,
            ai_provider=provider,
            node_index=node_index,
        )
        report = engine.remediate([str(playbook)], apply=False)

        assert provider.call_count == 1
        assert len(report.ai_proposed) == 1
        assert len(report.ai_proposed[0].patches) == 1

    def test_engine_ai_failed_on_none_response(self, tmp_path: Path) -> None:
        """Engine sets remaining_ai when provider returns None for all units.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        playbook = tmp_path / "play.yml"
        playbook.write_text("- name: test\n  debug: msg=hi\n")
        node_index = self._make_node_index(playbook)

        def scan_fn(paths: list[str]) -> list[ViolationDict]:
            return [
                {
                    "rule_id": "UNKNOWN_AI",
                    "file": str(playbook),
                    "line": 1,
                },
            ]

        provider = MockAIProvider(patch_results=[None, None])
        reg = TransformRegistry()
        engine = RemediationEngine(
            reg,
            scan_fn,
            max_passes=1,
            ai_provider=provider,
            node_index=node_index,
        )
        report = engine.remediate([str(playbook)], apply=False)

        assert len(report.ai_proposed) == 0

    def test_engine_groups_by_file(self, tmp_path: Path) -> None:
        """Engine groups violations by file for unit-level AI calls.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        play1 = tmp_path / "play1.yml"
        play2 = tmp_path / "play2.yml"
        play1.write_text("- name: a\n  debug: msg=1\n")
        play2.write_text("- name: b\n  debug: msg=2\n")

        payload = {
            "hierarchy": [
                {
                    "nodes": [
                        {"key": "t0", "type": "taskcall", "file": str(play1), "line": [1, 2]},
                        {"key": "t1", "type": "taskcall", "file": str(play2), "line": [1, 2]},
                    ]
                }
            ]
        }
        node_index = NodeIndex(payload)

        def scan_fn(paths: list[str]) -> list[ViolationDict]:
            result: list[ViolationDict] = []
            for p in paths:
                current = Path(p).read_text()
                if "ansible.builtin" not in current:
                    result.append({"rule_id": "UNKNOWN_AI", "file": p, "line": 2})
            return result

        patches1 = [AIPatch("UNKNOWN_AI", 1, 2, "- name: a\n  ansible.builtin.debug:\n    msg: 1\n", "FQCN", 0.9)]
        patches2 = [AIPatch("UNKNOWN_AI", 1, 2, "- name: b\n  ansible.builtin.debug:\n    msg: 2\n", "FQCN", 0.9)]
        provider = MockAIProvider(patch_results=[patches1, patches2])
        reg = TransformRegistry()
        engine = RemediationEngine(
            reg,
            scan_fn,
            max_passes=1,
            ai_provider=provider,
            node_index=node_index,
        )
        report = engine.remediate([str(play1), str(play2)], apply=False)

        assert provider.call_count == 2
        assert len(report.ai_proposed) == 2
