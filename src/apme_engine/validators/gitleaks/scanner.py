"""Run gitleaks against a directory and parse JSON results into violation dicts."""

from __future__ import annotations

import bisect
import contextlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import cast

from apme_engine.engine.models import ViolationDict

GITLEAKS_BIN = "gitleaks"

RULE_PREFIX = "SEC"

RULE_ID_MAP: dict[str, str] = {}

_VAULT_HEADER = re.compile(r"^\s*\$ANSIBLE_VAULT;")
_JINJA_REF = re.compile(r"\{\{.*?\}\}")
_NODE_DELIMITER = "# __apme_node__ "


def _is_vault_encrypted(content: str) -> bool:
    """Check if content starts with Ansible Vault header.

    Args:
        content: File content to check.

    Returns:
        True if content appears vault-encrypted.
    """
    return bool(_VAULT_HEADER.search(content))


def _value_is_jinja(match_text: str) -> bool:
    """Check if match text is a Jinja template reference (false positive).

    Args:
        match_text: Gitleaks match text.

    Returns:
        True if text looks like Jinja (e.g. {{ var }}).
    """
    stripped = match_text.strip().strip("'\"")
    return bool(_JINJA_REF.fullmatch(stripped))


def _build_rule_id(gitleaks_rule_id: str) -> str:
    """Map gitleaks rule ID to APME rule ID (SEC: prefix).

    Args:
        gitleaks_rule_id: Raw gitleaks rule identifier.

    Returns:
        APME rule ID (e.g. SEC:rule-id).
    """
    if gitleaks_rule_id in RULE_ID_MAP:
        return RULE_ID_MAP[gitleaks_rule_id]
    return f"{RULE_PREFIX}:{gitleaks_rule_id}"


