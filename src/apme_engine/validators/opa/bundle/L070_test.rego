# Integration tests for L070: Jinja position in task name

package apme.rules_test

import data.apme.rules

test_L070_fires_when_jinja_in_middle if {
	tree := {"nodes": [{"type": "taskcall", "name": "Install {{ pkg }} on server", "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	v := rules.jinja_name_position(tree, node)
	v.rule_id == "L070"
}

test_L070_does_not_fire_when_jinja_at_end if {
	tree := {"nodes": [{"type": "taskcall", "name": "Install package {{ pkg }}", "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	not rules.jinja_name_position(tree, node)
}
