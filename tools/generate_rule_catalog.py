#!/usr/bin/env python3
"""Generate docs/rules/RULE_CATALOG.md — a single-file reference of every rule.

Discovers rules from OPA (.rego), Native (GraphRule subclasses), Ansible
(explicit imports), and Gitleaks.  For each rule, reports:

  - validator, description, severity
  - whether a deterministic fixer (transform) exists
  - whether the implementation exists (code, not just a doc stub)
  - whether tests exist (Rego _test.rego or pytest files referencing the ID)

Run from repo root:  python tools/generate_rule_catalog.py
Or via prek hook:    triggered on rule source changes.

The output is written to docs/rules/RULE_CATALOG.md.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

NATIVE_DIR = REPO_ROOT / "src" / "apme_engine" / "graph" / "rules"
OPA_DIR = REPO_ROOT / "src" / "apme_engine" / "validators" / "opa" / "bundle"
ANSIBLE_DIR = REPO_ROOT / "src" / "apme_engine" / "validators" / "ansible" / "rules"
GITLEAKS_DIR = REPO_ROOT / "src" / "apme_engine" / "validators" / "gitleaks"
TESTS_DIR = REPO_ROOT / "tests"
INTEGRATION_TEST = TESTS_DIR / "rule_doc_integration_test.py"
TRANSFORMS_INIT = REPO_ROOT / "src" / "apme_engine" / "remediation" / "transforms" / "__init__.py"
OUTPUT = REPO_ROOT / "docs" / "rules" / "RULE_CATALOG.md"

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_KV = re.compile(r"^(\w+):\s*(.+)$", re.MULTILINE)
_NATIVE_RULE_ID = re.compile(r'rule_id:\s*str\s*=\s*"([^"]+)"')
_OPA_RULE_ID = re.compile(r'"rule_id":\s*"([^"]+)"')
_ANSIBLE_CONST = re.compile(r'RULE_ID\s*=\s*"([^"]+)"')
_ANSIBLE_INLINE = re.compile(r'"rule_id":\s*"([^"]+)"')
_REG_CALL = re.compile(r'reg\.register\(\s*"([^"]+)"')

_SKIP_NATIVE_STEMS = {"__init__", "base_rule", "sample_rule", "graph_rule_base", "_module_risk_mapping"}


@dataclass
class Rule:
    """A single rule entry for the catalog."""

    rule_id: str
    validator: str
    description: str
    severity: str = ""
    has_impl: bool = False
    has_test: bool = False
    has_fixer: bool = False
    has_doc: bool = False
    impl_file: str = ""
    test_files: list[str] = field(default_factory=list)
    status: str = ""
    status_reason: str = ""


def _parse_frontmatter(path: Path) -> dict[str, str]:
    """Parse YAML-ish frontmatter from a markdown file.

    Uses ``yaml.safe_load`` for correct handling of multiline scalars
    (folded ``>``, literal ``|``, etc.).  Falls back to regex extraction
    when PyYAML is unavailable.

    Args:
        path: Path to the markdown file.

    Returns:
        Dict of frontmatter key-value pairs.
    """
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER.match(text)
    if not m:
        return {}
    raw = m.group(1)
    try:
        import yaml

        parsed = yaml.safe_load(raw)
        if isinstance(parsed, dict):
            return {str(k): str(v).strip() for k, v in parsed.items() if v is not None}
    except ImportError:
        print(
            f"WARNING: PyYAML not available; using regex fallback for {path}",
            file=sys.stderr,
        )
    except yaml.YAMLError as exc:
        print(f"WARNING: YAML parse error in {path}: {exc}; falling back to regex", file=sys.stderr)
    pairs = _KV.findall(raw)
    return {k: v.strip("\"'") for k, v in pairs}


def _get_severity(rule_id: str) -> str:
    """Look up severity from apme_engine.graph.severity.

    Args:
        rule_id: Rule identifier.

    Returns:
        Severity label string.
    """
    try:
        from apme_engine.graph.severity import get_severity, severity_to_label

        return severity_to_label(get_severity(rule_id))
    except Exception:
        return ""


def _get_fixable_ids() -> set[str]:
    """Return set of rule_ids that have deterministic fixers.

    Returns:
        Set of rule_id strings with registered transforms.
    """
    try:
        from apme_engine.remediation.transforms import build_default_registry

        reg = build_default_registry()
        return set(reg.rule_ids)
    except Exception:
        pass

    if TRANSFORMS_INIT.exists():
        src = TRANSFORMS_INIT.read_text(encoding="utf-8")
        ids = set(_REG_CALL.findall(src))
        if ids:
            print(f"NOTE: loaded {len(ids)} fixer IDs from source (runtime import unavailable)", file=sys.stderr)
            return ids

    print("WARNING: could not determine fixable rule IDs", file=sys.stderr)
    return set()


def _is_incidental_reference(rule_id: str, text: str, filename: str) -> bool:
    """Check if a rule_id mention in a test file is just fixture/example data.

    A reference is considered incidental if the test file doesn't import or
    instantiate anything related to the rule.  Files named after rule
    categories (e.g. ``test_ansible_rules.py``) or containing a class/def
    whose name includes the rule ID are genuine.

    Args:
        rule_id: Rule identifier found in the file.
        text: Full file content.
        filename: Base filename.

    Returns:
        True if the reference is likely incidental fixture data.
    """
    rid_lower = rule_id.lower().replace("-", "_")
    if rid_lower in filename.lower():
        return False
    rule_context = re.compile(
        rf"(?:class\s+\w*{re.escape(rule_id)}\w*|"
        rf"def\s+test_\w*{re.escape(rid_lower)}\w*|"
        rf"import\s+.*{re.escape(rule_id)}|"
        rf"Rule.*{re.escape(rule_id)})",
        re.IGNORECASE,
    )
    if rule_context.search(text):
        return False
    rule_id_assignment = re.compile(rf'rule_id\s*[=:]\s*["\']{re.escape(rule_id)}["\']')
    return not rule_id_assignment.search(text)


_RULE_RANGE_IN_MODULE = re.compile(r"([A-Z])(\d+)_\1(\d+)_")


def _rule_ids_from_module_name(module_fragment: str) -> set[str]:
    """Expand grouped rule modules (e.g. M001_M004_introspect) to rule IDs.

    Args:
        module_fragment: Import path segment or module stem.

    Returns:
        Rule IDs covered by a range module name, or empty set.
    """
    m = _RULE_RANGE_IN_MODULE.search(module_fragment)
    if not m:
        return set()
    letter, start_s, end_s = m.group(1), m.group(2), m.group(3)
    start, end = int(start_s), int(end_s)
    if end < start or end - start > 50:
        return set()
    width = max(len(start_s), len(end_s))
    return {f"{letter}{i:0{width}d}" for i in range(start, end + 1)}


_TEST_CACHE: dict[str, list[str]] | None = None


def _get_test_cache() -> dict[str, list[str]]:
    """Build a cache of rule_id -> list of test files.

    Rules in _GRAPH_RULE_KNOWN_FAILURES whose only test reference is
    rule_doc_integration_test.py are excluded — a skip is not a test.

    Returns:
        Dict mapping rule_id strings to lists of test filenames.
    """
    global _TEST_CACHE  # noqa: PLW0603
    if _TEST_CACHE is not None:
        return _TEST_CACHE

    cache: dict[str, list[str]] = {}
    if not TESTS_DIR.is_dir():
        _TEST_CACHE = cache
        return cache

    all_rule_id_pat = re.compile(r'["\']((?:A|L|M|R|P)\d+|SEC:[a-zA-Z0-9_*-]+)["\']')
    import_rule_id_pat = re.compile(
        r"(?:from\s+\S+\.(?:rules|validators)\.\S*(?:_|\b)([A-Z]\d+)|"
        r"class\s+\w*?([A-Z]\d+)\w*(?:Rule|Test)|"
        r"def\s+test_\w*?([a-z]\d+))",
    )
    for py in sorted(TESTS_DIR.rglob("*.py")):
        if py.name.startswith("_"):
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = py.relative_to(TESTS_DIR).as_posix()
        seen_ids: set[str] = set()
        for m in all_rule_id_pat.finditer(text):
            rid = m.group(1)
            if _is_incidental_reference(rid, text, py.name):
                continue
            seen_ids.add(rid)
        for m in import_rule_id_pat.finditer(text):
            rid = (m.group(1) or m.group(2) or (m.group(3) or "").upper()).strip()
            if rid:
                seen_ids.add(rid)
        for m in re.finditer(r"from\s+[\w.]+\s+import\s+(\w+)", text):
            seen_ids.update(_rule_ids_from_module_name(m.group(1)))
        for rid in seen_ids:
            cache.setdefault(rid, [])
            if rel not in cache[rid]:
                cache[rid].append(rel)

    known_failures = _get_known_failure_ids()
    for rid in known_failures:
        files = cache.get(rid, [])
        real = [f for f in files if f != "rule_doc_integration_test.py"]
        if real:
            cache[rid] = real
        else:
            cache.pop(rid, None)

    _TEST_CACHE = cache
    return cache


def _get_known_failure_ids() -> set[str]:
    """Parse rule IDs from _GRAPH_RULE_KNOWN_FAILURES in the integration test.

    Returns:
        Set of rule_id strings that are known integration-test skips.
    """
    if not INTEGRATION_TEST.exists():
        return set()
    text = INTEGRATION_TEST.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r'^\s*"([A-Z]\d+)":', text, re.MULTILINE))


def _find_doc(rule_id: str, doc_dir: Path) -> Path | None:
    """Find the .md doc file for a rule ID.

    Args:
        rule_id: Rule ID to find.
        doc_dir: Directory to search.

    Returns:
        Path to .md file or None.
    """
    exact = doc_dir / f"{rule_id}.md"
    if exact.exists():
        return exact
    for md in doc_dir.glob("*.md"):
        if md.name == "README.md":
            continue
        if md.stem.startswith(rule_id):
            return md
    return None


_VALIDATOR_NAMES: dict[str, str] = {
    "opa": "OPA",
    "native": "Native",
    "ansible": "Ansible",
    "gitleaks": "Gitleaks",
}


def _normalize_validator(raw: str) -> str:
    """Normalize a validator name preserving canonical casing.

    Args:
        raw: Raw validator string from frontmatter.

    Returns:
        Canonical validator name, defaulting to ``Native``.
    """
    return _VALIDATOR_NAMES.get(raw.lower().strip(), raw.capitalize()) if raw else "Native"


def _collect_opa_rules() -> list[Rule]:
    """Collect rules from OPA bundle.

    Returns:
        List of Rule objects for OPA rules.
    """
    rules: list[Rule] = []
    for rego in sorted(OPA_DIR.glob("*.rego")):
        if rego.name.endswith("_test.rego") or rego.name.startswith("_"):
            continue
        text = rego.read_text(encoding="utf-8", errors="replace")
        m = _OPA_RULE_ID.search(text)
        if not m:
            continue
        rid = m.group(1)
        doc = _find_doc(rid, OPA_DIR)
        fm = _parse_frontmatter(doc) if doc else {}
        test_rego = OPA_DIR / f"{rego.stem}_test.rego"
        test_cache = _get_test_cache()
        pytest_files = test_cache.get(rid, [])

        rules.append(
            Rule(
                rule_id=rid,
                validator="OPA",
                description=fm.get("description", ""),
                has_impl=True,
                impl_file=rego.name,
                has_doc=doc is not None,
                has_test=test_rego.exists() or bool(pytest_files),
                test_files=([test_rego.name] if test_rego.exists() else []) + pytest_files,
            )
        )
    return rules


def _collect_native_rules() -> list[Rule]:
    """Collect rules from Native validator Python files.

    Returns:
        List of Rule objects for Native rules.
    """
    rules: list[Rule] = []
    doc_only_ids: set[str] = set()

    for py in sorted(NATIVE_DIR.glob("*.py")):
        if py.name.endswith("_test.py") or py.stem in _SKIP_NATIVE_STEMS:
            continue
        text = py.read_text(encoding="utf-8", errors="replace")
        m = _NATIVE_RULE_ID.search(text)
        if not m:
            continue
        rid = m.group(1)
        doc = _find_doc(rid, NATIVE_DIR)
        fm = _parse_frontmatter(doc) if doc else {}
        test_cache = _get_test_cache()
        pytest_files = test_cache.get(rid, [])

        rules.append(
            Rule(
                rule_id=rid,
                validator="Native",
                description=fm.get("description", ""),
                has_impl=True,
                impl_file=py.name,
                has_doc=doc is not None,
                has_test=bool(pytest_files),
                test_files=pytest_files,
            )
        )
        doc_only_ids.add(rid)

    for md in sorted(NATIVE_DIR.glob("*.md")):
        if md.name == "README.md" or md.name == "sample_rule.md":
            continue
        fm = _parse_frontmatter(md)
        rid = fm.get("rule_id", "")
        if not rid or rid in doc_only_ids:
            continue
        test_cache = _get_test_cache()
        pytest_files = test_cache.get(rid, [])

        fm_validator = _normalize_validator(fm.get("validator", ""))

        rules.append(
            Rule(
                rule_id=rid,
                validator=fm_validator,
                description=fm.get("description", ""),
                has_impl=False,
                impl_file="",
                has_doc=True,
                has_test=bool(pytest_files),
                test_files=pytest_files,
                status=fm.get("status", ""),
                status_reason=fm.get("status_reason", ""),
            )
        )

    return rules


def _collect_ansible_rules() -> list[Rule]:
    """Collect rules from Ansible validator.

    Returns:
        List of Rule objects for Ansible rules.
    """
    rules: list[Rule] = []
    if not ANSIBLE_DIR.is_dir():
        return rules

    for py in sorted(ANSIBLE_DIR.glob("*.py")):
        if py.name.startswith("_") or py.name.endswith("_test.py"):
            continue
        text = py.read_text(encoding="utf-8", errors="replace")
        found_ids: set[str] = set()
        for m in _ANSIBLE_CONST.finditer(text):
            found_ids.add(m.group(1))
        for m in _ANSIBLE_INLINE.finditer(text):
            found_ids.add(m.group(1))

        for rid in sorted(found_ids):
            doc = _find_doc(rid, ANSIBLE_DIR)
            fm = _parse_frontmatter(doc) if doc else {}
            test_cache = _get_test_cache()
            pytest_files = test_cache.get(rid, [])

            rules.append(
                Rule(
                    rule_id=rid,
                    validator="Ansible",
                    description=fm.get("description", ""),
                    has_impl=True,
                    impl_file=py.name,
                    has_doc=doc is not None,
                    has_test=bool(pytest_files),
                    test_files=pytest_files,
                )
            )

    return rules


def _collect_gitleaks_rules() -> list[Rule]:
    """Return a single Gitleaks rule entry.

    Returns:
        List with one Rule for Gitleaks SEC:*.
    """
    return [
        Rule(
            rule_id="SEC:*",
            validator="Gitleaks",
            description="Secret/credential detection (delegated to Gitleaks binary).",
            has_impl=True,
            impl_file="scanner.py",
            has_doc=False,
            has_test=any(k.startswith("SEC:") for k in _get_test_cache()),
        )
    ]


def _sort_key(rule: Rule) -> tuple[str, int]:
    """Return (prefix, number) for sorting rules by rule_id.

    Args:
        rule: Rule object.

    Returns:
        Tuple of (letter prefix, numeric portion) for sort ordering.
    """
    rid = rule.rule_id
    prefix = rid.rstrip("0123456789:*")
    num_str = rid[len(prefix) :].split(":")[0].split("*")[0]
    num = int(num_str) if num_str.isdigit() else 9999
    return (prefix, num)


def _escape_md_cell(text: str) -> str:
    r"""Escape unescaped pipe characters for use inside markdown table cells.

    Idempotent: already-escaped pipes (``\|``) are left unchanged.

    Args:
        text: Raw cell text.

    Returns:
        Text with unescaped ``|`` escaped as ``\|``.
    """
    return re.sub(r"(?<!\\)\|", r"\\|", text)


def _status_icon(ok: bool) -> str:
    """Return a checkmark or X for boolean status.

    Args:
        ok: Status value.

    Returns:
        Status indicator string.
    """
    return "Yes" if ok else "—"


def generate() -> str:
    """Collect all rules and return RULE_CATALOG.md content.

    Returns:
        Full markdown content for docs/rules/RULE_CATALOG.md.
    """
    all_rules: list[Rule] = []
    all_rules.extend(_collect_opa_rules())
    all_rules.extend(_collect_native_rules())
    all_rules.extend(_collect_ansible_rules())
    all_rules.extend(_collect_gitleaks_rules())
    all_rules.sort(key=_sort_key)

    fixable = _get_fixable_ids()
    for r in all_rules:
        r.has_fixer = r.rule_id in fixable
        r.severity = _get_severity(r.rule_id)

    total = len(all_rules)
    impl_count = sum(1 for r in all_rules if r.has_impl)
    test_count = sum(1 for r in all_rules if r.has_test)
    doc_count = sum(1 for r in all_rules if r.has_doc)
    fixer_count = sum(1 for r in all_rules if r.has_fixer)
    validators = len({r.validator for r in all_rules})

    lines = [
        "# Rule Catalog",
        "",
        "<!-- AUTO-GENERATED by tools/generate_rule_catalog.py — do not edit by hand -->",
        "",
        f"**{total} rules** across {validators} validators",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Implemented | {impl_count}/{total} |",
        f"| Tested | {test_count}/{total} |",
        f"| Documented | {doc_count}/{total} |",
        f"| Deterministic fixer | {fixer_count}/{total} |",
        "",
        "## All Rules",
        "",
        "| Rule ID | Validator | Severity | Description | Impl | Tested | Doc | Fixer |",
        "|---------|-----------|----------|-------------|------|--------|-----|-------|",
    ]

    for r in all_rules:
        lines.append(
            f"| {r.rule_id} | {r.validator} | {r.severity} | {_escape_md_cell(r.description)} "
            f"| {_status_icon(r.has_impl)} | {_status_icon(r.has_test)} "
            f"| {_status_icon(r.has_doc)} | {_status_icon(r.has_fixer)} |"
        )

    lines.append("")
    lines.append("## By Validator")
    lines.append("")

    validators_map: dict[str, list[Rule]] = {}
    for r in all_rules:
        validators_map.setdefault(r.validator, []).append(r)

    for vname in ("OPA", "Native", "Ansible", "Gitleaks"):
        vrules = validators_map.get(vname, [])
        if not vrules:
            continue
        v_impl = sum(1 for r in vrules if r.has_impl)
        v_test = sum(1 for r in vrules if r.has_test)
        v_fix = sum(1 for r in vrules if r.has_fixer)
        lines.append(f"### {vname} ({len(vrules)} rules, {v_impl} impl, {v_test} tested, {v_fix} fixers)")
        lines.append("")
        lines.append("| Rule ID | Severity | Description | Impl | Tested | Doc | Fixer |")
        lines.append("|---------|----------|-------------|------|--------|-----|-------|")
        for r in vrules:
            lines.append(
                f"| {r.rule_id} | {r.severity} | {_escape_md_cell(r.description)} "
                f"| {_status_icon(r.has_impl)} | {_status_icon(r.has_test)} "
                f"| {_status_icon(r.has_doc)} | {_status_icon(r.has_fixer)} |"
            )
        lines.append("")

    lines.append("## Coverage Gaps")
    lines.append("")

    no_impl = [r for r in all_rules if not r.has_impl]
    no_test = [r for r in all_rules if not r.has_test and r.has_impl]
    no_doc = [r for r in all_rules if not r.has_doc and r.has_impl]

    resolved_statuses = {"stub", "delegated"}
    no_impl_resolved = [r for r in no_impl if r.status in resolved_statuses]
    no_impl_planned = [r for r in no_impl if r.status == "planned"]
    no_impl_unknown = [r for r in no_impl if r.status not in resolved_statuses and r.status != "planned"]

    if no_impl_unknown:
        lines.append(f"### Doc-only rules (no implementation) — {len(no_impl_unknown)}")
        lines.append("")
        for r in no_impl_unknown:
            lines.append(f"- **{r.rule_id}** ({r.validator}): {r.description}")
        lines.append("")

    if no_impl_planned:
        lines.append(f"### Planned rules (implementation pending) — {len(no_impl_planned)}")
        lines.append("")
        for r in no_impl_planned:
            reason = f" — {r.status_reason}" if r.status_reason else ""
            lines.append(f"- **{r.rule_id}** ({r.validator}): {r.description}{reason}")
        lines.append("")

    if no_impl_resolved:
        lines.append(f"### Resolved without implementation — {len(no_impl_resolved)}")
        lines.append("")
        for r in no_impl_resolved:
            label = "Delegated" if r.status == "delegated" else "Stub"
            reason = f" — {r.status_reason}" if r.status_reason else ""
            lines.append(f"- **{r.rule_id}** ({r.validator}): [{label}] {r.description}{reason}")
        lines.append("")

    if no_test:
        lines.append(f"### Implemented but untested — {len(no_test)}")
        lines.append("")
        for r in no_test:
            lines.append(f"- **{r.rule_id}** ({r.validator}): {r.description}")
        lines.append("")

    if no_doc:
        lines.append(f"### Implemented but undocumented — {len(no_doc)}")
        lines.append("")
        for r in no_doc:
            lines.append(f"- **{r.rule_id}** ({r.validator}): {r.description}")
        lines.append("")

    if not no_impl and not no_test and not no_doc:
        lines.append("All rules are implemented, tested, and documented.")
        lines.append("")

    lines.append("## Fixer Summary")
    lines.append("")
    lines.append("Deterministic fixers (Tier 1) are auto-applied by `apme remediate`.")
    lines.append("Rules without fixers fall to Tier 2 (AI-proposable) or Tier 3 (manual review).")
    lines.append("")
    lines.append("| Rule ID | Severity | Description |")
    lines.append("|---------|----------|-------------|")

    for r in all_rules:
        if r.has_fixer:
            lines.append(f"| {r.rule_id} | {r.severity} | {_escape_md_cell(r.description)} |")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    """Write RULE_CATALOG.md to docs/rules/."""
    content = generate()
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Wrote {OUTPUT} ({content.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
