"""Load and evaluate violation suppressions from ``.apme/suppressions.yml`` (ADR-055)."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import yaml

from apme_engine.engine.models import ViolationDict
from apme_engine.fingerprint import canonicalize_rule_id, compute_fingerprint

SUPPRESSIONS_YML_PATH = Path(".apme") / "suppressions.yml"

_VALID_MODES = frozenset(("full", "rule_module", "rule_only"))


@dataclass(frozen=True, slots=True)
class Suppression:
    """A single suppression entry from the suppressions file.

    Attributes:
        fingerprint: SHA-256 hex digest identifying the suppressed content.
        rule_id: Rule that produced the violation.
        mode: Fingerprint granularity mode.
        reason: Human-provided justification.
        created: ISO 8601 date string.
    """

    fingerprint: str
    rule_id: str
    mode: str = "full"
    reason: str = ""
    created: str = ""


@dataclass(slots=True)
class SuppressionResult:
    """Result of applying suppressions to a violation list.

    Attributes:
        active: Violations that are not suppressed.
        suppressed: Violations that matched a suppression entry.
    """

    active: list[ViolationDict] = field(default_factory=list)
    suppressed: list[ViolationDict] = field(default_factory=list)


def load_suppressions(project_root: Path) -> list[Suppression]:
    """Parse ``<project_root>/.apme/suppressions.yml`` into Suppression objects.

    The file is optional. On missing path, returns an empty list. On parse
    errors, writes a warning to stderr and returns an empty list.

    Args:
        project_root: Resolved project root path.

    Returns:
        List of Suppression entries, possibly empty.
    """
    path = project_root / SUPPRESSIONS_YML_PATH
    if not path.is_file():
        return []

    try:
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
    except OSError as e:
        sys.stderr.write(f"Warning: could not read {path}: {e}\n")
        return []
    except yaml.YAMLError as e:
        sys.stderr.write(f"Warning: could not parse {path}: {e}\n")
        return []

    if data is None:
        return []

    if not isinstance(data, dict):
        sys.stderr.write(f"Warning: {path}: expected a mapping at top level\n")
        return []

    version = data.get("version")
    if version is not None and version != 1:
        sys.stderr.write(f"Warning: {path}: unsupported version {version}, ignoring suppressions\n")
        return []

    entries = data.get("suppressions")
    if entries is None:
        return []

    if not isinstance(entries, list):
        sys.stderr.write(f"Warning: {path}: 'suppressions' must be a list\n")
        return []

    suppressions: list[Suppression] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            sys.stderr.write(f"Warning: {path}: entry {i} is not a mapping, skipping\n")
            continue

        fp = entry.get("fingerprint")
        if not fp or not isinstance(fp, str):
            sys.stderr.write(f"Warning: {path}: entry {i} missing 'fingerprint', skipping\n")
            continue

        fp = fp.strip().lower()
        if len(fp) != 64 or not all(c in "0123456789abcdef" for c in fp):
            sys.stderr.write(f"Warning: {path}: entry {i} has invalid fingerprint format, skipping\n")
            continue

        raw_rule_id = entry.get("rule_id")
        rule_id = raw_rule_id if isinstance(raw_rule_id, str) else ""
        raw_mode = entry.get("mode")
        mode = raw_mode if isinstance(raw_mode, str) else "full"
        if mode not in _VALID_MODES:
            sys.stderr.write(
                f"Warning: {path}: entry {i} has invalid mode {mode!r}, defaulting to 'full'\n",
            )
            mode = "full"

        raw_reason = entry.get("reason")
        reason = raw_reason if isinstance(raw_reason, str) else ""
        raw_created = entry.get("created")
        if isinstance(raw_created, str):
            created = raw_created
        elif isinstance(raw_created, datetime | date):
            created = raw_created.isoformat()
        else:
            created = ""

        suppressions.append(
            Suppression(
                fingerprint=fp,
                rule_id=rule_id,
                mode=mode,
                reason=reason,
                created=created,
            ),
        )

    return suppressions


def apply_suppressions(
    violations: Sequence[ViolationDict],
    suppressions: list[Suppression],
    enforced_rules: set[str] | None = None,
) -> SuppressionResult:
    """Partition violations into active and suppressed based on fingerprint matching.

    Violations for enforced rules (ADR-041) bypass suppression entirely.

    Args:
        violations: Sequence of violation dicts (must include ``rule_id``,
            ``original_yaml``, and optionally ``module_fqcn`` or
            ``resolved_fqcn``/``original_module``).
        suppressions: Loaded suppression entries.
        enforced_rules: Set of rule IDs that cannot be suppressed.

    Returns:
        SuppressionResult with active and suppressed lists.
    """
    if not suppressions:
        return SuppressionResult(active=list(violations), suppressed=[])

    enforced = enforced_rules or set()

    fp_index_full: dict[str, Suppression] = {}
    fp_index_module: dict[str, Suppression] = {}
    fp_index_rule: dict[str, Suppression] = {}

    for s in suppressions:
        if s.mode == "full":
            fp_index_full[s.fingerprint] = s
        elif s.mode == "rule_module":
            fp_index_module[s.fingerprint] = s
        elif s.mode == "rule_only":
            fp_index_rule[s.fingerprint] = s

    result = SuppressionResult()

    for v in violations:
        rule_id = str(v.get("rule_id", ""))
        canonical_id = canonicalize_rule_id(rule_id)

        if canonical_id in enforced or rule_id in enforced:
            result.active.append(v)
            continue

        original_yaml = str(v.get("original_yaml") or "")
        module_fqcn = str(
            v.get("module_fqcn") or v.get("resolved_fqcn") or v.get("original_module") or v.get("fqcn") or "",
        )

        suppressed = False

        if fp_index_rule:
            fp_rule = compute_fingerprint(rule_id, original_yaml, mode="rule_only")
            if fp_rule in fp_index_rule:
                suppressed = True

        if not suppressed and fp_index_module and module_fqcn:
            fp_module = compute_fingerprint(
                rule_id,
                original_yaml,
                mode="rule_module",
                module_fqcn=module_fqcn,
            )
            if fp_module in fp_index_module:
                suppressed = True

        if not suppressed and fp_index_full:
            fp_full = compute_fingerprint(rule_id, original_yaml, mode="full")
            if fp_full in fp_index_full:
                suppressed = True

        if suppressed:
            result.suppressed.append(v)
        else:
            result.active.append(v)

    return result


def write_suppressions(project_root: Path, suppressions: list[Suppression]) -> None:
    """Write suppression entries to ``.apme/suppressions.yml``.

    Creates the ``.apme/`` directory if it does not exist.

    Args:
        project_root: Resolved project root path.
        suppressions: List of suppression entries to write.
    """
    path = project_root / SUPPRESSIONS_YML_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, str]] = []
    for s in suppressions:
        entry: dict[str, str] = {
            "fingerprint": s.fingerprint,
            "rule_id": s.rule_id,
        }
        if s.mode != "full":
            entry["mode"] = s.mode
        if s.reason:
            entry["reason"] = s.reason
        if s.created:
            entry["created"] = s.created
        entries.append(entry)

    data: dict[str, object] = {
        "version": 1,
        "suppressions": entries,
    }

    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
