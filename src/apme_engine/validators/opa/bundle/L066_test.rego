# Integration tests for L066: Do not mix roles: and tasks:

package apme.rules_test

import data.apme.rules

test_L066_fires_when_roles_and_tasks_mixed if {
	tree := {"nodes": [{"type": "playcall", "options": {"roles": ["common"], "tasks": [{"name": "foo"}]}, "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	v := rules.mixed_roles_tasks(tree, node)
	v.rule_id == "L066"
}

test_L066_does_not_fire_for_roles_only if {
	tree := {"nodes": [{"type": "playcall", "options": {"roles": ["common"]}, "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	not rules.mixed_roles_tasks(tree, node)
}
