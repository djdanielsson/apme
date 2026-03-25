# Integration tests for L069: Batch package names

package apme.rules_test

import data.apme.rules

test_L069_fires_when_package_loop_with_item if {
	tree := {"nodes": [{"type": "taskcall", "module": "ansible.builtin.apt", "module_options": {"name": "{{ item }}"}, "options": {"loop": ["nginx", "curl"]}, "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	v := rules.package_loop(tree, node)
	v.rule_id == "L069"
}

test_L069_does_not_fire_for_list_name if {
	tree := {"nodes": [{"type": "taskcall", "module": "ansible.builtin.apt", "module_options": {"name": ["nginx", "curl"]}, "options": {}, "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	not rules.package_loop(tree, node)
}
