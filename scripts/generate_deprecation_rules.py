#!/usr/bin/env python3
"""Generate APME M-rule scaffolds from curated deprecation rule definitions.

Reads ``src/apme_engine/data/deprecation_rules.json`` (or .yaml with PyYAML)
and generates:

  - OPA Rego rules + tests (for ``validator: opa`` entries)
  - Native Python rule stubs (for ``validator: native`` entries)
  - Markdown documentation for both
  - Updates to ANSIBLE_CORE_MIGRATION.md summary table

Before generating, the script inventories all existing rules in the OPA bundle
and native rules directories to avoid creating duplicates.

Usage:
    python scripts/generate_deprecation_rules.py [--dry-run] [--rules M014,M015]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from pathlib import Path
from typing import Any

RuleDict = dict[str, Any]

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

REPO_ROOT = Path(__file__).resolve().parent.parent
RULES_JSON = REPO_ROOT / "src" / "apme_engine" / "data" / "deprecation_rules.json"
RULES_YAML = REPO_ROOT / "src" / "apme_engine" / "data" / "deprecation_rules.yaml"
OPA_BUNDLE = REPO_ROOT / "src" / "apme_engine" / "validators" / "opa" / "bundle"
NATIVE_RULES = REPO_ROOT / "src" / "apme_engine" / "validators" / "native" / "rules"
ANSIBLE_RULES = REPO_ROOT / "src" / "apme_engine" / "validators" / "ansible" / "rules"
LINT_MAPPING = REPO_ROOT / ".sdlc" / "context" / "lint-rule-mapping.md"

# ── Existing rule inventory ──────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_RULE_ID_RE = re.compile(r"rule_id:\s*(\S+)")
_PY_RULE_ID_RE = re.compile(r'rule_id\s*[=:]\s*["\'](\w+)["\']')
_PY_DESC_RE = re.compile(r'description\s*[=:]\s*["\'](.+?)["\']')
_REGO_RULE_ID_RE = re.compile(r'"rule_id":\s*"(\w+)"')
_REGO_COMMENT_RE = re.compile(r"^#\s*\w+:\s*(.+)", re.MULTILINE)
_FM_DESC_RE = re.compile(r"description:\s*(.+)")


class _RuleInfo:
    """Metadata about an existing rule used for overlap detection."""

    __slots__ = ("rule_id", "path", "description", "source_text")

    def __init__(self, rule_id: str, path: str, description: str = "", source_text: str = "") -> None:
        """Initialize rule metadata.

        Args:
            rule_id: Rule identifier (e.g. L076).
            path: File path relative to repo root.
            description: Rule description text (stored lowercased).
            source_text: Full source code of the rule file (stored lowercased).
        """
        self.rule_id = rule_id
        self.path = path
        self.description = description.lower()
        self.source_text = source_text.lower()


def inventory_existing_rules() -> tuple[dict[str, str], list[_RuleInfo]]:
    """Scan OPA, native, and ansible rule dirs for existing rule_ids.

    Returns:
        (id_map, rule_infos) where id_map is rule_id -> source file path
        and rule_infos is a list of _RuleInfo with descriptions and source
        text for overlap detection.
    """
    existing: dict[str, str] = {}
    infos: list[_RuleInfo] = []

    def _add(rid: str, path: str, desc: str = "", source: str = "") -> None:
        existing[rid] = path
        for info in infos:
            if info.rule_id == rid:
                if desc:
                    info.description = desc.lower()
                if source:
                    info.source_text = source.lower()
                return
        infos.append(_RuleInfo(rid, path, desc, source))

    # OPA .rego files
    for rego in OPA_BUNDLE.glob("*.rego"):
        if rego.name.endswith("_test.rego"):
            continue
        text = rego.read_text(encoding="utf-8", errors="replace")
        rel = str(rego.relative_to(REPO_ROOT))
        desc = ""
        cm = _REGO_COMMENT_RE.search(text)
        if cm:
            desc = cm.group(1).strip()
        for m in _REGO_RULE_ID_RE.finditer(text):
            _add(m.group(1), rel, desc, text)

    # OPA .md frontmatter
    for md in OPA_BUNDLE.glob("*.md"):
        text = md.read_text(encoding="utf-8", errors="replace")
        fm = _FRONTMATTER_RE.match(text)
        if fm:
            rm = _RULE_ID_RE.search(fm.group(1))
            dm = _FM_DESC_RE.search(fm.group(1))
            if rm:
                _add(rm.group(1), str(md.relative_to(REPO_ROOT)), dm.group(1) if dm else "", text)

    # Native .py files
    for py in NATIVE_RULES.glob("*.py"):
        text = py.read_text(encoding="utf-8", errors="replace")
        rel = str(py.relative_to(REPO_ROOT))
        desc = ""
        dm = _PY_DESC_RE.search(text)
        if dm:
            desc = dm.group(1).strip()
        for m in _PY_RULE_ID_RE.finditer(text):
            _add(m.group(1), rel, desc, text)

    # Native .md frontmatter
    for md in NATIVE_RULES.glob("*.md"):
        text = md.read_text(encoding="utf-8", errors="replace")
        fm = _FRONTMATTER_RE.match(text)
        if fm:
            rm = _RULE_ID_RE.search(fm.group(1))
            dm = _FM_DESC_RE.search(fm.group(1))
            if rm:
                _add(rm.group(1), str(md.relative_to(REPO_ROOT)), dm.group(1) if dm else "")

    # Ansible validator rules — .py files
    if ANSIBLE_RULES.exists():
        for py in ANSIBLE_RULES.glob("*.py"):
            text = py.read_text(encoding="utf-8", errors="replace")
            rel = str(py.relative_to(REPO_ROOT))
            for m in _PY_RULE_ID_RE.finditer(text):
                _add(m.group(1), rel, "", text)
            for m in re.finditer(r'"rule_id":\s*"(\w+)"', text):
                _add(m.group(1), rel, "", text)

        for md in ANSIBLE_RULES.glob("*.md"):
            text = md.read_text(encoding="utf-8", errors="replace")
            fm = _FRONTMATTER_RE.match(text)
            if fm:
                rm = _RULE_ID_RE.search(fm.group(1))
                dm = _FM_DESC_RE.search(fm.group(1))
                if rm:
                    _add(rm.group(1), str(md.relative_to(REPO_ROOT)), dm.group(1) if dm else "")

    return existing, infos


# Known semantic overlaps between new M-rules and existing rules, with
# the reason string explaining the relationship.  Maintained manually
# after reviewing the full rule inventory.
_KNOWN_OVERLAPS: dict[str, list[tuple[str, str]]] = {
    "M014": [
        (
            "L076",
            "L076 AnsibleFactsBracketRule checks the same injected ansible_* fact variables and suggests ansible_facts['name']",
        ),
    ],
    "M023": [
        (
            "L061",
            "L061 truthy_boolean flags yes/no string values on ALL module options, which subsumes follow_redirects: 'yes'",
        ),
    ],
    "M026": [
        ("L050", "L050 VarNamingRule enforces ^[a-z][a-z0-9_]*$ which catches most non-identifier variable names"),
    ],
    "M027": [
        ("L046", "L046 NoFreeFormRule detects free-form key=value args on non-command modules"),
        ("L062", "L062 yaml_module_args detects _raw_params with key=value on non-shell modules"),
    ],
}

# Fingerprint-based overlap detection: maps a new rule's "detection
# fingerprint" (option key + scope) to existing rules that check the
# same structural pattern.  Each entry is:
#   (option_keys_to_check, node_type, existing_rule_id, explanation)
_STRUCTURAL_FINGERPRINTS: list[tuple[frozenset[str], str | None, str, str]] = [
    (
        frozenset({"ansible_facts", "ansible_hostname", "ansible_distribution", "ansible_os_family"}),
        "taskcall",
        "L076",
        "L076 scans task text for the same injected ansible_* variable names",
    ),
    (
        frozenset({"yes", "no", "truthy", "follow_redirects"}),
        "taskcall",
        "L061",
        "L061 checks all module options for YAML truthy strings (yes/no/True/False/on/off)",
    ),
    (
        frozenset({"isidentifier", "variable", "naming"}),
        "taskcall",
        "L050",
        "L050 enforces lowercase_snake naming on all variable references",
    ),
    (
        frozenset({"_raw_params", "key=value", "free_form"}),
        "taskcall",
        "L046",
        "L046 detects free-form key=value arguments on non-command modules",
    ),
    (
        frozenset({"with_items", "with_dict", "with_loop"}),
        "taskcall",
        "M009",
        "M009 already detects all deprecated with_* loop keywords",
    ),
    (
        frozenset({"include", "bare_include"}),
        "taskcall",
        "M008",
        "M008 already detects bare include usage",
    ),
    (
        frozenset({"deprecated_module", "removed_module"}),
        "taskcall",
        "L004",
        "L004 checks the deprecated modules list from data.apme.ansible.deprecated_modules",
    ),
]


def check_semantic_overlap(
    rule: RuleDict,
    existing: dict[str, str],
    infos: list[_RuleInfo],
) -> list[tuple[str, str]]:
    """Check if a proposed rule semantically overlaps with existing ones.

    Uses a known-overlap table, structural fingerprinting on detection text,
    and description similarity (substring and shared-token checks).

    Args:
        rule: Proposed deprecation rule dict (e.g. rule_id, description, detection).
        existing: Map of existing rule_id to source file path.
        infos: Existing rule metadata from ``inventory_existing_rules``.

    Returns:
        (existing_rule_id, reason) pairs for each overlap found.
    """
    rid = rule["rule_id"]
    overlaps: list[tuple[str, str]] = []
    seen: set[str] = set()

    # 1. Curated known-overlap table
    if rid in _KNOWN_OVERLAPS:
        for oid, reason in _KNOWN_OVERLAPS[rid]:
            if oid in existing and oid != rid and oid not in seen:
                overlaps.append((oid, reason))
                seen.add(oid)

    # 2. Structural fingerprinting: check if the new rule's detection
    #    patterns/approach match known structural patterns
    detection = rule.get("detection", {})
    approach = (detection.get("approach", "") + " " + rule.get("description", "")).lower()
    det_patterns = [str(p).lower() for p in detection.get("patterns", [])]
    det_text = approach + " " + " ".join(det_patterns)

    for fingerprint_keys, _node_type, target_rid, explanation in _STRUCTURAL_FINGERPRINTS:
        if target_rid == rid or target_rid in seen:
            continue
        if target_rid not in existing:
            continue
        matched = sum(1 for k in fingerprint_keys if k in det_text)
        if matched >= 2:
            overlaps.append((target_rid, explanation))
            seen.add(target_rid)

    # 3. Description similarity: find existing rules whose description
    #    is a substantial substring of (or shares substantial overlap with)
    #    the new rule's description.  Only match on description text, not
    #    full source, to avoid false positives from common code patterns.
    new_desc = rule.get("description", "").lower()
    new_title = rule.get("title", "").lower()
    for info in infos:
        if info.rule_id == rid or info.rule_id in seen:
            continue
        if info.rule_id not in existing:
            continue
        if not info.description:
            continue
        # Check if the existing rule's description is substantially
        # contained in the new rule's description or vice versa
        if len(info.description) > 15 and (info.description in new_desc or new_desc in info.description):
            overlaps.append(
                (
                    info.rule_id,
                    f"Description closely matches {info.rule_id}: '{info.description[:80]}'",
                )
            )
            seen.add(info.rule_id)
            continue
        # Check if both descriptions share the same distinctive phrase
        # (4+ word sequences, excluding common stop words and deprecation vocabulary)
        _stop = {
            "the",
            "a",
            "an",
            "is",
            "in",
            "of",
            "to",
            "for",
            "and",
            "or",
            "not",
            "use",
            "with",
            "are",
            "it",
            "be",
            "on",
            "at",
            "by",
            "from",
            "deprecated",
            "removed",
            "error",
            "warning",
            "will",
            "must",
            "instead",
            "remove",
            "add",
            "task",
            "play",
        }
        # Also exclude version references like (2.23), 2.24, etc.
        all_new = set(new_desc.split()) | set(new_title.split())
        new_words = {w for w in all_new if w not in _stop and not re.match(r"^\(?\d+\.\d+\)?;?$", w)}
        ex_words = {w for w in info.description.split() if w not in _stop and not re.match(r"^\(?\d+\.\d+\)?;?$", w)}
        common = new_words & ex_words
        if len(common) >= 4 and len(common) / max(len(new_words), 1) > 0.5:
            overlaps.append(
                (
                    info.rule_id,
                    f"Significant description overlap with {info.rule_id} (shared: {', '.join(sorted(common)[:5])})",
                )
            )
            seen.add(info.rule_id)

    return overlaps


# ── Rule loading ─────────────────────────────────────────────────────


def load_rules(path: Path | None = None, filter_ids: set[str] | None = None) -> list[RuleDict]:
    """Load rule definitions from JSON (preferred) or YAML (requires PyYAML).

    Args:
        path: Optional path to rules file; defaults to repo deprecation_rules.json/yaml.
        filter_ids: If set, only rules whose rule_id is in this set.

    Returns:
        List of rule definition dicts loaded from the file.
    """
    if path and path.exists():
        source = path
    elif RULES_JSON.exists():
        source = RULES_JSON
    elif RULES_YAML.exists() and HAS_YAML:
        source = RULES_YAML
    else:
        print(
            f"ERROR: Neither {RULES_JSON} nor {RULES_YAML} found (or PyYAML not installed for .yaml)",
            file=sys.stderr,
        )
        sys.exit(1)

    with source.open(encoding="utf-8") as f:
        if source.suffix == ".json":
            all_rules = json.load(f)
        elif HAS_YAML:
            all_rules = yaml.safe_load(f)
        else:
            print(f"Cannot read {source}: PyYAML not installed", file=sys.stderr)
            sys.exit(1)

    if filter_ids:
        all_rules = [r for r in all_rules if r["rule_id"] in filter_ids]
    return list(all_rules)


# ── OPA Rego generation (fully implemented detection logic) ──────────

_OPA_GENERATORS: dict[str, object] = {}


def _rego_slug(rule: RuleDict) -> str:
    """Derive a Rego function name from the rule title.

    Args:
        rule: Rule dict containing ``title``.

    Returns:
        Alphanumeric/underscore slug suitable for a Rego predicate name.
    """
    slug = rule["title"].lower()
    slug = slug.replace(" ", "_").replace("/", "_").replace("-", "_")
    return "".join(c for c in slug if c.isalnum() or c == "_")


def generate_opa_rule(rule: RuleDict) -> str:
    """Generate a Rego rule file with real detection logic.

    Args:
        rule: Deprecation rule dict (rule_id, title, description, detection, etc.).

    Returns:
        Full ``.rego`` file contents as a string.
    """
    rid = rule["rule_id"]
    generators = {
        "M016": _rego_m016_empty_when,
        "M017": _rego_m017_action_mapping,
        "M018": _rego_m018_paramiko,
        "M021": _rego_m021_empty_args,
        "M023": _rego_m023_follow_redirects,
        "M024": _rego_m024_include_vars_ignore_files,
        "M025": _rego_m025_third_party_strategy,
        "M028": _rego_m028_first_found_split,
    }
    if rid in generators:
        return generators[rid](rule)
    return _rego_generic(rule)


def _rego_m016_empty_when(rule: RuleDict) -> str:
    return textwrap.dedent("""\
        # M016: Empty when: conditional is deprecated (2.23)

        package apme.rules

        import future.keywords.if
        import future.keywords.in

        violations contains v if {
        \tsome tree in input.hierarchy
        \tsome node in tree.nodes
        \tv := empty_when_conditional(tree, node)
        }

        empty_when_conditional(tree, node) := v if {
        \tnode.type == "taskcall"
        \topts := object.get(node, "options", {})
        \twhen_val := opts["when"]
        \twhen_val == ""
        \tcount(node.line) > 0
        \tv := {
        \t\t"rule_id": "M016",
        \t\t"level": "warning",
        \t\t"message": "Empty when: conditional is deprecated and will be an error in 2.23; remove the when: key or add an explicit condition",
        \t\t"file": node.file,
        \t\t"line": node.line[0],
        \t\t"path": node.key,
        \t\t"scope": "task",
        \t}
        }

        empty_when_conditional(tree, node) := v if {
        \tnode.type == "taskcall"
        \topts := object.get(node, "options", {})
        \twhen_val := opts["when"]
        \tis_null(when_val)
        \tcount(node.line) > 0
        \tv := {
        \t\t"rule_id": "M016",
        \t\t"level": "warning",
        \t\t"message": "Empty when: conditional is deprecated and will be an error in 2.23; remove the when: key or add an explicit condition",
        \t\t"file": node.file,
        \t\t"line": node.line[0],
        \t\t"path": node.key,
        \t\t"scope": "task",
        \t}
        }
    """)


def _rego_m017_action_mapping(rule: RuleDict) -> str:
    return textwrap.dedent("""\
        # M017: action: as a mapping is deprecated (2.23)

        package apme.rules

        import future.keywords.if
        import future.keywords.in

        violations contains v if {
        \tsome tree in input.hierarchy
        \tsome node in tree.nodes
        \tv := action_as_mapping(tree, node)
        }

        action_as_mapping(tree, node) := v if {
        \tnode.type == "taskcall"
        \topts := object.get(node, "options", {})
        \taction_val := opts["action"]
        \tis_object(action_val)
        \tcount(node.line) > 0
        \tv := {
        \t\t"rule_id": "M017",
        \t\t"level": "warning",
        \t\t"message": "action: with a mapping value is deprecated in 2.23; use the module key directly with args",
        \t\t"file": node.file,
        \t\t"line": node.line[0],
        \t\t"path": node.key,
        \t\t"scope": "task",
        \t}
        }
    """)


def _rego_m018_paramiko(rule: RuleDict) -> str:
    return textwrap.dedent("""\
        # M018: paramiko_ssh connection plugin is deprecated (removed in 2.21)

        package apme.rules

        import future.keywords.if
        import future.keywords.in

        violations contains v if {
        \tsome tree in input.hierarchy
        \tsome node in tree.nodes
        \tv := paramiko_ssh_connection(tree, node)
        }

        paramiko_ssh_connection(tree, node) := v if {
        \tnode.type == "playcall"
        \topts := object.get(node, "options", {})
        \tconn := object.get(opts, "connection", "")
        \tconn == "paramiko_ssh"
        \tcount(node.line) > 0
        \tv := {
        \t\t"rule_id": "M018",
        \t\t"level": "error",
        \t\t"message": "paramiko_ssh connection plugin is removed in 2.21; use connection: ssh",
        \t\t"file": node.file,
        \t\t"line": node.line[0],
        \t\t"path": node.key,
        \t\t"scope": "play",
        \t}
        }

        paramiko_ssh_connection(tree, node) := v if {
        \tnode.type == "taskcall"
        \topts := object.get(node, "options", {})
        \tvars_block := object.get(opts, "vars", {})
        \tconn := object.get(vars_block, "ansible_connection", "")
        \tconn == "paramiko_ssh"
        \tcount(node.line) > 0
        \tv := {
        \t\t"rule_id": "M018",
        \t\t"level": "error",
        \t\t"message": "paramiko_ssh connection plugin is removed in 2.21; use ansible_connection: ssh",
        \t\t"file": node.file,
        \t\t"line": node.line[0],
        \t\t"path": node.key,
        \t\t"scope": "task",
        \t}
        }
    """)


def _rego_m021_empty_args(rule: RuleDict) -> str:
    return textwrap.dedent("""\
        # M021: Empty args: keyword on a task is deprecated (2.23)

        package apme.rules

        import future.keywords.if
        import future.keywords.in

        violations contains v if {
        \tsome tree in input.hierarchy
        \tsome node in tree.nodes
        \tv := empty_args_keyword(tree, node)
        }

        empty_args_keyword(tree, node) := v if {
        \tnode.type == "taskcall"
        \topts := object.get(node, "options", {})
        \targs_val := opts["args"]
        \tis_null(args_val)
        \tcount(node.line) > 0
        \tv := {
        \t\t"rule_id": "M021",
        \t\t"level": "warning",
        \t\t"message": "Empty args: keyword is deprecated in 2.23; remove the args: key",
        \t\t"file": node.file,
        \t\t"line": node.line[0],
        \t\t"path": node.key,
        \t\t"scope": "task",
        \t}
        }

        empty_args_keyword(tree, node) := v if {
        \tnode.type == "taskcall"
        \topts := object.get(node, "options", {})
        \targs_val := opts["args"]
        \targs_val == {}
        \tcount(node.line) > 0
        \tv := {
        \t\t"rule_id": "M021",
        \t\t"level": "warning",
        \t\t"message": "Empty args: keyword is deprecated in 2.23; remove the args: key",
        \t\t"file": node.file,
        \t\t"line": node.line[0],
        \t\t"path": node.key,
        \t\t"scope": "task",
        \t}
        }
    """)


def _rego_m023_follow_redirects(rule: RuleDict) -> str:
    return textwrap.dedent("""\
        # M023: follow_redirects: yes/no string deprecated in url lookup (2.22)

        package apme.rules

        import future.keywords.if
        import future.keywords.in

        violations contains v if {
        \tsome tree in input.hierarchy
        \tsome node in tree.nodes
        \tv := follow_redirects_string(tree, node)
        }

        _string_bools := {"yes", "no", "Yes", "No", "YES", "NO"}

        follow_redirects_string(tree, node) := v if {
        \tnode.type == "taskcall"
        \tmopts := object.get(node, "module_options", {})
        \tfr_val := mopts["follow_redirects"]
        \tis_string(fr_val)
        \t_string_bools[fr_val]
        \tcount(node.line) > 0
        \tv := {
        \t\t"rule_id": "M023",
        \t\t"level": "warning",
        \t\t"message": sprintf("follow_redirects: '%s' (string) is deprecated in 2.22; use true/false boolean", [fr_val]),
        \t\t"file": node.file,
        \t\t"line": node.line[0],
        \t\t"path": node.key,
        \t\t"scope": "task",
        \t}
        }
    """)


def _rego_m024_include_vars_ignore_files(rule: RuleDict) -> str:
    return textwrap.dedent("""\
        # M024: include_vars ignore_files must be a list, not a string (2.24)

        package apme.rules

        import future.keywords.if
        import future.keywords.in

        violations contains v if {
        \tsome tree in input.hierarchy
        \tsome node in tree.nodes
        \tv := include_vars_ignore_files_string(tree, node)
        }

        _include_vars_modules := {
        \t"ansible.builtin.include_vars",
        \t"include_vars",
        \t"ansible.legacy.include_vars",
        }

        include_vars_ignore_files_string(tree, node) := v if {
        \tnode.type == "taskcall"
        \t_include_vars_modules[node.module]
        \tmopts := object.get(node, "module_options", {})
        \tignore_val := mopts["ignore_files"]
        \tis_string(ignore_val)
        \tcount(node.line) > 0
        \tv := {
        \t\t"rule_id": "M024",
        \t\t"level": "warning",
        \t\t"message": "include_vars ignore_files must be a list, not a string (2.24); wrap in a YAML list",
        \t\t"file": node.file,
        \t\t"line": node.line[0],
        \t\t"path": node.key,
        \t\t"scope": "task",
        \t}
        }
    """)


def _rego_m025_third_party_strategy(rule: RuleDict) -> str:
    return textwrap.dedent("""\
        # M025: Third-party strategy plugins are deprecated (2.23)

        package apme.rules

        import future.keywords.if
        import future.keywords.in

        violations contains v if {
        \tsome tree in input.hierarchy
        \tsome node in tree.nodes
        \tv := third_party_strategy(tree, node)
        }

        _builtin_strategies := {"linear", "free", "debug", "host_pinned"}

        third_party_strategy(tree, node) := v if {
        \tnode.type == "playcall"
        \topts := object.get(node, "options", {})
        \tstrategy := opts["strategy"]
        \tis_string(strategy)
        \tnot _builtin_strategies[strategy]
        \tnot startswith(strategy, "ansible.builtin.")
        \tcount(node.line) > 0
        \tv := {
        \t\t"rule_id": "M025",
        \t\t"level": "warning",
        \t\t"message": sprintf("Third-party strategy plugin '%s' is deprecated in 2.23; use an ansible.builtin strategy", [strategy]),
        \t\t"file": node.file,
        \t\t"line": node.line[0],
        \t\t"path": node.key,
        \t\t"scope": "play",
        \t}
        }
    """)


def _rego_m028_first_found_split(rule: RuleDict) -> str:
    return textwrap.dedent("""\
        # M028: first_found lookup auto-splitting paths on delimiters is deprecated (2.23)

        package apme.rules

        import future.keywords.if
        import future.keywords.in

        violations contains v if {
        \tsome tree in input.hierarchy
        \tsome node in tree.nodes
        \tv := first_found_auto_split(tree, node)
        }

        _first_found_modules := {
        \t"ansible.builtin.first_found",
        \t"first_found",
        \t"ansible.legacy.first_found",
        }

        first_found_auto_split(tree, node) := v if {
        \tnode.type == "taskcall"
        \t_first_found_modules[node.module]
        \tmopts := object.get(node, "module_options", {})
        \tterms := mopts["terms"]
        \tis_string(terms)
        \tcontains(terms, ",")
        \tcount(node.line) > 0
        \tv := {
        \t\t"rule_id": "M028",
        \t\t"level": "warning",
        \t\t"message": "first_found auto-splitting paths on delimiters is deprecated in 2.23; use a YAML list",
        \t\t"file": node.file,
        \t\t"line": node.line[0],
        \t\t"path": node.key,
        \t\t"scope": "task",
        \t}
        }

        first_found_auto_split(tree, node) := v if {
        \tnode.type == "taskcall"
        \t_first_found_modules[node.module]
        \tmopts := object.get(node, "module_options", {})
        \tterms := mopts["terms"]
        \tis_string(terms)
        \tcontains(terms, ":")
        \tnot re_match(`^[a-zA-Z]:\\\\`, terms)
        \tnot re_match(`^https?://`, terms)
        \tcount(node.line) > 0
        \tv := {
        \t\t"rule_id": "M028",
        \t\t"level": "warning",
        \t\t"message": "first_found auto-splitting paths on delimiters is deprecated in 2.23; use a YAML list",
        \t\t"file": node.file,
        \t\t"line": node.line[0],
        \t\t"path": node.key,
        \t\t"scope": "task",
        \t}
        }
    """)


def _rego_generic(rule: RuleDict) -> str:
    """Fallback Rego scaffold when no rule-specific generator exists.

    Args:
        rule: Deprecation rule dict (rule_id, title, description, detection).

    Returns:
        Rego source with a stub ``false`` detection body for manual follow-up.
    """
    rid = rule["rule_id"]
    slug = _rego_slug(rule)
    desc = rule["description"]
    return textwrap.dedent(f"""\
        # {rid}: {desc}

        package apme.rules

        import future.keywords.if
        import future.keywords.in

        violations contains v if {{
        \tsome tree in input.hierarchy
        \tsome node in tree.nodes
        \tv := {slug}(tree, node)
        }}

        {slug}(tree, node) := v if {{
        \tnode.type == "taskcall"
        \topts := object.get(node, "options", {{}})
        \t# Detection: {rule["detection"]["approach"]}
        \tfalse  # needs manual implementation
        \tcount(node.line) > 0
        \tv := {{
        \t\t"rule_id": "{rid}",
        \t\t"level": "warning",
        \t\t"message": "{desc}",
        \t\t"file": node.file,
        \t\t"line": node.line[0],
        \t\t"path": node.key,
        \t\t"scope": "task",
        \t}}
        }}
    """)


# ── OPA test generation ──────────────────────────────────────────────


def generate_opa_test(rule: RuleDict) -> str:
    """Generate a Rego test file with real test cases.

    Args:
        rule: Deprecation rule dict (rule_id, title, etc.).

    Returns:
        Full ``*_test.rego`` file contents as a string.
    """
    rid = rule["rule_id"]
    generators = {
        "M016": _test_m016,
        "M017": _test_m017,
        "M018": _test_m018,
        "M021": _test_m021,
        "M023": _test_m023,
        "M024": _test_m024,
        "M025": _test_m025,
        "M028": _test_m028,
    }
    if rid in generators:
        return generators[rid](rule)
    return _test_generic(rule)


def _test_m016(rule: RuleDict) -> str:
    return textwrap.dedent("""\
        # Tests for M016: Empty when conditional

        package apme.rules_test

        import data.apme.rules

        test_M016_fires_on_empty_string if {
        \ttree := {"nodes": [{"type": "taskcall", "options": {"when": ""}, "line": [1], "key": "k", "file": "f.yml", "module": "debug"}]}
        \tnode := tree.nodes[0]
        \tv := rules.empty_when_conditional(tree, node)
        \tv.rule_id == "M016"
        }

        test_M016_fires_on_null if {
        \ttree := {"nodes": [{"type": "taskcall", "options": {"when": null}, "line": [1], "key": "k", "file": "f.yml", "module": "debug"}]}
        \tnode := tree.nodes[0]
        \tv := rules.empty_when_conditional(tree, node)
        \tv.rule_id == "M016"
        }

        test_M016_no_fire_on_real_condition if {
        \ttree := {"nodes": [{"type": "taskcall", "options": {"when": "foo is defined"}, "line": [1], "key": "k", "file": "f.yml", "module": "debug"}]}
        \tnode := tree.nodes[0]
        \tnot rules.empty_when_conditional(tree, node)
        }

        test_M016_no_fire_without_when if {
        \ttree := {"nodes": [{"type": "taskcall", "options": {}, "line": [1], "key": "k", "file": "f.yml", "module": "debug"}]}
        \tnode := tree.nodes[0]
        \tnot rules.empty_when_conditional(tree, node)
        }
    """)


def _test_m017(rule: RuleDict) -> str:
    return textwrap.dedent("""\
        # Tests for M017: action as mapping

        package apme.rules_test

        import data.apme.rules

        test_M017_fires_on_action_dict if {
        \ttree := {"nodes": [{"type": "taskcall", "options": {"action": {"module": "copy", "src": "a"}}, "line": [1], "key": "k", "file": "f.yml", "module": "copy"}]}
        \tnode := tree.nodes[0]
        \tv := rules.action_as_mapping(tree, node)
        \tv.rule_id == "M017"
        }

        test_M017_no_fire_on_action_string if {
        \ttree := {"nodes": [{"type": "taskcall", "options": {"action": "copy src=a"}, "line": [1], "key": "k", "file": "f.yml", "module": "copy"}]}
        \tnode := tree.nodes[0]
        \tnot rules.action_as_mapping(tree, node)
        }

        test_M017_no_fire_without_action if {
        \ttree := {"nodes": [{"type": "taskcall", "options": {}, "line": [1], "key": "k", "file": "f.yml", "module": "debug"}]}
        \tnode := tree.nodes[0]
        \tnot rules.action_as_mapping(tree, node)
        }
    """)


def _test_m018(rule: RuleDict) -> str:
    return textwrap.dedent("""\
        # Tests for M018: paramiko_ssh connection plugin

        package apme.rules_test

        import data.apme.rules

        test_M018_fires_on_play_paramiko if {
        \ttree := {"nodes": [{"type": "playcall", "options": {"connection": "paramiko_ssh"}, "line": [1], "key": "k", "file": "f.yml", "name": "test"}]}
        \tnode := tree.nodes[0]
        \tv := rules.paramiko_ssh_connection(tree, node)
        \tv.rule_id == "M018"
        }

        test_M018_fires_on_task_vars_paramiko if {
        \ttree := {"nodes": [{"type": "taskcall", "options": {"vars": {"ansible_connection": "paramiko_ssh"}}, "line": [1], "key": "k", "file": "f.yml", "module": "debug"}]}
        \tnode := tree.nodes[0]
        \tv := rules.paramiko_ssh_connection(tree, node)
        \tv.rule_id == "M018"
        }

        test_M018_no_fire_on_ssh if {
        \ttree := {"nodes": [{"type": "playcall", "options": {"connection": "ssh"}, "line": [1], "key": "k", "file": "f.yml", "name": "test"}]}
        \tnode := tree.nodes[0]
        \tnot rules.paramiko_ssh_connection(tree, node)
        }

        test_M018_no_fire_on_local if {
        \ttree := {"nodes": [{"type": "playcall", "options": {"connection": "local"}, "line": [1], "key": "k", "file": "f.yml", "name": "test"}]}
        \tnode := tree.nodes[0]
        \tnot rules.paramiko_ssh_connection(tree, node)
        }
    """)


def _test_m021(rule: RuleDict) -> str:
    return textwrap.dedent("""\
        # Tests for M021: Empty args keyword

        package apme.rules_test

        import data.apme.rules

        test_M021_fires_on_null_args if {
        \ttree := {"nodes": [{"type": "taskcall", "options": {"args": null}, "line": [1], "key": "k", "file": "f.yml", "module": "command"}]}
        \tnode := tree.nodes[0]
        \tv := rules.empty_args_keyword(tree, node)
        \tv.rule_id == "M021"
        }

        test_M021_fires_on_empty_dict_args if {
        \ttree := {"nodes": [{"type": "taskcall", "options": {"args": {}}, "line": [1], "key": "k", "file": "f.yml", "module": "command"}]}
        \tnode := tree.nodes[0]
        \tv := rules.empty_args_keyword(tree, node)
        \tv.rule_id == "M021"
        }

        test_M021_no_fire_on_real_args if {
        \ttree := {"nodes": [{"type": "taskcall", "options": {"args": {"chdir": "/tmp"}}, "line": [1], "key": "k", "file": "f.yml", "module": "command"}]}
        \tnode := tree.nodes[0]
        \tnot rules.empty_args_keyword(tree, node)
        }

        test_M021_no_fire_without_args if {
        \ttree := {"nodes": [{"type": "taskcall", "options": {}, "line": [1], "key": "k", "file": "f.yml", "module": "debug"}]}
        \tnode := tree.nodes[0]
        \tnot rules.empty_args_keyword(tree, node)
        }
    """)


def _test_m023(rule: RuleDict) -> str:
    return textwrap.dedent("""\
        # Tests for M023: follow_redirects string boolean

        package apme.rules_test

        import data.apme.rules

        test_M023_fires_on_yes_string if {
        \ttree := {"nodes": [{"type": "taskcall", "module_options": {"follow_redirects": "yes"}, "options": {}, "line": [1], "key": "k", "file": "f.yml", "module": "uri"}]}
        \tnode := tree.nodes[0]
        \tv := rules.follow_redirects_string(tree, node)
        \tv.rule_id == "M023"
        }

        test_M023_fires_on_no_string if {
        \ttree := {"nodes": [{"type": "taskcall", "module_options": {"follow_redirects": "no"}, "options": {}, "line": [1], "key": "k", "file": "f.yml", "module": "uri"}]}
        \tnode := tree.nodes[0]
        \tv := rules.follow_redirects_string(tree, node)
        \tv.rule_id == "M023"
        }

        test_M023_no_fire_on_boolean if {
        \ttree := {"nodes": [{"type": "taskcall", "module_options": {"follow_redirects": true}, "options": {}, "line": [1], "key": "k", "file": "f.yml", "module": "uri"}]}
        \tnode := tree.nodes[0]
        \tnot rules.follow_redirects_string(tree, node)
        }
    """)


def _test_m024(rule: RuleDict) -> str:
    return textwrap.dedent("""\
        # Tests for M024: include_vars ignore_files as string

        package apme.rules_test

        import data.apme.rules

        test_M024_fires_on_string_ignore_files if {
        \ttree := {"nodes": [{"type": "taskcall", "module_options": {"ignore_files": "*.bak", "dir": "vars/"}, "options": {}, "line": [1], "key": "k", "file": "f.yml", "module": "ansible.builtin.include_vars"}]}
        \tnode := tree.nodes[0]
        \tv := rules.include_vars_ignore_files_string(tree, node)
        \tv.rule_id == "M024"
        }

        test_M024_no_fire_on_list if {
        \ttree := {"nodes": [{"type": "taskcall", "module_options": {"ignore_files": ["*.bak"], "dir": "vars/"}, "options": {}, "line": [1], "key": "k", "file": "f.yml", "module": "ansible.builtin.include_vars"}]}
        \tnode := tree.nodes[0]
        \tnot rules.include_vars_ignore_files_string(tree, node)
        }

        test_M024_no_fire_on_other_module if {
        \ttree := {"nodes": [{"type": "taskcall", "module_options": {"ignore_files": "*.bak"}, "options": {}, "line": [1], "key": "k", "file": "f.yml", "module": "ansible.builtin.copy"}]}
        \tnode := tree.nodes[0]
        \tnot rules.include_vars_ignore_files_string(tree, node)
        }
    """)


def _test_m025(rule: RuleDict) -> str:
    return textwrap.dedent("""\
        # Tests for M025: Third-party strategy plugin

        package apme.rules_test

        import data.apme.rules

        test_M025_fires_on_mitogen if {
        \ttree := {"nodes": [{"type": "playcall", "options": {"strategy": "mitogen_linear"}, "line": [1], "key": "k", "file": "f.yml", "name": "test"}]}
        \tnode := tree.nodes[0]
        \tv := rules.third_party_strategy(tree, node)
        \tv.rule_id == "M025"
        }

        test_M025_no_fire_on_linear if {
        \ttree := {"nodes": [{"type": "playcall", "options": {"strategy": "linear"}, "line": [1], "key": "k", "file": "f.yml", "name": "test"}]}
        \tnode := tree.nodes[0]
        \tnot rules.third_party_strategy(tree, node)
        }

        test_M025_no_fire_on_free if {
        \ttree := {"nodes": [{"type": "playcall", "options": {"strategy": "free"}, "line": [1], "key": "k", "file": "f.yml", "name": "test"}]}
        \tnode := tree.nodes[0]
        \tnot rules.third_party_strategy(tree, node)
        }

        test_M025_no_fire_without_strategy if {
        \ttree := {"nodes": [{"type": "playcall", "options": {}, "line": [1], "key": "k", "file": "f.yml", "name": "test"}]}
        \tnode := tree.nodes[0]
        \tnot rules.third_party_strategy(tree, node)
        }
    """)


def _test_m028(rule: RuleDict) -> str:
    return textwrap.dedent("""\
        # Tests for M028: first_found auto-splitting paths

        package apme.rules_test

        import data.apme.rules

        test_M028_fires_on_comma_terms if {
        \ttree := {"nodes": [{"type": "taskcall", "module_options": {"terms": "a.yml,b.yml"}, "options": {}, "line": [1], "key": "k", "file": "f.yml", "module": "first_found"}]}
        \tnode := tree.nodes[0]
        \tv := rules.first_found_auto_split(tree, node)
        \tv.rule_id == "M028"
        }

        test_M028_fires_on_colon_terms if {
        \ttree := {"nodes": [{"type": "taskcall", "module_options": {"terms": "a.yml:b.yml"}, "options": {}, "line": [1], "key": "k", "file": "f.yml", "module": "first_found"}]}
        \tnode := tree.nodes[0]
        \tv := rules.first_found_auto_split(tree, node)
        \tv.rule_id == "M028"
        }

        test_M028_no_fire_on_list if {
        \ttree := {"nodes": [{"type": "taskcall", "module_options": {"terms": ["a.yml", "b.yml"]}, "options": {}, "line": [1], "key": "k", "file": "f.yml", "module": "first_found"}]}
        \tnode := tree.nodes[0]
        \tnot rules.first_found_auto_split(tree, node)
        }

        test_M028_no_fire_on_single_term if {
        \ttree := {"nodes": [{"type": "taskcall", "module_options": {"terms": "a.yml"}, "options": {}, "line": [1], "key": "k", "file": "f.yml", "module": "first_found"}]}
        \tnode := tree.nodes[0]
        \tnot rules.first_found_auto_split(tree, node)
        }

        test_M028_no_fire_on_url if {
        \ttree := {"nodes": [{"type": "taskcall", "module_options": {"terms": "https://example.com/vars.yml"}, "options": {}, "line": [1], "key": "k", "file": "f.yml", "module": "first_found"}]}
        \tnode := tree.nodes[0]
        \tnot rules.first_found_auto_split(tree, node)
        }
    """)


def _test_generic(rule: RuleDict) -> str:
    rid = rule["rule_id"]
    slug = _rego_slug(rule)
    return textwrap.dedent(f"""\
        # Tests for {rid}: {rule["title"]}

        package apme.rules_test

        import data.apme.rules

        test_{rid}_no_fire_on_clean if {{
        \ttree := {{"nodes": [{{"type": "taskcall", "options": {{}}, "line": [1], "key": "k", "file": "f.yml", "module": "debug"}}]}}
        \tnode := tree.nodes[0]
        \tnot rules.{slug}(tree, node)
        }}
    """)


# ── Native Python generation (fully implemented detection) ───────────


def _python_class_name(rule: RuleDict) -> str:
    words = rule["title"].replace("/", " ").replace("-", " ").replace("!", "").split()
    return "".join(w.capitalize() for w in words) + "Rule"


def _python_filename(rule: RuleDict) -> str:
    rid = rule["rule_id"]
    slug = rule["title"].lower().replace(" ", "_").replace("/", "_").replace("-", "_")
    slug = "".join(c for c in slug if c.isalnum() or c == "_")
    return f"{rid}_{slug}.py"


def generate_native_rule(rule: RuleDict) -> str:
    """Generate a native Python rule module with detection logic.

    Args:
        rule: Deprecation rule dict (rule_id, title, description, etc.).

    Returns:
        Full ``.py`` rule module source as a string.
    """
    rid = rule["rule_id"]
    generators = {
        "M014": _native_m014_top_level_facts,
        "M015": _native_m015_play_hosts,
        "M019": _native_m019_omap_pairs,
        "M020": _native_m020_vault_encrypted,
        "M022": _native_m022_callback_plugins,
        "M026": _native_m026_invalid_var_names,
        "M027": _native_m027_kv_with_args,
        "M029": _native_m029_inventory_meta,
        "M030": _native_m030_broken_conditional,
    }
    if rid in generators:
        return generators[rid](rule)
    return _native_generic(rule)


def _native_m014_top_level_facts(rule: RuleDict) -> str:
    return textwrap.dedent('''\
        """M014: Top-level fact variables — use ansible_facts["name"] (removed in 2.24).

        Higher severity than L076 (lint/style): this is a *breaking change* in 2.24
        where top-level fact injection is removed entirely. L076 is a best-practice
        recommendation; M014 fires only when the target ansible_core_version >= 2.24.
        """

        import re
        from dataclasses import dataclass
        from typing import cast

        from apme_engine.engine.models import (
            AnsibleRunContext,
            Rule,
            RuleResult,
            RunTargetType,
            Severity,
            YAMLDict,
        )
        from apme_engine.engine.models import (
            RuleTag as Tag,
        )

        MAGIC_VARS = frozenset({
            "ansible_check_mode", "ansible_diff_mode", "ansible_forks",
            "ansible_play_batch", "ansible_play_hosts", "ansible_play_hosts_all",
            "ansible_play_name", "ansible_play_role_names", "ansible_role_names",
            "ansible_run_tags", "ansible_skip_tags", "ansible_version",
            "ansible_loop", "ansible_loop_var", "ansible_index_var",
            "ansible_parent_role_names", "ansible_parent_role_paths",
            "ansible_facts", "ansible_local",
            "ansible_verbosity", "ansible_config_file",
            "ansible_connection", "ansible_become", "ansible_become_method",
        })

        _ANSIBLE_VAR = re.compile(r"\\b(ansible_\\w+)\\b")


        @dataclass
        class TopLevelFactVariablesRule(Rule):
            """Detect injected ansible_* fact variables that will break in 2.24.

            Attributes:
                rule_id: Rule identifier.
                description: Rule description.
                enabled: Whether the rule is enabled.
                name: Rule name.
                version: Rule version.
                severity: Severity level.
                tags: Rule tags.
            """

            rule_id: str = "M014"
            description: str = "Use ansible_facts[\\"name\\"] instead of injected ansible_* fact variables (removed in 2.24)"
            enabled: bool = True
            name: str = "TopLevelFactVariables"
            version: str = "v0.0.1"
            severity: str = Severity.HIGH
            tags: tuple[str, ...] = (Tag.CODING,)

            def match(self, ctx: AnsibleRunContext) -> bool:
                """Check if context has a task target."""
                if ctx.current is None:
                    return False
                return bool(ctx.current.type == RunTargetType.Task)

            def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
                """Scan Jinja2 expressions for deprecated top-level fact variables."""
                task = ctx.current
                if task is None:
                    return None

                yaml_lines = getattr(task.spec, "yaml_lines", "") or ""
                options = getattr(task.spec, "options", None) or {}
                module_options = getattr(task.spec, "module_options", None) or {}

                all_text_parts = [yaml_lines]
                for v in list(options.values()) + list(module_options.values()):
                    if isinstance(v, str):
                        all_text_parts.append(v)
                text = " ".join(all_text_parts)

                found = set()
                for m in _ANSIBLE_VAR.finditer(text):
                    varname = m.group(1)
                    if varname not in MAGIC_VARS and varname.startswith("ansible_"):
                        found.add(varname)

                verdict = len(found) > 0
                detail: dict[str, object] = {}
                if found:
                    suggestions = {v: f\'ansible_facts["{v.removeprefix("ansible_")}"]' for v in sorted(found)}
                    detail["message"] = f"Top-level fact variable(s) {', '.join(sorted(found))} removed in 2.24"
                    detail["found_facts"] = sorted(found)
                    detail["suggestions"] = suggestions
                return RuleResult(
                    verdict=verdict,
                    detail=cast(YAMLDict | None, detail),
                    file=cast("tuple[str | int, ...] | None", task.file_info()),
                    rule=self.get_metadata(),
                )
    ''')


def _native_m015_play_hosts(rule: RuleDict) -> str:
    return textwrap.dedent('''\
        """M015: play_hosts magic variable is deprecated (removed in 2.23).

        Use ansible_play_batch instead.
        """

        import re
        from dataclasses import dataclass
        from typing import cast

        from apme_engine.engine.models import (
            AnsibleRunContext,
            Rule,
            RuleResult,
            RunTargetType,
            Severity,
            YAMLDict,
        )
        from apme_engine.engine.models import (
            RuleTag as Tag,
        )

        _PLAY_HOSTS_REF = re.compile(r"\\bplay_hosts\\b")


        @dataclass
        class PlayHostsMagicVariableRule(Rule):
            """Detect deprecated play_hosts variable usage.

            Attributes:
                rule_id: Rule identifier.
                description: Rule description.
                enabled: Whether the rule is enabled.
                name: Rule name.
                version: Rule version.
                severity: Severity level.
                tags: Rule tags.
            """

            rule_id: str = "M015"
            description: str = "Use ansible_play_batch instead of deprecated play_hosts variable (removed in 2.23)"
            enabled: bool = True
            name: str = "PlayHostsMagicVariable"
            version: str = "v0.0.1"
            severity: str = Severity.MEDIUM
            tags: tuple[str, ...] = (Tag.CODING,)

            def match(self, ctx: AnsibleRunContext) -> bool:
                """Check if context has a task target."""
                if ctx.current is None:
                    return False
                return bool(ctx.current.type == RunTargetType.Task)

            def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
                """Scan Jinja2 expressions for deprecated play_hosts variable."""
                task = ctx.current
                if task is None:
                    return None

                yaml_lines = getattr(task.spec, "yaml_lines", "") or ""
                options = getattr(task.spec, "options", None) or {}
                module_options = getattr(task.spec, "module_options", None) or {}

                all_text_parts = [yaml_lines]
                for v in list(options.values()) + list(module_options.values()):
                    if isinstance(v, str):
                        all_text_parts.append(v)
                text = " ".join(all_text_parts)

                found = bool(_PLAY_HOSTS_REF.search(text))
                detail: dict[str, object] = {}
                if found:
                    detail["message"] = "play_hosts is deprecated in 2.23; use ansible_play_batch"
                    detail["replacement"] = "ansible_play_batch"
                return RuleResult(
                    verdict=found,
                    detail=cast(YAMLDict | None, detail),
                    file=cast("tuple[str | int, ...] | None", task.file_info()),
                    rule=self.get_metadata(),
                )
    ''')


def _native_m019_omap_pairs(rule: RuleDict) -> str:
    return textwrap.dedent('''\
        """M019: !!omap / !!pairs YAML tags are deprecated (2.23).

        Standard YAML mappings preserve insertion order in Python 3.7+.
        """

        from dataclasses import dataclass
        from typing import cast

        from apme_engine.engine.models import (
            AnsibleRunContext,
            Rule,
            RuleResult,
            RunTargetType,
            Severity,
            YAMLDict,
        )
        from apme_engine.engine.models import (
            RuleTag as Tag,
        )


        @dataclass
        class OmapPairsYamlTagsRule(Rule):
            """Detect !!omap and !!pairs YAML tags in content.

            Attributes:
                rule_id: Rule identifier.
                description: Rule description.
                enabled: Whether the rule is enabled.
                name: Rule name.
                version: Rule version.
                severity: Severity level.
                tags: Rule tags.
            """

            rule_id: str = "M019"
            description: str = "!!omap and !!pairs YAML tags are deprecated; use plain mappings (2.23)"
            enabled: bool = True
            name: str = "OmapPairsYamlTags"
            version: str = "v0.0.1"
            severity: str = Severity.LOW
            tags: tuple[str, ...] = (Tag.CODING,)

            def match(self, ctx: AnsibleRunContext) -> bool:
                """Check if context has a task target."""
                if ctx.current is None:
                    return False
                return bool(ctx.current.type == RunTargetType.Task)

            def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
                """Scan raw YAML for !!omap or !!pairs tags."""
                task = ctx.current
                if task is None:
                    return None

                yaml_lines = getattr(task.spec, "yaml_lines", "") or ""
                found_tags = []
                if "!!omap" in yaml_lines:
                    found_tags.append("!!omap")
                if "!!pairs" in yaml_lines:
                    found_tags.append("!!pairs")

                verdict = len(found_tags) > 0
                detail: dict[str, object] = {}
                if found_tags:
                    detail["message"] = f"Deprecated YAML tag(s): {', '.join(found_tags)}; dicts are ordered in Python 3.7+"
                    detail["tags"] = found_tags
                return RuleResult(
                    verdict=verdict,
                    detail=cast(YAMLDict | None, detail),
                    file=cast("tuple[str | int, ...] | None", task.file_info()),
                    rule=self.get_metadata(),
                )
    ''')


def _native_m020_vault_encrypted(rule: RuleDict) -> str:
    return textwrap.dedent('''\
        """M020: !vault-encrypted tag is deprecated (2.23). Use !vault instead."""

        from dataclasses import dataclass
        from typing import cast

        from apme_engine.engine.models import (
            AnsibleRunContext,
            Rule,
            RuleResult,
            RunTargetType,
            Severity,
            YAMLDict,
        )
        from apme_engine.engine.models import (
            RuleTag as Tag,
        )


        @dataclass
        class VaultEncryptedTagRule(Rule):
            """Detect !vault-encrypted YAML tag usage.

            Attributes:
                rule_id: Rule identifier.
                description: Rule description.
                enabled: Whether the rule is enabled.
                name: Rule name.
                version: Rule version.
                severity: Severity level.
                tags: Rule tags.
            """

            rule_id: str = "M020"
            description: str = "Use !vault instead of deprecated !vault-encrypted tag (2.23)"
            enabled: bool = True
            name: str = "VaultEncryptedTag"
            version: str = "v0.0.1"
            severity: str = Severity.LOW
            tags: tuple[str, ...] = (Tag.CODING,)

            def match(self, ctx: AnsibleRunContext) -> bool:
                """Check if context has a task target."""
                if ctx.current is None:
                    return False
                return bool(ctx.current.type == RunTargetType.Task)

            def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
                """Scan raw YAML for !vault-encrypted tag."""
                task = ctx.current
                if task is None:
                    return None

                yaml_lines = getattr(task.spec, "yaml_lines", "") or ""
                verdict = "!vault-encrypted" in yaml_lines
                detail: dict[str, object] = {}
                if verdict:
                    detail["message"] = "!vault-encrypted is deprecated in 2.23; use !vault"
                    detail["replacement"] = "!vault"
                return RuleResult(
                    verdict=verdict,
                    detail=cast(YAMLDict | None, detail),
                    file=cast("tuple[str | int, ...] | None", task.file_info()),
                    rule=self.get_metadata(),
                )
    ''')


def _native_m022_callback_plugins(rule: RuleDict) -> str:
    return textwrap.dedent('''\
        """M022: tree / oneline callback plugins removed in 2.23.

        Detects tasks that set ANSIBLE_STDOUT_CALLBACK or similar environment
        variables to a removed callback. Does not scan ansible.cfg directly
        since that is outside the playbook/role task scope.
        """

        import re
        from dataclasses import dataclass
        from typing import cast

        from apme_engine.engine.models import (
            AnsibleRunContext,
            Rule,
            RuleResult,
            RunTargetType,
            Severity,
            YAMLDict,
        )
        from apme_engine.engine.models import (
            RuleTag as Tag,
        )

        _REMOVED_CALLBACKS = {"tree", "oneline"}
        _CALLBACK_REF = re.compile(r"\\b(?:stdout_callback|callback_whitelist|callbacks_enabled)\\s*[=:]\\s*(\\w+)")


        @dataclass
        class TreeOnelineCallbackPluginsRule(Rule):
            """Detect references to removed tree/oneline callback plugins.

            Attributes:
                rule_id: Rule identifier.
                description: Rule description.
                enabled: Whether the rule is enabled.
                name: Rule name.
                version: Rule version.
                severity: Severity level.
                tags: Rule tags.
            """

            rule_id: str = "M022"
            description: str = "tree and oneline callback plugins are removed in 2.23"
            enabled: bool = True
            name: str = "TreeOnelineCallbackPlugins"
            version: str = "v0.0.1"
            severity: str = Severity.MEDIUM
            tags: tuple[str, ...] = (Tag.CODING,)

            def match(self, ctx: AnsibleRunContext) -> bool:
                """Check if context has a task target."""
                if ctx.current is None:
                    return False
                return bool(ctx.current.type == RunTargetType.Task)

            def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
                """Check for references to removed callback plugins."""
                task = ctx.current
                if task is None:
                    return None

                yaml_lines = getattr(task.spec, "yaml_lines", "") or ""
                options = getattr(task.spec, "options", None) or {}
                module_options = getattr(task.spec, "module_options", None) or {}

                all_text = yaml_lines
                for v in list(options.values()) + list(module_options.values()):
                    if isinstance(v, str):
                        all_text += " " + v

                found = set()
                for m in _CALLBACK_REF.finditer(all_text):
                    cb = m.group(1).strip()
                    if cb in _REMOVED_CALLBACKS:
                        found.add(cb)

                env_vars = options.get("environment") or {}
                if isinstance(env_vars, dict):
                    for key in ("ANSIBLE_STDOUT_CALLBACK",):
                        val = env_vars.get(key, "")
                        if isinstance(val, str) and val in _REMOVED_CALLBACKS:
                            found.add(val)

                verdict = len(found) > 0
                detail: dict[str, object] = {}
                if found:
                    detail["message"] = f"Removed callback plugin(s): {', '.join(sorted(found))}"
                    detail["removed_callbacks"] = sorted(found)
                return RuleResult(
                    verdict=verdict,
                    detail=cast(YAMLDict | None, detail),
                    file=cast("tuple[str | int, ...] | None", task.file_info()),
                    rule=self.get_metadata(),
                )
    ''')


def _native_m026_invalid_var_names(rule: RuleDict) -> str:
    return textwrap.dedent('''\
        """M026: Invalid inventory variable names enforced in 2.23.

        Variable names must be valid Python identifiers.
        """

        from dataclasses import dataclass
        from typing import cast

        from apme_engine.engine.models import (
            AnsibleRunContext,
            Rule,
            RuleResult,
            RunTargetType,
            Severity,
            YAMLDict,
        )
        from apme_engine.engine.models import (
            RuleTag as Tag,
        )


        @dataclass
        class InvalidInventoryVariableNamesRule(Rule):
            """Detect variable names that are not valid Python identifiers.

            Attributes:
                rule_id: Rule identifier.
                description: Rule description.
                enabled: Whether the rule is enabled.
                name: Rule name.
                version: Rule version.
                severity: Severity level.
                tags: Rule tags.
            """

            rule_id: str = "M026"
            description: str = "Inventory variable names must be valid Python identifiers (enforced in 2.23)"
            enabled: bool = True
            name: str = "InvalidInventoryVariableNames"
            version: str = "v0.0.1"
            severity: str = Severity.MEDIUM
            tags: tuple[str, ...] = (Tag.VARIABLE,)

            def match(self, ctx: AnsibleRunContext) -> bool:
                """Check if context has a task target."""
                if ctx.current is None:
                    return False
                return bool(ctx.current.type == RunTargetType.Task)

            def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
                """Check set_fact/vars keys for invalid Python identifiers."""
                task = ctx.current
                if task is None:
                    return None

                module_options = getattr(task.spec, "module_options", None) or {}
                options = getattr(task.spec, "options", None) or {}
                task_vars = options.get("vars") or {}

                invalid = []
                for src in (module_options, task_vars):
                    if isinstance(src, dict):
                        for key in src:
                            if isinstance(key, str) and not key.isidentifier():
                                invalid.append(key)

                verdict = len(invalid) > 0
                detail: dict[str, object] = {}
                if invalid:
                    detail["message"] = f"Invalid variable name(s): {', '.join(invalid)}"
                    detail["invalid_names"] = invalid
                return RuleResult(
                    verdict=verdict,
                    detail=cast(YAMLDict | None, detail),
                    file=cast("tuple[str | int, ...] | None", task.file_info()),
                    rule=self.get_metadata(),
                )
    ''')


def _native_m027_kv_with_args(rule: RuleDict) -> str:
    return textwrap.dedent('''\
        """M027: Mixing inline k=v arguments with args: mapping is deprecated (2.23)."""

        import re
        from dataclasses import dataclass
        from typing import cast

        from apme_engine.engine.models import (
            AnsibleRunContext,
            Rule,
            RuleResult,
            RunTargetType,
            Severity,
            YAMLDict,
        )
        from apme_engine.engine.models import (
            RuleTag as Tag,
        )

        _KV_INLINE = re.compile(r"\\w+=\\S")


        @dataclass
        class LegacyKvMergedWithArgsRule(Rule):
            """Detect tasks that mix inline k=v args with an args: mapping.

            Attributes:
                rule_id: Rule identifier.
                description: Rule description.
                enabled: Whether the rule is enabled.
                name: Rule name.
                version: Rule version.
                severity: Severity level.
                tags: Rule tags.
            """

            rule_id: str = "M027"
            description: str = "Mixing inline k=v arguments with args: mapping is deprecated (2.23)"
            enabled: bool = True
            name: str = "LegacyKvMergedWithArgs"
            version: str = "v0.0.1"
            severity: str = Severity.LOW
            tags: tuple[str, ...] = (Tag.CODING,)

            def match(self, ctx: AnsibleRunContext) -> bool:
                """Check if context has a task target."""
                if ctx.current is None:
                    return False
                return bool(ctx.current.type == RunTargetType.Task)

            def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
                """Check for inline k=v + args: mapping in the same task."""
                task = ctx.current
                if task is None:
                    return None

                options = getattr(task.spec, "options", None) or {}
                module_options = getattr(task.spec, "module_options", None) or {}

                has_args_key = "args" in options and isinstance(options.get("args"), dict) and bool(options["args"])

                has_inline_kv = False
                raw = module_options.get("_raw_params", "")
                if isinstance(raw, str) and _KV_INLINE.search(raw):
                    has_inline_kv = True
                else:
                    for val in module_options.values():
                        if isinstance(val, str) and _KV_INLINE.search(val):
                            has_inline_kv = True
                            break

                verdict = has_args_key and has_inline_kv
                detail: dict[str, object] = {}
                if verdict:
                    detail["message"] = "Inline k=v args merged with args: mapping is deprecated in 2.23; move all params into args: or module key"
                return RuleResult(
                    verdict=verdict,
                    detail=cast(YAMLDict | None, detail),
                    file=cast("tuple[str | int, ...] | None", task.file_info()),
                    rule=self.get_metadata(),
                )
    ''')


def _native_m029_inventory_meta(rule: RuleDict) -> str:
    return textwrap.dedent('''\
        """M029: Inventory scripts must include _meta.hostvars (enforced in 2.23).

        Detection scope is limited: this rule fires when it sees an inventory
        script plugin task (script-based inventory) without evidence of _meta.
        Full detection requires running the script, so this is informational.
        """

        from dataclasses import dataclass
        from typing import cast

        from apme_engine.engine.models import (
            AnsibleRunContext,
            Rule,
            RuleResult,
            RunTargetType,
            Severity,
            YAMLDict,
        )
        from apme_engine.engine.models import (
            RuleTag as Tag,
        )


        @dataclass
        class InventoryScriptMissingMetaRule(Rule):
            """Informational rule about inventory script _meta requirement.

            Attributes:
                rule_id: Rule identifier.
                description: Rule description.
                enabled: Whether the rule is enabled.
                name: Rule name.
                version: Rule version.
                severity: Severity level.
                tags: Rule tags.
            """

            rule_id: str = "M029"
            description: str = "Inventory scripts must include _meta.hostvars in JSON output (enforced in 2.23)"
            enabled: bool = False
            name: str = "InventoryScriptMissingMeta"
            version: str = "v0.0.1"
            severity: str = Severity.MEDIUM
            tags: tuple[str, ...] = (Tag.CODING,)

            def match(self, ctx: AnsibleRunContext) -> bool:
                """This rule is disabled by default (informational)."""
                return False

            def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
                """No-op: informational rule, not statically detectable."""
                return None
    ''')


def _native_m030_broken_conditional(rule: RuleDict) -> str:
    return textwrap.dedent('''\
        """M030: Broken conditional expressions will error in 2.23.

        Attempts to parse when: values as Jinja2 expressions and flags
        those that fail to parse.
        """

        from dataclasses import dataclass
        from typing import cast

        from apme_engine.engine.models import (
            AnsibleRunContext,
            Rule,
            RuleResult,
            RunTargetType,
            Severity,
            YAMLDict,
        )
        from apme_engine.engine.models import (
            RuleTag as Tag,
        )

        try:
            from jinja2 import Environment as _Env
            _JINJA_ENV = _Env()
            HAS_JINJA = True
        except ImportError:
            HAS_JINJA = False
            _JINJA_ENV = None


        @dataclass
        class BrokenConditionalExpressionsRule(Rule):
            """Detect when: conditions that fail Jinja2 expression parsing.

            Attributes:
                rule_id: Rule identifier.
                description: Rule description.
                enabled: Whether the rule is enabled.
                name: Rule name.
                version: Rule version.
                severity: Severity level.
                tags: Rule tags.
            """

            rule_id: str = "M030"
            description: str = "Broken conditional expressions will error in 2.23"
            enabled: bool = True
            name: str = "BrokenConditionalExpressions"
            version: str = "v0.0.1"
            severity: str = Severity.MEDIUM
            tags: tuple[str, ...] = (Tag.CODING,)

            def match(self, ctx: AnsibleRunContext) -> bool:
                """Check if context has a task target and Jinja2 is available."""
                if not HAS_JINJA:
                    return False
                if ctx.current is None:
                    return False
                return bool(ctx.current.type == RunTargetType.Task)

            def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
                """Parse when: value as a Jinja2 expression."""
                task = ctx.current
                if task is None:
                    return None

                options = getattr(task.spec, "options", None) or {}
                when_val = options.get("when")
                if when_val is None or when_val == "":
                    return RuleResult(
                        verdict=False, detail=cast(YAMLDict | None, {}),
                        file=cast("tuple[str | int, ...] | None", task.file_info()),
                        rule=self.get_metadata(),
                    )

                when_list = when_val if isinstance(when_val, list) else [when_val]
                broken = []
                for cond in when_list:
                    if not isinstance(cond, str):
                        continue
                    cond = cond.strip()
                    if not cond:
                        continue
                    try:
                        _JINJA_ENV.parse("{{ " + cond + " }}")
                    except Exception:
                        broken.append(cond)

                verdict = len(broken) > 0
                detail: dict[str, object] = {}
                if broken:
                    detail["message"] = f"Broken conditional(s) will error in 2.23: {broken}"
                    detail["broken_conditions"] = broken
                return RuleResult(
                    verdict=verdict,
                    detail=cast(YAMLDict | None, detail),
                    file=cast("tuple[str | int, ...] | None", task.file_info()),
                    rule=self.get_metadata(),
                )
    ''')


def _native_generic(rule: RuleDict) -> str:
    rid = rule["rule_id"]
    cls = _python_class_name(rule)
    desc = rule["description"]
    severity = rule.get("severity", "medium").upper()
    detection = rule["detection"]["approach"]

    return textwrap.dedent(f'''\
        """{rid}: {rule["title"]} — {desc}

        Removal version: {rule["removal_version"]}
        Detection: {detection}
        """

        from dataclasses import dataclass
        from typing import cast

        from apme_engine.engine.models import (
            AnsibleRunContext,
            Rule,
            RuleResult,
            RunTargetType,
            Severity,
            YAMLDict,
        )
        from apme_engine.engine.models import (
            RuleTag as Tag,
        )


        @dataclass
        class {cls}(Rule):
            """{desc}

            Attributes:
                rule_id: Rule identifier.
                description: Rule description.
                enabled: Whether the rule is enabled.
                name: Rule name.
                version: Rule version.
                severity: Severity level.
                tags: Rule tags.
            """

            rule_id: str = "{rid}"
            description: str = "{desc}"
            enabled: bool = True
            name: str = "{cls.replace("Rule", "")}"
            version: str = "v0.0.1"
            severity: str = Severity.{severity}
            tags: tuple[str, ...] = (Tag.CODING,)

            def match(self, ctx: AnsibleRunContext) -> bool:
                """Check if context has a task target."""
                if ctx.current is None:
                    return False
                return bool(ctx.current.type == RunTargetType.Task)

            def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
                """Detect {rule["title"]} pattern."""
                task = ctx.current
                if task is None:
                    return None

                verdict = False
                detail: dict[str, object] = {{}}
                return RuleResult(
                    verdict=verdict,
                    detail=cast(YAMLDict | None, detail),
                    file=cast("tuple[str | int, ...] | None", task.file_info()),
                    rule=self.get_metadata(),
                )
    ''')


# ── Markdown documentation generation ────────────────────────────────


def generate_rule_md(rule: RuleDict) -> str:
    """Generate markdown documentation for a rule.

    Args:
        rule: Deprecation rule dict (frontmatter fields, examples, remediation).

    Returns:
        Markdown string with YAML frontmatter and body sections.
    """
    rid = rule["rule_id"]
    validator = rule["validator"]
    desc = rule["description"]
    violation = rule.get("example_violation", "# add example").strip()
    pass_yaml = rule.get("example_pass", "# add example").strip()
    strategy = rule.get("remediation", {}).get("strategy", "Manual review required.")

    return (
        f"---\n"
        f"rule_id: {rid}\n"
        f"validator: {validator}\n"
        f"description: {desc}\n"
        f"scope: task\n"
        f"---\n"
        f"\n"
        f"## {rule['title']} ({rid})\n"
        f"\n"
        f"{desc}\n"
        f"\n"
        f"**Removal version**: {rule['removal_version']}\n"
        f"**Fix tier**: {rule.get('fix_tier', 'N/A')}\n"
        f"**Audience**: {rule.get('audience', 'content')}\n"
        f"\n"
        f"### Detection\n"
        f"\n"
        f"{rule['detection']['approach']}\n"
        f"\n"
        f"### Example: violation\n"
        f"\n"
        f"```yaml\n"
        f"{violation}\n"
        f"```\n"
        f"\n"
        f"### Example: pass\n"
        f"\n"
        f"```yaml\n"
        f"{pass_yaml}\n"
        f"```\n"
        f"\n"
        f"### Remediation\n"
        f"\n"
        f"{strategy}\n"
    )


# ── Migration doc table generation ────────────────────────────────────


def generate_migration_table(rules: list[RuleDict]) -> str:
    """Build a summary table snippet for ANSIBLE_CORE_MIGRATION.md.

    Args:
        rules: Rule dicts to include (rule_id, removal_version, title, validator, etc.).

    Returns:
        Markdown heading and pipe table lines joined by newlines.
    """
    lines = [
        "## Deprecation Rules (2.21\u20132.24) \u2014 Auto-generated",
        "",
        "| Rule | Version | Pattern | Validator | Fix Tier | Priority |",
        "|------|---------|---------|-----------|----------|----------|",
    ]

    for r in sorted(rules, key=lambda x: (x["removal_version"], x["rule_id"])):
        fix = f"Tier {r.get('fix_tier', '?')}"
        lines.append(
            f"| {r['rule_id']} | {r['removal_version']} "
            f"| {r['title']} | {r['validator']} | {fix} | P{r.get('priority', '?')} |"
        )

    lines.append("")
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────


def main() -> None:
    """Generate rule scaffolds with deduplication against existing rules."""
    parser = argparse.ArgumentParser(
        description="Generate APME M-rule scaffolds from deprecation rule definitions.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print what would be generated without writing files")
    parser.add_argument("--rules", help="Comma-separated rule IDs to generate (default: all)")
    parser.add_argument("--input", type=Path, default=None, help="Path to deprecation_rules.json or .yaml")
    parser.add_argument("--force", action="store_true", help="Overwrite existing rule files")
    parser.add_argument(
        "--check", action="store_true", help="Check mode: exit 1 if new rules would be generated (for CI)"
    )

    args = parser.parse_args()
    filter_ids = set(args.rules.split(",")) if args.rules else None
    rules = load_rules(args.input, filter_ids)

    if not rules:
        print("No rules to generate.", file=sys.stderr)
        sys.exit(0)

    # Inventory existing rules for deduplication
    existing, infos = inventory_existing_rules()
    print(f"Found {len(existing)} existing rules in the codebase", file=sys.stderr)

    created: list[str] = []
    skipped: list[str] = []
    duplicates: list[str] = []
    overlap_warnings: list[str] = []

    for rule in rules:
        rid = rule["rule_id"]
        validator = rule["validator"]

        # Check for exact rule_id duplicate
        if rid in existing and not args.force:
            duplicates.append(f"{rid} (exists at {existing[rid]})")
            continue

        # Check for semantic overlap with existing rules
        overlaps = check_semantic_overlap(rule, existing, infos)
        for oid, reason in overlaps:
            overlap_warnings.append(f"{rid} overlaps with existing {oid} — {reason}")

        if validator == "opa":
            rego_path = OPA_BUNDLE / f"{rid}.rego"
            test_path = OPA_BUNDLE / f"{rid}_test.rego"
            md_path = OPA_BUNDLE / f"{rid}.md"

            for path, content, label in [
                (rego_path, generate_opa_rule(rule), f"{rid}.rego"),
                (test_path, generate_opa_test(rule), f"{rid}_test.rego"),
                (md_path, generate_rule_md(rule), f"{rid}.md"),
            ]:
                if not args.force and path.exists():
                    skipped.append(label)
                    continue
                if args.dry_run or args.check:
                    created.append(label)
                else:
                    path.write_text(content, encoding="utf-8")
                    created.append(label)
                    print(f"  Created: {path.relative_to(REPO_ROOT)}")

        elif validator == "native":
            py_filename = _python_filename(rule)
            py_path = NATIVE_RULES / py_filename
            md_stem = py_filename.split("_", 1)[1].replace(".py", ".md")
            md_path = NATIVE_RULES / f"{rid}_{md_stem}"

            for path, content, label in [
                (py_path, generate_native_rule(rule), py_filename),
                (md_path, generate_rule_md(rule), md_path.name),
            ]:
                if not args.force and path.exists():
                    skipped.append(label)
                    continue
                if args.dry_run or args.check:
                    created.append(label)
                else:
                    path.write_text(content, encoding="utf-8")
                    created.append(label)
                    print(f"  Created: {path.relative_to(REPO_ROOT)}")

    # Print migration table
    non_dup_rules = [r for r in rules if r["rule_id"] not in {d.split(" ")[0] for d in duplicates}]
    if non_dup_rules:
        print("\n" + "=" * 60, file=sys.stderr)
        print("Migration summary table:", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(generate_migration_table(non_dup_rules))

    # Summary
    print(f"\nCreated: {len(created)} files", file=sys.stderr)
    if skipped:
        print(f"Skipped: {len(skipped)} files (already exist)", file=sys.stderr)
    if duplicates:
        print(f"Duplicates avoided: {len(duplicates)}", file=sys.stderr)
        for d in duplicates:
            print(f"  - {d}", file=sys.stderr)
    if overlap_warnings:
        print(f"Overlap warnings: {len(overlap_warnings)}", file=sys.stderr)
        for w in overlap_warnings:
            print(f"  ⚠ {w}", file=sys.stderr)
    if args.dry_run:
        print("(dry run — no files were written)", file=sys.stderr)

    if args.check:
        if created:
            print(f"\n{len(created)} new rule files would be created", file=sys.stderr)
            sys.exit(1)
        else:
            print("\nNo new rules to generate", file=sys.stderr)
            sys.exit(0)


if __name__ == "__main__":
    main()
