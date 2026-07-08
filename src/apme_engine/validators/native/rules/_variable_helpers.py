"""Shared Jinja variable-extraction and sensitivity helpers for graph rules.

Root-level Jinja reference extraction (``collect_strings``, ``extract_jinja_refs``,
``extract_bare_refs``) is used by L039 and R402.  L110 keeps a local
path-aware extractor (``_extract_jinja_vars``) because it must match dotted
paths such as ``vault.db_password``; the shared extractors intentionally return
root identifiers only.

``no_log_true_in_scope`` is shared by L110 and R404.  Sensitivity name/value
checks (``var_looks_sensitive``, ``value_looks_sensitive``) live in
``apme_engine.engine.sensitivity`` and are imported directly by L110/R404.
"""

from __future__ import annotations

import re

from apme_engine.graph.content_graph import ContentGraph, NodeType

TASK_TYPES: frozenset[NodeType] = frozenset({NodeType.TASK, NodeType.HANDLER})

_JINJA_VAR_RE = re.compile(r"\{\{(.*?)\}\}")
_BARE_IDENT_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b")

_JINJA_BUILTINS: frozenset[str] = frozenset(
    {
        "and",
        "or",
        "not",
        "in",
        "is",
        "if",
        "else",
        "elif",
        "for",
        "import",
        "as",
        "with",
        "bool",
        "true",
        "false",
        "True",
        "False",
        "none",
        "None",
        "null",
        "Null",
        "int",
        "float",
        "string",
        "list",
        "dict",
        "length",
        "lower",
        "upper",
        "default",
        "defined",
        "undefined",
        "sameas",
        "mapping",
        "iterable",
        "sequence",
        "number",
        "match",
        "search",
        "regex",
        "select",
        "reject",
        "map",
        "sort",
        "join",
        "first",
        "last",
        "min",
        "max",
        "abs",
        "round",
        "trim",
        "replace",
        "split",
        "unique",
        "flatten",
        "combine",
        "mandatory",
        "ternary",
        "from_json",
        "from_yaml",
        "to_json",
        "to_yaml",
        "to_nice_json",
        "to_nice_yaml",
        "to_datetime",
        "to_uuid",
        "b64encode",
        "b64decode",
        "hash",
        "type_debug",
        "ipaddr",
        "ipv4",
        "ipv6",
        "basename",
        "dirname",
        "realpath",
        "relpath",
        "expanduser",
        "expandvars",
        "fileglob",
        "splitext",
        "win_basename",
        "win_dirname",
        "win_splitdrive",
        "regex_replace",
        "regex_search",
        "regex_findall",
        "regex_escape",
        "password_hash",
        "comment",
        "subelements",
        "product",
        "zip",
        "zip_longest",
        "json_query",
        "items2dict",
        "dict2items",
        "groupby",
        "selectattr",
        "rejectattr",
        "extract",
        "symmetric_difference",
        "difference",
        "intersect",
        "union",
        "community",
        "succeeded",
        "failed",
        "changed",
        "skipped",
        "success",
        "failure",
        "unreachable",
        "human_readable",
        "human_to_bytes",
        "shuffle",
        "log",
        "pow",
        "root",
        "urlsplit",
        "urlencode",
        "ansible_native",
        "checksum",
        "strftime",
        "wordcount",
        "xmlattr",
    }
)

_QUOTED_STRING_RE = re.compile(r"""(?:'[^']*'|"[^"]*")""")
_DOTTED_ATTR_RE = re.compile(r"\.([a-zA-Z_][a-zA-Z0-9_]*)")
_PIPE_FILTER_RE = re.compile(r"\|\s*([a-zA-Z_][a-zA-Z0-9_]*)")


def extract_jinja_refs(texts: list[str]) -> set[str]:
    """Extract simple variable identifiers from Jinja expressions.

    Only extracts the root identifier (before ``.`` or ``|``).  Dotted
    access and filters are stripped.

    Args:
        texts: Strings that may contain ``{{ ... }}`` expressions.

    Returns:
        Set of root variable names referenced in the Jinja expressions.
    """
    refs: set[str] = set()
    for text in texts:
        for m in _JINJA_VAR_RE.findall(text):
            cleaned = m.strip().split("|")[0].split(".")[0].split("[")[0].strip()
            if cleaned and cleaned.isidentifier():
                refs.add(cleaned)
    return refs


