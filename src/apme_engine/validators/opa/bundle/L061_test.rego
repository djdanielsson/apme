# Integration tests for L061: Use true/false for booleans

package apme.rules_test

import data.apme.rules

test_L061_fires_when_yes_in_options if {
	tree := {"nodes": [{"type": "taskcall", "options": {"become": "yes"}, "module_options": {}, "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	v := rules.truthy_boolean(tree, node)
	v.rule_id == "L061"
}

test_L061_does_not_fire_for_true if {
	tree := {"nodes": [{"type": "taskcall", "options": {"become": true}, "module_options": {}, "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	not rules.truthy_boolean(tree, node)
}
