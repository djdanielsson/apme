# Integration tests for L065: No Jinja in play names

package apme.rules_test

import data.apme.rules

test_L065_fires_when_play_name_has_jinja if {
	tree := {"nodes": [{"type": "playcall", "name": "Deploy {{ app }}", "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	v := rules.no_jinja_play_name(tree, node)
	v.rule_id == "L065"
}

test_L065_does_not_fire_for_static_play_name if {
	tree := {"nodes": [{"type": "playcall", "name": "Deploy application", "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	not rules.no_jinja_play_name(tree, node)
}
