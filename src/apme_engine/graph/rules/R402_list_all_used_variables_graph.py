"""GraphRule R402: report all variables used at end of a play sequence.

Informational/audit rule (severity INFO) that enumerates every variable
reference found across all tasks within a play.  Fires once per PLAY
node and walks all task/handler descendants to collect Jinja variable
references, then resolves their provenance.

This rule is disabled by default — enable by including ``R402`` in the
rule_id_list when loading rules.
"""

from dataclasses import dataclass
from typing import cast

from apme_engine.engine.sensitivity import var_looks_sensitive
from apme_engine.graph.content_graph import ContentGraph, EdgeType, NodeType
from apme_engine.graph.rule_base import GraphRule, GraphRuleResult
from apme_engine.graph.types import RuleScope, Severity, YAMLDict, YAMLValue
from apme_engine.graph.types import RuleTag as Tag
from apme_engine.graph.variable_provenance import (
    ProvenanceSource,
    VariableProvenance,
    VariableProvenanceResolver,
)
from apme_engine.validators.native.rules._variable_helpers import (
    TASK_TYPES,
    collect_strings,
    extract_bare_refs,
    extract_jinja_refs,
    no_log_true_in_scope,
)

_REDACTED = "[REDACTED]"
_MAX_VARIABLES_USED = 500


def _play_task_descendant_ids(graph: ContentGraph, play_id: str) -> set[str]:
    """Return task/handler nodes under a play via CONTAINS and INCLUDE edges.

    Traversal intentionally excludes DATA_FLOW and NOTIFY edges so register
    consumers in other plays are not pulled into a play-level audit report.

    Args:
        graph: ContentGraph under scan.
        play_id: Play node whose task sequence is enumerated.

    Returns:
        Task and handler node IDs reachable from the play.
    """
    result: set[str] = set()
    seen: set[str] = set()
    stack = [play_id]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        node = graph.get_node(current)
        if node is not None and node.node_type in TASK_TYPES:
            result.add(current)
        for target, _attrs in graph.edges_from(current, EdgeType.CONTAINS):
            stack.append(target)
        for edge_type in (EdgeType.INCLUDE, EdgeType.IMPORT):
            for target, _attrs in graph.edges_from(current, edge_type):
                stack.append(target)
    return result


@dataclass
class ListAllUsedVariablesGraphRule(GraphRule):
    """Aggregate all variable references across a play's task sequence.

    Walks every task/handler descendant, extracts Jinja variable references
    from module_options, when_expr, name, etc., and reports the union with
    provenance information.

    Attributes:
        rule_id: Rule identifier.
        description: Rule description.
        enabled: Whether the rule is enabled.
        name: Rule name.
        version: Rule version.
        severity: Severity level.
        tags: Rule tags.
        scope: Structural scope (play-level).
    """

    rule_id: str = "R402"
    description: str = "Report variables used at end of sequence"
    enabled: bool = False
    name: str = "ListAllUsedVariables"
    version: str = "v0.0.1"
    severity: Severity = Severity.INFO
    tags: tuple[str, ...] = (Tag.DEBUG,)
    scope: str = RuleScope.PLAY

    def match(self, graph: ContentGraph, node_id: str) -> bool:
        """Match only PLAY nodes so the rule fires once per play.

        Args:
            graph: The full ContentGraph.
            node_id: ID of the node to check.

        Returns:
            True for play-level nodes.
        """
        node = graph.get_node(node_id)
        if node is None:
            return False
        return node.node_type == NodeType.PLAY

    def process(self, graph: ContentGraph, node_id: str) -> GraphRuleResult | None:
        """Walk all task descendants and collect Jinja variable references with provenance.

        Extracts actual Jinja ``{{ }}`` and bare expression references
        (when, changed_when, etc.) from each task, then resolves provenance
        per task so shadowed names keep task-local sources.

        Args:
            graph: The full ContentGraph.
            node_id: ID of the play node.

        Returns:
            GraphRuleResult with ``variables_used`` list, or None if node missing.
        """
        node = graph.get_node(node_id)
        if node is None:
            return None

        resolver = VariableProvenanceResolver(graph)
        all_refs: set[str] = set()
        task_ids: list[str] = []
        refs_by_task: dict[str, set[str]] = {}
        resolved_by_task: dict[str, dict[str, VariableProvenance]] = {}
        task_desc_ids = list(_play_task_descendant_ids(graph, node_id))

        def _task_sort_key(desc_id: str) -> tuple[str, int, str]:
            desc_node = graph.get_node(desc_id)
            if desc_node is None:
                return ("", 0, desc_id)
            return (desc_node.file_path, desc_node.line_start, desc_id)

        for desc_id in sorted(task_desc_ids, key=_task_sort_key):
            desc = graph.get_node(desc_id)
            if desc is None:
                continue
            task_ids.append(desc_id)
            templates, bare = collect_strings(desc)
            task_refs = extract_jinja_refs(templates) | extract_bare_refs(bare)
            refs_by_task[desc_id] = task_refs
            all_refs |= task_refs

        if not all_refs:
            return GraphRuleResult(
                verdict=False,
                node_id=node_id,
                file=(node.file_path, node.line_start),
            )

        var_list: list[YAMLValue] = []
        for tid in task_ids:
            task_refs = refs_by_task[tid]
            if not task_refs:
                continue
            if tid not in resolved_by_task:
                resolved_by_task[tid] = resolver.resolve_variables(tid)
            resolved = resolved_by_task[tid]
            task_node = graph.get_node(tid)
            task_path = task_node.identity.path if task_node else tid
            task_no_log = no_log_true_in_scope(graph, tid)
            for ref in sorted(task_refs):
                prov = resolved.get(ref)
                source = prov.source.value if prov else ProvenanceSource.EXTERNAL.value
                var_list.append(
                    cast(
                        YAMLValue,
                        {
                            "name": _REDACTED if var_looks_sensitive(ref) or task_no_log else ref,
                            "source": source,
                            "task": task_path,
                        },
                    )
                )

        total_refs = len(var_list)
        truncated = total_refs > _MAX_VARIABLES_USED
        if truncated:
            var_list = var_list[:_MAX_VARIABLES_USED]

        detail: YAMLDict = {
            "message": (
                f"Play references {total_refs} variable use(s) across tasks" + (" (truncated)" if truncated else "")
            ),
            "variables_used": cast(YAMLValue, var_list),
        }
        return GraphRuleResult(
            verdict=True,
            detail=detail,
            node_id=node_id,
            file=(node.file_path, node.line_start),
        )
