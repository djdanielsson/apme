# Integration tests for L063: Block should have a name

package apme.rules_test

import data.apme.rules

test_L063_fires_when_block_has_no_name if {
	tree := {"nodes": [{"type": "blockcall", "name": null, "line": [3], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	v := rules.block_has_no_name(tree, node)
	v.rule_id == "L063"
}

test_L063_does_not_fire_when_block_has_name if {
	tree := {"nodes": [{"type": "blockcall", "name": "Install block", "line": [3], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	not rules.block_has_no_name(tree, node)
}
