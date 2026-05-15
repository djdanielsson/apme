"""GraphRule L110: debug tasks should not log sensitive variables without no_log.

Detects debug module usage where msg or var contains references to sensitive
variables (password, secret, token, api_key, etc.) without no_log: true set
on the task or an ancestor scope.

Complements L047 (which checks password-like parameter *names*) by catching
sensitive variable *values* being logged via debug.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from apme_engine.engine.content_graph import ContentGraph, ContentNode, NodeType
from apme_engine.engine.models import RuleTag as Tag
from apme_engine.engine.models import Severity, YAMLDict
from apme_engine.validators.native.rules.graph_rule_base import GraphRule, GraphRuleResult

_TASK_TYPES = frozenset({NodeType.TASK, NodeType.HANDLER})

_DEBUG_MODULES = frozenset(
    {
        "debug",
        "ansible.builtin.debug",
        "ansible.legacy.debug",
    }
)

_SENSITIVE_WORDS = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "secret",
        "secrets",
        "token",
        "api_key",
        "apikey",
        "credential",
        "credentials",
        "cred",
        "private_key",
        "ssh_key",
    }
)

_JINJA_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)")
_WORD_BOUNDARY_RE = re.compile(r"(?:^|_)({})(?:_|$)".format("|".join(_SENSITIVE_WORDS)))


def _extract_jinja_vars(text: str) -> set[str]:
    """Extract variable names from Jinja template references.

    Args:
        text: String potentially containing Jinja syntax like {{ var_name }}.

    Returns:
        Set of variable names found in the text.
    """
    if not isinstance(text, str):
        return set()
    return {m.group(1) for m in _JINJA_VAR_RE.finditer(text)}


def _var_looks_sensitive(var_name: str) -> bool:
    """Check if a variable name matches sensitive patterns.

    Uses word-boundary matching to avoid false positives like 'secretary_name'
    (contains 'secret') or 'tokenized_value' (contains 'token'). Matches when
    a sensitive word appears as a complete segment bounded by underscores or
    string start/end.

    Args:
        var_name: Variable name to check.

    Returns:
        True if the variable name contains a sensitive word as a segment.
    """
    lower = var_name.lower()
    return bool(_WORD_BOUNDARY_RE.search(lower))


def _find_sensitive_vars_in_debug(node: ContentNode) -> list[str]:
    """Find sensitive variable references in debug task msg/var.

    Args:
        node: Task node to inspect.

    Returns:
        List of sensitive variable names found.
    """
    sensitive_found: list[str] = []
    mo = node.module_options if isinstance(node.module_options, dict) else {}

    msg = mo.get("msg", "")
    if msg:
        for var_name in _extract_jinja_vars(str(msg)):
            if _var_looks_sensitive(var_name):
                sensitive_found.append(var_name)

    var_param = mo.get("var", "")
    if var_param and isinstance(var_param, str) and _var_looks_sensitive(var_param):
        sensitive_found.append(var_param)

    return sensitive_found


def _no_log_true_in_scope(graph: ContentGraph, node_id: str) -> bool:
    """Return True if any scope in the chain sets no_log to True.

    Args:
        graph: Content graph for the scan.
        node_id: Task or handler node id.

    Returns:
        True when no_log is explicitly true on the node or an ancestor.
    """
    node = graph.get_node(node_id)
    if node is None:
        return False
    chain: list[ContentNode] = [node] + graph.ancestors(node_id)
    return any(scope.no_log is True for scope in chain)


@dataclass
class DebugSensitiveVarsGraphRule(GraphRule):
    """Flag debug tasks logging sensitive variables without no_log protection.

    Detects patterns like:
        - debug: msg="{{ db_password }}"
        - debug: var=api_token

    Without no_log: true on the task or a containing block/play.

    Attributes:
        rule_id: Rule identifier.
        description: Rule description.
        enabled: Whether the rule is enabled.
        name: Rule name.
        version: Rule version.
        severity: Severity level.
        tags: Rule tags.
    """

    rule_id: str = "L110"
    description: str = "Debug tasks should not log sensitive variables without no_log: true"
    enabled: bool = True
    name: str = "DebugSensitiveVars"
    version: str = "v0.0.1"
    severity: Severity = Severity.HIGH
    tags: tuple[str, ...] = (Tag.SYSTEM,)

    def match(self, graph: ContentGraph, node_id: str) -> bool:
        """Match debug tasks with msg or var parameters.

        Args:
            graph: The full ContentGraph.
            node_id: ID of the node to check.

        Returns:
            True when the node is a debug task with msg or var set.
        """
        node = graph.get_node(node_id)
        if node is None:
            return False
        if node.node_type not in _TASK_TYPES:
            return False
        if node.module not in _DEBUG_MODULES:
            return False

        mo = node.module_options if isinstance(node.module_options, dict) else {}
        return bool(mo.get("msg") or mo.get("var"))

    def process(self, graph: ContentGraph, node_id: str) -> GraphRuleResult | None:
        """Check if debug task logs sensitive variables without no_log.

        Args:
            graph: The full ContentGraph.
            node_id: ID of the node to evaluate.

        Returns:
            GraphRuleResult; verdict True when violation is found.
        """
        node = graph.get_node(node_id)
        if node is None:
            return None

        sensitive_vars = _find_sensitive_vars_in_debug(node)
        if not sensitive_vars:
            return GraphRuleResult(
                verdict=False,
                node_id=node_id,
                file=(node.file_path, node.line_start),
            )

        if _no_log_true_in_scope(graph, node_id):
            return GraphRuleResult(
                verdict=False,
                node_id=node_id,
                file=(node.file_path, node.line_start),
            )

        vars_str = ", ".join(sorted(sensitive_vars))
        detail: YAMLDict = {
            "message": f"Debug task logs sensitive variable(s): {vars_str}; set no_log: true",
            "sensitive_vars": list(sensitive_vars),
        }
        return GraphRuleResult(
            verdict=True,
            detail=detail,
            node_id=node_id,
            file=(node.file_path, node.line_start),
        )