def run_gitleaks(scan_dir: str | Path, *, timeout: int = 120) -> list[dict[str, str | int | list[int] | None]]:
    """Run gitleaks detect on *scan_dir* (no git required) and return violation dicts.

    Args:
        scan_dir: Directory to scan.
        timeout: Timeout in seconds for gitleaks subprocess.

    Returns:
        List of violation dicts.
    """
    scan_dir = Path(scan_dir)
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tmp:
        report_path = tmp.name

    cmd = [
        GITLEAKS_BIN,
        "detect",
        "--no-git",
        "--source",
        str(scan_dir),
        "--report-format",
        "json",
        "--report-path",
        report_path,
        "--exit-code",
        "0",
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if proc.returncode not in (0, 1):
            sys.stderr.write(f"gitleaks exited {proc.returncode}: {proc.stderr[:500]}\n")
            sys.stderr.flush()
            return []
    except FileNotFoundError:
        sys.stderr.write("gitleaks binary not found; skipping secret scan\n")
        sys.stderr.flush()
        return []
    except subprocess.TimeoutExpired:
        sys.stderr.write(f"gitleaks timed out after {timeout}s\n")
        sys.stderr.flush()
        return []

    try:
        raw = Path(report_path).read_text()
        if not raw.strip():
            return []
        findings = cast(list[dict[str, object]], json.loads(raw))
    except (json.JSONDecodeError, OSError) as exc:
        sys.stderr.write(f"gitleaks report parse error: {exc}\n")
        sys.stderr.flush()
        return []
    finally:
        with contextlib.suppress(OSError):
            Path(report_path).unlink()

    return _convert_findings(findings, scan_dir)


def _convert_findings(
    findings: list[dict[str, object]], scan_dir: Path
) -> list[dict[str, str | int | list[int] | None]]:
    """Convert gitleaks JSON findings to APME violation dicts, filtering false positives.

    Args:
        findings: Raw gitleaks findings.
        scan_dir: Root directory for relative paths.

    Returns:
        List of APME violation dicts.
    """
    violations: list[dict[str, str | int | list[int] | None]] = []
    for f in findings:
        file_path = str(f.get("File", ""))
        match_text = str(f.get("Match", ""))

        try:
            rel = str(Path(file_path).relative_to(scan_dir))
        except ValueError:
            rel = file_path

        if _value_is_jinja(match_text):
            continue

        try:
            content = Path(file_path).read_text(errors="replace")
            if _is_vault_encrypted(content):
                continue
        except OSError:
            pass

        line_val = f.get("StartLine", 0)
        end_val = f.get("EndLine", line_val)
        line = int(line_val) if isinstance(line_val, int | float | str) else 0
        end_line = int(end_val) if isinstance(end_val, int | float | str) else line
        gitleaks_rule = str(f.get("RuleID", "unknown"))
        desc = str(f.get("Description", f"Secret detected: {gitleaks_rule}"))

        violations.append(
            {
                "rule_id": _build_rule_id(gitleaks_rule),
                "severity": "critical",
                "message": desc,
                "file": rel,
                "line": line if line == end_line else [line, end_line],
                "path": "",
                "scope": "playbook",
                "source": "gitleaks",
            }
        )

    return violations


# ---------------------------------------------------------------------------
# Node-native stdin scanning (Strategy 2 — concatenated with delimiters)
# ---------------------------------------------------------------------------


def _build_stdin_payload(
    nodes: list[tuple[str, str]],
) -> tuple[str, list[int], list[str], dict[str, str]]:
    """Concatenate node content with delimiter lines and build a line-to-node map.

    Args:
        nodes: ``(node_id, content)`` tuples.

    Returns:
        Tuple of ``(payload_text, delimiter_lines, node_ids,
        node_content_by_id)`` in the same order as ``nodes``, where
        ``delimiter_lines[i]`` is the 1-based line number of the delimiter
        for ``node_ids[i]``.
    """
    parts: list[str] = []
    delimiter_lines: list[int] = []
    node_ids: list[str] = []
    content_by_id: dict[str, str] = {}
    current_line = 1

    for node_id, content in nodes:
        delimiter = f"{_NODE_DELIMITER}{node_id}\n"
        parts.append(delimiter)
        delimiter_lines.append(current_line)
        node_ids.append(node_id)
        content_by_id[node_id] = content
        current_line += 1

        if content and not content.endswith("\n"):
            content += "\n"
        parts.append(content)
        current_line += content.count("\n")

    return "".join(parts), delimiter_lines, node_ids, content_by_id


def _resolve_node_id(
    finding_line: int,
    delimiter_lines: list[int],
    node_ids: list[str],
) -> tuple[str, int]:
    """Walk backwards from finding_line to the nearest delimiter.

    Args:
        finding_line: 1-based line from gitleaks StartLine.
        delimiter_lines: 1-based line numbers of delimiters (input order).
        node_ids: Parallel list of node IDs.

    Returns:
        Tuple of ``(node_id, delimiter_line)`` for the owning node,
        or ``("", 0)`` if before any delimiter.
    """
    idx = bisect.bisect_right(delimiter_lines, finding_line) - 1
    if idx < 0:
        return "", 0
    return node_ids[idx], delimiter_lines[idx]


def run_gitleaks_nodes(
    nodes: list[tuple[str, str]],
    *,
    timeout: int = 120,
) -> list[ViolationDict]:
    """Scan node content for secrets via ``gitleaks detect --pipe`` stdin.

    Concatenates all ``(node_id, content)`` with unique delimiter comments,
    pipes the result to gitleaks via stdin, and maps each finding back to
    the originating ``node_id`` by walking backwards from the reported
    line number to the nearest delimiter.

    Args:
        nodes: ``(node_id, content)`` tuples to scan.
        timeout: Subprocess timeout in seconds.

    Returns:
        List of violation dicts with ``path`` set to the owning ``node_id``.
    """
    if not nodes:
        return []

    payload, delimiter_lines, node_ids, content_by_id = _build_stdin_payload(nodes)

    cmd = [
        GITLEAKS_BIN,
        "detect",
        "--pipe",
        "--report-format",
        "json",
        "--report-path",
        "/dev/stdout",
        "--exit-code",
        "0",
    ]

    try:
        proc = subprocess.run(
            cmd,
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode not in (0, 1):
            sys.stderr.write(f"gitleaks exited {proc.returncode}: {proc.stderr[:500]}\n")
            sys.stderr.flush()
            return []
    except FileNotFoundError:
        sys.stderr.write("gitleaks binary not found; skipping secret scan\n")
        sys.stderr.flush()
        return []
    except subprocess.TimeoutExpired:
        sys.stderr.write(f"gitleaks timed out after {timeout}s\n")
        sys.stderr.flush()
        return []

    stdout = proc.stdout.strip()
    if not stdout:
        return []

    try:
        findings = cast(list[dict[str, object]], json.loads(stdout))
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"gitleaks JSON parse error: {exc}\n")
        sys.stderr.flush()
        return []

    violations: list[ViolationDict] = []
    for f in findings:
        match_text = str(f.get("Match", ""))
        if _value_is_jinja(match_text):
            continue

        line_val = f.get("StartLine", 0)
        end_val = f.get("EndLine", line_val)
        start_line = int(line_val) if isinstance(line_val, int | float | str) else 0
        end_line = int(end_val) if isinstance(end_val, int | float | str) else start_line

        node_id, delim_line = _resolve_node_id(start_line, delimiter_lines, node_ids)
        if not node_id:
            continue

        node_content = content_by_id.get(node_id, "")
        if _is_vault_encrypted(node_content):
            continue

        gitleaks_rule = str(f.get("RuleID", "unknown"))
        desc = str(f.get("Description", f"Secret detected: {gitleaks_rule}"))

        rel_start = max(1, start_line - delim_line)
        rel_end = max(1, end_line - delim_line)
        violations.append(
            {
                "rule_id": _build_rule_id(gitleaks_rule),
                "severity": "critical",
                "message": desc,
                "file": "",
                "line": rel_start if rel_start == rel_end else [rel_start, rel_end],
                "path": node_id,
                "scope": "playbook",
                "source": "gitleaks",
            }
        )

    return violations
