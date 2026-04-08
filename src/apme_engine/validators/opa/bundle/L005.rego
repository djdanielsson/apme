# L005: Community collection module detected
#
# Flags tasks using modules from community.* collections.  Community
# collections are not covered by Red Hat support — use certified or
# validated collections instead where available.
#
# The rule checks both the resolved module name and the original YAML
# module name so it catches short aliases that the engine resolved to
# a community.* FQCN as well as explicit community.* FQCNs.

package apme.rules

import future.keywords.if
import future.keywords.in

violations contains v if {
	some tree in input.hierarchy
	some node in tree.nodes
	v := community_module(tree, node)
}

_is_fqcn(s) if {
	contains(s, ".")
	not contains(s, "/")
	not contains(s, " ")
	not contains(s, "#")
	not startswith(s, "taskfile")
}

# Resolved FQCN starts with community.* — flag it.
community_module(tree, node) := v if {
	node.type == "taskcall"
	om := object.get(node, "original_module", node.module)
	om != ""
	count(node.line) > 0
	resolved := node.module
	_is_fqcn(resolved)
	startswith(resolved, "community.")
	v := {
		"rule_id": "L005",
		"severity": "low",
		"message": sprintf("Community collection module: %s; consider a certified or validated collection", [resolved]),
		"file": node.file,
		"line": node.line[0],
		"path": node.key,
		"original_module": om,
		"resolved_fqcn": resolved,
		"scope": "task",
	}
}

# Original YAML explicitly uses a community.* FQCN (even when the
# engine's resolved name differs or is absent).
community_module(tree, node) := v if {
	node.type == "taskcall"
	om := object.get(node, "original_module", node.module)
	om != ""
	count(node.line) > 0
	startswith(om, "community.")
	not _is_fqcn(node.module)
	v := {
		"rule_id": "L005",
		"severity": "low",
		"message": sprintf("Community collection module: %s; consider a certified or validated collection", [om]),
		"file": node.file,
		"line": node.line[0],
		"path": node.key,
		"original_module": om,
		"scope": "task",
	}
}