def extract_bare_refs(texts: list[str]) -> set[str]:
    """Extract identifiers from bare Jinja expressions (no ``{{ }}``).

    Used for ``when``, ``changed_when``, ``failed_when`` which are
    implicitly Jinja — Ansible evaluates them as expressions without
    requiring ``{{ }}`` wrappers.

    Strips quoted strings, dotted attribute names, and Jinja filter names
    (identifiers following ``|``) before extraction so that ``'RedHat'``,
    ``.rc``, and ``| to_datetime`` are not treated as variables.

    Args:
        texts: Bare expression strings.

    Returns:
        Set of identifier names minus Jinja builtins/operators.
    """
    refs: set[str] = set()
    for text in texts:
        stripped = _QUOTED_STRING_RE.sub("", text)
        dotted_attrs = {m.group(1) for m in _DOTTED_ATTR_RE.finditer(stripped)}
        pipe_filters = {m.group(1) for m in _PIPE_FILTER_RE.finditer(stripped)}
        for ident in _BARE_IDENT_RE.findall(stripped):
            if (
                ident not in _JINJA_BUILTINS
                and ident not in dotted_attrs
                and ident not in pipe_filters
                and not ident[0].isdigit()
            ):
                refs.add(ident)
    return refs


def collect_strings(node: object) -> tuple[list[str], list[str]]:
    """Gather string fields from a node, split by expression type.

    Args:
        node: A ContentNode (duck-typed to avoid circular import in tests).

    Returns:
        Tuple of (template_strings, bare_expression_strings).
        Template strings may contain ``{{ }}``; bare expression strings
        are implicitly Jinja (``when``, ``changed_when``, ``failed_when``).
    """
    templates: list[str] = []
    bare: list[str] = []

    when_expr = getattr(node, "when_expr", None)
    if when_expr:
        if isinstance(when_expr, list):
            bare.extend(str(w) for w in when_expr)
        else:
            bare.append(str(when_expr))

    name = getattr(node, "name", None)
    if isinstance(name, str):
        templates.append(name)

    mo = getattr(node, "module_options", None)
    if isinstance(mo, dict):
        _collect_dict_strings(mo, templates)

    for attr in ("changed_when", "failed_when"):
        val = getattr(node, attr, None)
        if isinstance(val, str):
            bare.append(val)
        elif isinstance(val, list):
            bare.extend(str(v) for v in val)

    env = getattr(node, "environment", None)
    if isinstance(env, dict):
        _collect_dict_strings(env, templates)

    loop = getattr(node, "loop", None)
    if isinstance(loop, str):
        templates.append(loop)
    elif isinstance(loop, list):
        templates.extend(str(item) for item in loop)

    variables = getattr(node, "variables", None)
    if isinstance(variables, dict):
        _collect_dict_strings(variables, templates)

    return templates, bare


def _collect_dict_strings(d: dict[str, object], out: list[str]) -> None:
    """Recursively collect string values from a nested dict.

    Args:
        d: Dictionary to traverse.
        out: Accumulator list for discovered strings.
    """
    for v in d.values():
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, dict):
            _collect_dict_strings(v, out)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    out.append(item)
                elif isinstance(item, dict):
                    _collect_dict_strings(item, out)


def no_log_true_in_scope(graph: ContentGraph, node_id: str) -> bool:
    """Return True if no_log is effectively True at this node.

    Ansible allows more-specific scopes to override inherited keywords. A task
    with no_log: false can opt out of a block/play with no_log: true. We walk
    the chain from the task outward (closest to farthest) and return on the
    first explicit no_log setting.

    Args:
        graph: ContentGraph for the scan.
        node_id: Task or handler node id.

    Returns:
        True when no_log is effectively true at this scope.
    """
    node = graph.get_node(node_id)
    if node is None:
        return False
    if node.no_log is False:
        return False
    if node.no_log is True:
        return True
    for ancestor in graph.ancestors(node_id):
        if ancestor.no_log is False:
            return False
        if ancestor.no_log is True:
            return True
    return False
