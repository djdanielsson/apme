#!/usr/bin/env python3
"""Scrape ansible-core devel branch for version-gated deprecation notices.

Clones (or updates) the ansible/ansible devel branch into a local cache,
then extracts all deprecation patterns using three detection mechanisms:

  1. display.deprecated() calls — active runtime warnings
  2. # deprecated: comments — staged deprecations not yet active
  3. _tags.Deprecated() — tag-based deprecation system (2.19+)

Output is written to a machine-readable JSON file that can be consumed by
``generate_deprecation_rules.py`` to scaffold APME M-rules.

Usage:
    python scripts/scrape_ansible_deprecations.py [--output PATH] [--cache-dir PATH]

The default output is ``src/apme_engine/data/deprecations.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import textwrap
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "src" / "apme_engine" / "data" / "deprecations.json"
DEFAULT_CACHE = REPO_ROOT / ".cache" / "ansible-core"
ANSIBLE_REPO = "https://github.com/ansible/ansible.git"
ANSIBLE_LIB = "lib/ansible"

# ── Regex patterns for deprecation extraction ────────────────────────

# display.deprecated("message", version="X.YZ") — handles f-strings,
# concatenated strings, and multi-line calls.
_DEPRECATED_CALL = re.compile(
    r"""display\.deprecated\(\s*
        (?P<quote>["']{1,3})(?P<message>.*?)(?P=quote)  # message string
        [^)]*?                                            # everything before closing
        version\s*=\s*["'](?P<version>[\d.]+)["']         # version="2.23"
    """,
    re.VERBOSE | re.DOTALL,
)

# Alternate form: version is the second positional arg.
_DEPRECATED_CALL_POS = re.compile(
    r"""display\.deprecated\(\s*
        (?P<quote>["']{1,3})(?P<message>.*?)(?P=quote)\s*,\s*
        ["'](?P<version>[\d.]+)["']                        # positional version
    """,
    re.VERBOSE | re.DOTALL,
)

# display.deprecated("message", date=datetime.date(Y, M, D))
_DEPRECATED_DATE_CALL = re.compile(
    r"""display\.deprecated\(\s*
        (?P<quote>["']{1,3})(?P<message>.*?)(?P=quote)
        [^)]*?
        date\s*=\s*datetime\.date\((?P<year>\d+),\s*(?P<month>\d+),\s*(?P<day>\d+)\)
    """,
    re.VERBOSE | re.DOTALL,
)

# # deprecated: <version> — staged comment-based deprecation
_DEPRECATED_COMMENT = re.compile(
    r"#\s*deprecated:\s*(?P<version>[\d.]+)\s*(?:[-—:]\s*(?P<note>.*))?",
    re.IGNORECASE,
)

# _tags.Deprecated(version="X.Y")
_DEPRECATED_TAG = re.compile(
    r"_tags\.Deprecated\(\s*(?:version\s*=\s*)?[\"'](?P<version>[\d.]+)[\"']",
)

# collection_name kwarg
_COLLECTION_NAME = re.compile(
    r"collection_name\s*=\s*[\"'](?P<collection>[^\"']+)[\"']",
)


# ── Audience and detectability classification ────────────────────────

_CONTENT_PATHS = [
    "parsing/mod_args",
    "parsing/dataloader",
    "playbook/",
    "vars/manager",
    "vars/hostvars",
    "plugins/lookup/",
    "plugins/callback/tree",
    "plugins/callback/oneline",
    "plugins/connection/paramiko",
    "plugins/inventory/",
    "executor/task_executor",
    "plugins/filter/core",
    "plugins/action/include_vars",
    "_internal/_yaml/",
    "_internal/_templating/",
]

_DEV_PATHS = [
    "template/__init__",
    "module_utils/",
    "errors/",
    "compat/",
    "plugins/cache/base",
    "plugins/shell/",
    "parsing/yaml/objects",
    "parsing/ajson",
    "parsing/utils/jsonify",
    "utils/listify",
]

_CONTENT_KW = [
    "playbook",
    "task",
    "play_hosts",
    "ansible_hostname",
    "ansible_facts",
    "when:",
    "when ",
    "conditional",
    "args:",
    "action:",
    "connection:",
    "strategy:",
    "callback",
    "inventory",
    "!!omap",
    "!!pairs",
    "vault",
    "include",
    "yum_repository",
    "follow_redirects",
    "first_found",
    "variable name",
    "host_var",
    "group_var",
    "ignore_files",
    "paramiko_ssh",
    "tree callback",
    "oneline callback",
]

_DEV_KW = [
    "templar",
    "ansiblemodule",
    "jsonify",
    "exit_json",
    "fail_json",
    "import ",
    "api ",
    "class ",
    "method ",
    "function ",
    "argument_spec",
    "_available_variables",
    "do_template",
    "set_temporary_context",
    "copy_with_new_env",
    "module_utils",
    "suppress_extended_error",
    "AnsibleFilterTypeError",
    "_AnsibleActionDone",
    "importlib_resources",
    "ShellModule",
    "checksum()",
    "wrap_for_exec",
    "_encode_script",
]

_STATIC_SIGS = {
    "paramiko_ssh": "connection: paramiko_ssh in plays/host vars",
    "paramiko": "connection: paramiko_ssh in plays/host vars",
    "follow_redirects": "follow_redirects: yes/no in lookup args",
    "!!omap": "!!omap YAML tag in content",
    "!!pairs": "!!pairs YAML tag in content",
    "!vault-encrypted": "!vault-encrypted tag in YAML",
    "vault-encrypted": "!vault-encrypted tag in YAML",
    "empty conditional": "when: with empty/null value",
    "when:": "when condition pattern",
    "empty when": "when: with empty/null value",
    "action:": "action: with dict value in task",
    "action as a mapping": "action: with dict value in task",
    "empty args": "empty args: keyword in task",
    "play_hosts": "play_hosts variable in Jinja2",
    "ansible_hostname": "ansible_* fact variables in Jinja2",
    "inject_facts": "top-level fact injection",
    "tree": "callback plugin reference",
    "oneline": "callback plugin reference",
    "include_vars": "include_vars parameter patterns",
    "ignore_files": "include_vars ignore_files pattern",
    "first_found": "first_found lookup terms",
    "variable name": "variable naming validation",
    "k=v": "legacy k=v argument merging",
    "_meta": "inventory script _meta.hostvars",
    "strategy plugin": "third-party strategy plugin",
}

_RUNTIME_KW = [
    "runtime",
    "data type",
    "non-string input",
    "non-boolean",
    "return value",
    "filter coercing",
    "encoding",
]


def _classify_audience(filepath: str, message: str) -> str:
    """Classify whether a deprecation targets content authors or plugin devs.

    Args:
        filepath: Relative path under lib/ansible for the deprecation source.
        message: Deprecation message text used for keyword heuristics.

    Returns:
        ``content``, ``developer``, or ``unknown`` audience label.
    """
    for p in _CONTENT_PATHS:
        if p in filepath:
            return "content"
    for p in _DEV_PATHS:
        if p in filepath:
            return "developer"

    msg_lower = message.lower()
    for kw in _CONTENT_KW:
        if kw in msg_lower:
            return "content"
    for kw in _DEV_KW:
        if kw in msg_lower:
            return "developer"
    return "unknown"


def _classify_detectable(filepath: str, message: str) -> tuple[bool | None, str]:
    """Classify whether APME can detect this deprecation statically.

    Args:
        filepath: Relative path under lib/ansible for the deprecation source.
        message: Deprecation message text to match against static/runtime hints.

    Returns:
        Pair of static detectability (``True``/``False``/``None``) and hint string.
    """
    msg_lower = message.lower()

    for sig, hint in _STATIC_SIGS.items():
        if sig in msg_lower:
            return True, hint

    for kw in _RUNTIME_KW:
        if kw in msg_lower:
            return False, "Depends on runtime data"

    return None, ""


def _fingerprint(source_file: str, line_number: int, message: str) -> str:
    """Stable hash for deduplication across scrape runs.

    Args:
        source_file: Relative path of the source file.
        line_number: 1-based line number of the deprecation.
        message: Deprecation message (first 80 chars participate in the hash).

    Returns:
        12-character hex SHA-256 digest prefix.
    """
    raw = f"{source_file}:{line_number}:{message[:80]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


# ── Data classes ─────────────────────────────────────────────────────


@dataclass
class DeprecationEntry:
    """A single deprecation notice extracted from ansible-core source.

    Attributes:
        source_file: Path of the file relative to lib/ansible.
        line_number: 1-based line where the notice was found.
        mechanism: How it was detected (e.g. display.deprecated, comment, tag).
        removal_version: Target removal version or date-prefixed string.
        message: Normalized deprecation text.
        fingerprint: Short stable hash for deduplication.
        context_lines: Surrounding source lines for context.
        collection_name: Declaring collection (default ansible.builtin).
        audience: content, developer, or unknown.
        statically_detectable: Whether APME can detect it statically, if known.
        detection_hint: Short hint when statically detectable or why not.
    """

    source_file: str
    line_number: int
    mechanism: str
    removal_version: str
    message: str
    fingerprint: str = ""
    context_lines: list[str] = field(default_factory=list)
    collection_name: str = "ansible.builtin"
    audience: str = "unknown"
    statically_detectable: bool | None = None
    detection_hint: str = ""


@dataclass
class ScrapeResult:
    """Complete scrape output with metadata.

    Attributes:
        scraped_at: UTC ISO-8601 timestamp of the scrape.
        commit: ansible/ansible HEAD commit hash.
        branch: Git branch that was scraped.
        ansible_core_version: Value from lib/ansible/release.py or unknown.
        total_deprecations: Count of deprecation records after filtering.
        by_version: Counts keyed by removal_version.
        by_mechanism: Counts keyed by mechanism.
        by_audience: Counts keyed by audience.
        deprecations: List of deprecation dicts (asdict of DeprecationEntry).
    """

    scraped_at: str
    commit: str
    branch: str
    ansible_core_version: str
    total_deprecations: int
    by_version: dict[str, int]
    by_mechanism: dict[str, int]
    by_audience: dict[str, int]
    deprecations: list[dict[str, Any]]


# ── Git helpers ──────────────────────────────────────────────────────


def _run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    """Run a subprocess and return the result.

    Args:
        cmd: Executable and arguments passed to subprocess.run.
        **kwargs: Extra arguments forwarded to subprocess.run.

    Returns:
        CompletedProcess from a successful run (raises on non-zero exit).
    """
    return subprocess.run(  # type: ignore[call-overload,no-any-return]
        cmd, check=True, capture_output=True, text=True, **kwargs
    )


def clone_or_update(cache_dir: Path, branch: str = "devel") -> Path:
    """Clone ansible/ansible or fetch latest; return path to the repo.

    Args:
        cache_dir: Local directory for the clone or existing repo.
        branch: Remote branch to check out (default devel).

    Returns:
        Absolute path to the repository root (same as cache_dir).
    """
    if cache_dir.exists() and (cache_dir / ".git").exists():
        print(f"Updating existing clone at {cache_dir}…", file=sys.stderr)
        _run(["git", "fetch", "origin", branch], cwd=cache_dir)
        _run(["git", "checkout", f"origin/{branch}"], cwd=cache_dir)
    else:
        print(f"Cloning ansible-core into {cache_dir}…", file=sys.stderr)
        cache_dir.parent.mkdir(parents=True, exist_ok=True)
        _run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                branch,
                "--single-branch",
                ANSIBLE_REPO,
                str(cache_dir),
            ]
        )
    return cache_dir


def get_commit(repo_dir: Path) -> str:
    """Return the current HEAD full commit hash.

    Args:
        repo_dir: Root of the git checkout.

    Returns:
        Full 40-character commit SHA from ``git rev-parse HEAD``.
    """
    result = _run(["git", "rev-parse", "HEAD"], cwd=repo_dir)
    return result.stdout.strip()


def get_ansible_version(repo_dir: Path) -> str:
    """Extract ansible-core version from lib/ansible/release.py.

    Args:
        repo_dir: Root of the ansible/ansible checkout.

    Returns:
        __version__ string from release.py, or ``unknown`` if missing.
    """
    release_py = repo_dir / ANSIBLE_LIB / "release.py"
    if release_py.exists():
        text = release_py.read_text(encoding="utf-8")
        m = re.search(r"__version__\s*=\s*[\"']([^\"']+)[\"']", text)
        if m:
            return m.group(1)
    return "unknown"


# ── File scanning ────────────────────────────────────────────────────


def _get_context(lines: list[str], line_idx: int, window: int = 3) -> list[str]:
    """Return surrounding lines for context.

    Args:
        lines: Full file split into lines (no trailing newlines).
        line_idx: 0-based index of the center line.
        window: Number of lines to include before and after the center.

    Returns:
        Slice of lines from index ``line_idx - window`` through ``line_idx + window``.
    """
    start = max(0, line_idx - window)
    end = min(len(lines), line_idx + window + 1)
    return lines[start:end]


def scan_file(filepath: Path, base_dir: Path) -> list[DeprecationEntry]:
    """Scan a single Python file for all deprecation patterns.

    Args:
        filepath: Absolute path to the Python file under base_dir.
        base_dir: ansible lib root used to compute relative source_file paths.

    Returns:
        Extracted deprecation entries; empty list on read errors.
    """
    entries: list[DeprecationEntry] = []
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return entries

    lines = text.splitlines()
    rel_path = str(filepath.relative_to(base_dir))
    seen_spans: set[tuple[int, int]] = set()

    def _add_entry(m_start: int, mechanism: str, version: str, msg: str, collection: str = "ansible.builtin") -> None:
        """Deduplicate by character span and add entry.

        Args:
            m_start: Start index in file text of the regex match.
            mechanism: Detection mechanism name for the entry.
            version: Removal version or date string from the match.
            msg: Raw deprecation message text.
            collection: Declaring collection name (default ansible.builtin).
        """
        line_no = text[:m_start].count("\n") + 1
        span_key = (line_no, hash(msg[:60]))
        if span_key in seen_spans:
            return
        seen_spans.add(span_key)

        msg = re.sub(r"\s+", " ", msg.strip())
        audience = _classify_audience(rel_path, msg)
        detectable, hint = _classify_detectable(rel_path, msg)
        fp = _fingerprint(rel_path, line_no, msg)

        entries.append(
            DeprecationEntry(
                source_file=rel_path,
                line_number=line_no,
                mechanism=mechanism,
                removal_version=version,
                message=msg,
                fingerprint=fp,
                context_lines=_get_context(lines, line_no - 1),
                collection_name=collection,
                audience=audience,
                statically_detectable=detectable,
                detection_hint=hint,
            )
        )

    # 1. display.deprecated() with version= keyword arg
    for m in _DEPRECATED_CALL.finditer(text):
        collection = "ansible.builtin"
        cm = _COLLECTION_NAME.search(m.group(0))
        if cm:
            collection = cm.group("collection")
        _add_entry(m.start(), "display.deprecated", m.group("version"), m.group("message"), collection)

    # 2. display.deprecated() with positional version
    for m in _DEPRECATED_CALL_POS.finditer(text):
        _add_entry(m.start(), "display.deprecated", m.group("version"), m.group("message"))

    # 3. display.deprecated() with date= instead of version
    for m in _DEPRECATED_DATE_CALL.finditer(text):
        year, month, day = m.group("year"), m.group("month"), m.group("day")
        version = f"date:{year}-{month.zfill(2)}-{day.zfill(2)}"
        _add_entry(m.start(), "display.deprecated", version, m.group("message"))

    # 4. # deprecated: <version> comments
    for i, line in enumerate(lines):
        cm = _DEPRECATED_COMMENT.search(line)
        if cm:
            note = (cm.group("note") or "").strip()
            # Pull context from the next non-blank, non-comment line
            next_code = ""
            for j in range(i + 1, min(i + 5, len(lines))):
                stripped = lines[j].strip()
                if stripped and not stripped.startswith("#"):
                    next_code = stripped
                    break
            context_msg = note or next_code or f"Staged deprecation for removal in {cm.group('version')}"
            span_key = (i + 1, hash(context_msg[:60]))
            if span_key not in seen_spans:
                seen_spans.add(span_key)
                audience = _classify_audience(rel_path, context_msg)
                fp = _fingerprint(rel_path, i + 1, context_msg)
                entries.append(
                    DeprecationEntry(
                        source_file=rel_path,
                        line_number=i + 1,
                        mechanism="comment",
                        removal_version=cm.group("version"),
                        message=context_msg,
                        fingerprint=fp,
                        context_lines=_get_context(lines, i),
                        audience=audience,
                    )
                )

    # 5. _tags.Deprecated(version=...)
    for m in _DEPRECATED_TAG.finditer(text):
        # Grab the surrounding function/class for context
        line_no = text[: m.start()].count("\n") + 1
        nearby = " ".join(lines[max(0, line_no - 5) : line_no + 2])
        func_m = re.search(r"(?:def|class)\s+(\w+)", nearby)
        ctx_name = func_m.group(1) if func_m else "unknown"
        msg = f"Tag-based deprecation of {ctx_name}: removal in {m.group('version')}"
        _add_entry(m.start(), "tag", m.group("version"), msg)

    return entries


# ── Aggregation helpers ──────────────────────────────────────────────


def _build_aggregations(
    entries: list[dict[str, Any]],
) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    """Build version/mechanism/audience aggregation dicts.

    Args:
        entries: Deprecation dicts with removal_version, mechanism, audience.

    Returns:
        Tuple of sorted count maps: by_version, by_mechanism, by_audience.
    """
    by_version: dict[str, int] = {}
    by_mechanism: dict[str, int] = {}
    by_audience: dict[str, int] = {}
    for e in entries:
        v = e["removal_version"]
        by_version[v] = by_version.get(v, 0) + 1
        m = e["mechanism"]
        by_mechanism[m] = by_mechanism.get(m, 0) + 1
        a = e["audience"]
        by_audience[a] = by_audience.get(a, 0) + 1
    return (
        dict(sorted(by_version.items())),
        dict(sorted(by_mechanism.items())),
        dict(sorted(by_audience.items())),
    )


def _diff_with_previous(new_entries: list[dict[str, Any]], prev_path: Path) -> list[dict[str, Any]]:
    """Return entries whose fingerprints are new since the last scrape.

    Args:
        new_entries: Current scrape entries as dicts with fingerprint keys.
        prev_path: Path to prior JSON output to diff against.

    Returns:
        Subset of new_entries whose fingerprints were absent in prev_path.
    """
    if not prev_path.exists():
        return new_entries
    try:
        with prev_path.open(encoding="utf-8") as f:
            prev = json.load(f)
        prev_fps = {d["fingerprint"] for d in prev.get("deprecations", []) if d.get("fingerprint")}
    except (json.JSONDecodeError, KeyError):
        return new_entries
    return [e for e in new_entries if e.get("fingerprint") not in prev_fps]


# ── Main scrape ──────────────────────────────────────────────────────


def scrape(repo_dir: Path) -> ScrapeResult:
    """Scrape all Python files under lib/ansible/ for deprecation notices.

    Args:
        repo_dir: Root of the ansible/ansible checkout (must contain lib/ansible).

    Returns:
        ScrapeResult with commit, version, aggregations, and all deprecations.
    """
    ansible_lib = repo_dir / ANSIBLE_LIB
    if not ansible_lib.exists():
        print(f"ERROR: {ansible_lib} not found", file=sys.stderr)
        sys.exit(1)

    commit = get_commit(repo_dir)
    version = get_ansible_version(repo_dir)
    all_entries: list[DeprecationEntry] = []

    py_files = sorted(ansible_lib.rglob("*.py"))
    print(f"Scanning {len(py_files)} Python files in {ansible_lib}…", file=sys.stderr)

    for py_file in py_files:
        all_entries.extend(scan_file(py_file, ansible_lib))

    entry_dicts = [asdict(e) for e in all_entries]
    by_version, by_mechanism, by_audience = _build_aggregations(entry_dicts)

    print(f"Found {len(all_entries)} deprecation notices", file=sys.stderr)
    for v in sorted(by_version.keys()):
        print(f"  {v}: {by_version[v]}", file=sys.stderr)

    return ScrapeResult(
        scraped_at=datetime.now(tz=timezone.utc).isoformat(),
        commit=commit,
        branch="devel",
        ansible_core_version=version,
        total_deprecations=len(all_entries),
        by_version=by_version,
        by_mechanism=by_mechanism,
        by_audience=by_audience,
        deprecations=entry_dicts,
    )


def _version_gte(version: str, min_version: str) -> bool:
    """Compare version strings (e.g. '2.23' >= '2.21').

    Args:
        version: Dotted integer version string to test.
        min_version: Dotted integer minimum version for comparison.

    Returns:
        True if version parses as >= min_version; True on parse errors (permissive).
    """
    try:
        v = tuple(int(x) for x in version.split("."))
        mv = tuple(int(x) for x in min_version.split("."))
        return v >= mv
    except (ValueError, TypeError):
        return True


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Scrape ansible-core deprecation notices from the devel branch.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python scripts/scrape_ansible_deprecations.py
              python scripts/scrape_ansible_deprecations.py --skip-clone --cache-dir /tmp/ansible
              python scripts/scrape_ansible_deprecations.py --min-version 2.21 --audience content
              python scripts/scrape_ansible_deprecations.py --diff-only
        """),
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSON file (default: {DEFAULT_OUTPUT.relative_to(REPO_ROOT)})",
    )
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE, help="Directory to clone ansible-core into")
    parser.add_argument("--branch", default="devel", help="Branch to scrape (default: devel)")
    parser.add_argument(
        "--skip-clone", action="store_true", help="Skip git clone/fetch; use existing cache directory as-is"
    )
    parser.add_argument("--min-version", help="Only include deprecations >= this version (e.g. 2.21)")
    parser.add_argument(
        "--audience", choices=["content", "developer", "all"], default="all", help="Filter by audience (default: all)"
    )
    parser.add_argument("--diff-only", action="store_true", help="Only output deprecations new since the last scrape")
    parser.add_argument("--pretty", action="store_true", default=True, help="Pretty-print JSON output (default: True)")

    args = parser.parse_args()

    if not args.skip_clone:
        clone_or_update(args.cache_dir, args.branch)

    result = scrape(args.cache_dir)

    filtered = result.deprecations
    if args.min_version:
        filtered = [
            d
            for d in filtered
            if not d["removal_version"].startswith("date:") and _version_gte(d["removal_version"], args.min_version)
        ]
    if args.audience != "all":
        filtered = [d for d in filtered if d["audience"] == args.audience]

    if args.diff_only:
        new_only = _diff_with_previous(filtered, args.output)
        print(f"  {len(new_only)} new deprecations (of {len(filtered)} total)", file=sys.stderr)
        filtered = new_only

    result.deprecations = filtered
    result.total_deprecations = len(filtered)
    bv, bm, ba = _build_aggregations(filtered)
    result.by_version, result.by_mechanism, result.by_audience = bv, bm, ba

    args.output.parent.mkdir(parents=True, exist_ok=True)
    indent = 2 if args.pretty else None
    args.output.write_text(
        json.dumps(asdict(result), indent=indent, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote {len(filtered)} deprecations to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
