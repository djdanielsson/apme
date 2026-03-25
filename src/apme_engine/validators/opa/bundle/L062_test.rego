# Integration tests for L062: YAML-style module arguments

package apme.rules_test

import data.apme.rules

test_L062_fires_when_free_form_with_equals if {
	tree := {"nodes": [{"type": "taskcall", "module": "ansible.builtin.apt", "module_options": {"_raw_params": "name=nginx state=present"}, "options": {}, "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	v := rules.yaml_module_args(tree, node)
	v.rule_id == "L062"
}

test_L062_does_not_fire_for_yaml_style if {
	tree := {"nodes": [{"type": "taskcall", "module": "ansible.builtin.apt", "module_options": {"name": "nginx", "state": "present"}, "options": {}, "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	not rules.yaml_module_args(tree, node)
}

test_L062_does_not_fire_for_shell if {
	tree := {"nodes": [{"type": "taskcall", "module": "ansible.builtin.shell", "module_options": {"_raw_params": "echo foo=bar"}, "options": {}, "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	not rules.yaml_module_args(tree, node)
}
