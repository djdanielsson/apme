# Integration tests for L072: Set backup on template/copy

package apme.rules_test

import data.apme.rules

test_L072_fires_when_no_backup if {
	tree := {"nodes": [{"type": "taskcall", "module": "ansible.builtin.template", "module_options": {"src": "a.j2", "dest": "/etc/a"}, "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	v := rules.missing_backup(tree, node)
	v.rule_id == "L072"
}

test_L072_does_not_fire_when_backup_set if {
	tree := {"nodes": [{"type": "taskcall", "module": "ansible.builtin.template", "module_options": {"src": "a.j2", "dest": "/etc/a", "backup": true}, "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	not rules.missing_backup(tree, node)
}
