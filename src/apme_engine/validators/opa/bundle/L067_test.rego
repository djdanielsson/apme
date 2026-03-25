# Integration tests for L067: Set verbosity on debug tasks

package apme.rules_test

import data.apme.rules

test_L067_fires_when_debug_has_no_verbosity if {
	tree := {"nodes": [{"type": "taskcall", "module": "ansible.builtin.debug", "module_options": {"msg": "hello"}, "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	v := rules.debug_verbosity(tree, node)
	v.rule_id == "L067"
}

test_L067_does_not_fire_when_verbosity_set if {
	tree := {"nodes": [{"type": "taskcall", "module": "ansible.builtin.debug", "module_options": {"msg": "hello", "verbosity": 2}, "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	not rules.debug_verbosity(tree, node)
}
