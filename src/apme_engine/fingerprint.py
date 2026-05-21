"""Content-based violation fingerprinting (ADR-055).

Provides deterministic SHA-256 fingerprints for violations based on
rule ID and normalized task YAML content. Shared by CLI and Gateway.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from io import StringIO

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

_LEGACY_PREFIX_RE = re.compile(r"^(native|opa|ansible|gitleaks):")
_BLANK_LINE_RUN_RE = re.compile(r"\n{3,}")


def canonicalize_rule_id(raw_id: str) -> str:
    """Strip legacy validator prefixes to produce a bare rule ID.

    Args:
        raw_id: Raw rule ID possibly prefixed with ``native:``, ``opa:``, etc.

    Returns:
        Canonical rule ID (e.g. ``L046``).
    """
    return _LEGACY_PREFIX_RE.sub("", raw_id.strip())


def _strip_comments(data: object) -> None:
    """Recursively remove all YAML comments from a ruamel data structure.

    Args:
        data: A ruamel.yaml CommentedMap, CommentedSeq, or scalar.
    """
    if isinstance(data, CommentedMap):
        data.ca.comment = None
        for key in data.ca.items:
            data.ca.items[key] = [None, None, None, None]
        for val in data.values():
            _strip_comments(val)
    elif isinstance(data, CommentedSeq):
        data.ca.comment = None
        for idx in list(data.ca.items):
            data.ca.items[idx] = [None, None, None, None]
        for item in data:
            _strip_comments(item)


def normalize_yaml(text: str) -> str:
    """Normalize YAML for fingerprinting: strip comments, normalize whitespace.

    Preserves block scalar bodies verbatim (content inside ``|``/``>`` is
    runtime data). Does NOT re-order keys, change quoting, or alter values.

    Args:
        text: Raw YAML text (single node/task).

    Returns:
        Normalized YAML string (UTF-8 NFC, LF line endings).
    """
    if not text or not text.strip():
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFC", text)

    yaml = YAML(typ="rt", pure=True)
    yaml.preserve_quotes = True
    yaml.allow_duplicate_keys = True
    yaml.width = 4096

    try:
        data = yaml.load(text)
    except Exception:
        return _fallback_normalize(text)

    if data is None:
        return ""

    _strip_comments(data)

    out_yaml = YAML(typ="rt", pure=True)
    out_yaml.preserve_quotes = True
    out_yaml.allow_duplicate_keys = True
    out_yaml.width = 4096
    out_yaml.indent(mapping=2, sequence=2, offset=2)

    try:
        buf = StringIO()
        out_yaml.dump(data, buf)
        result = buf.getvalue()
    except Exception:
        return _fallback_normalize(text)

    result = result.replace("\r\n", "\n")
    result = _BLANK_LINE_RUN_RE.sub("\n\n", result)
    result = result.strip()

    return unicodedata.normalize("NFC", result)


def _fallback_normalize(text: str) -> str:
    """Best-effort normalization when YAML parsing fails.

    Strips unindented comment lines, normalizes whitespace, preserves content.
    Indented ``#`` lines are kept because they may be block-scalar content.

    Args:
        text: Raw YAML text that failed to parse.

    Returns:
        Normalized text.
    """
    lines: list[str] = []
    for line in text.split("\n"):
        if line.startswith("#"):
            continue
        lines.append(line.rstrip())

    result = "\n".join(lines)
    result = _BLANK_LINE_RUN_RE.sub("\n\n", result)
    return result.strip()


def compute_fingerprint(
    rule_id: str,
    original_yaml: str,
    mode: str = "full",
    module_fqcn: str = "",
) -> str:
    """Compute a SHA-256 fingerprint for a violation.

    Args:
        rule_id: Canonical or raw rule ID (will be canonicalized).
        original_yaml: Full node YAML as originally written.
        mode: Fingerprint mode — ``"full"``, ``"rule_module"``, or ``"rule_only"``.
        module_fqcn: Resolved module FQCN (required for ``rule_module`` mode).

    Returns:
        SHA-256 hex digest string.

    Raises:
        ValueError: If mode is not one of the three valid values, or if
            ``mode="rule_module"`` is used without a non-empty ``module_fqcn``.
    """
    canonical_id = canonicalize_rule_id(rule_id)

    if mode == "full":
        normalized = normalize_yaml(original_yaml)
        payload = canonical_id + "\x00" + normalized
    elif mode == "rule_module":
        if not module_fqcn:
            msg = "module_fqcn is required for 'rule_module' mode (empty value collides with 'rule_only')."
            raise ValueError(msg)
        payload = canonical_id + "\x00" + module_fqcn
    elif mode == "rule_only":
        payload = canonical_id + "\x00"
    else:
        msg = f"Invalid fingerprint mode: {mode!r}. Must be 'full', 'rule_module', or 'rule_only'."
        raise ValueError(msg)

    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
