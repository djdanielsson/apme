# Integration tests for L068: Avoid lineinfile

package apme.rules_test

import data.apme.rules

test_L068_fires_for_lineinfile if {
	tree := {"nodes": [{"type": "taskcall", "module": "ansible.builtin.lineinfile", "module_options": {"path": "/etc/foo"}, "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	v := rules.avoid_lineinfile(tree, node)
	v.rule_id == "L068"
}

test_L068_does_not_fire_for_template if {
	tree := {"nodes": [{"type": "taskcall", "module": "ansible.builtin.template", "module_options": {"src": "foo.j2"}, "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	not rules.avoid_lineinfile(tree, node)
}
