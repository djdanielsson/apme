# Integration tests for L064: Avoid meta: end_play

package apme.rules_test

import data.apme.rules

test_L064_fires_for_end_play if {
	tree := {"nodes": [{"type": "taskcall", "module": "ansible.builtin.meta", "module_options": {"_raw_params": "end_play"}, "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	v := rules.avoid_end_play(tree, node)
	v.rule_id == "L064"
}

test_L064_does_not_fire_for_end_host if {
	tree := {"nodes": [{"type": "taskcall", "module": "ansible.builtin.meta", "module_options": {"_raw_params": "end_host"}, "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	not rules.avoid_end_play(tree, node)
}
