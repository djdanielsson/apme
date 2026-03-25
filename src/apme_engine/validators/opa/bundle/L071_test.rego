# Integration tests for L071: Template over copy

package apme.rules_test

import data.apme.rules

test_L071_fires_when_copy_content_has_jinja if {
	tree := {"nodes": [{"type": "taskcall", "module": "ansible.builtin.copy", "module_options": {"content": "val={{ foo }}", "dest": "/etc/foo"}, "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	v := rules.use_template_over_copy(tree, node)
	v.rule_id == "L071"
}

test_L071_does_not_fire_for_static_content if {
	tree := {"nodes": [{"type": "taskcall", "module": "ansible.builtin.copy", "module_options": {"content": "static text", "dest": "/etc/foo"}, "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	not rules.use_template_over_copy(tree, node)
}
