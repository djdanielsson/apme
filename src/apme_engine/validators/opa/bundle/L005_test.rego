# Tests for L005: Community collection module detected

package apme.rules_test

import data.apme.rules

test_L005_fires_for_community_general_fqcn if {
	tree := {"nodes": [{"type": "taskcall", "module": "community.general.ini_file", "original_module": "community.general.ini_file", "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	v := rules.community_module(tree, node)
	v.rule_id == "L005"
	v.resolved_fqcn == "community.general.ini_file"
	contains(v.message, "certified or validated")
}

test_L005_fires_for_community_crypto_fqcn if {
	tree := {"nodes": [{"type": "taskcall", "module": "community.crypto.openssl_privatekey", "original_module": "community.crypto.openssl_privatekey", "line": [5], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	v := rules.community_module(tree, node)
	v.rule_id == "L005"
	v.resolved_fqcn == "community.crypto.openssl_privatekey"
}

test_L005_fires_for_short_name_resolved_to_community if {
	tree := {"nodes": [{"type": "taskcall", "module": "community.general.sysctl", "original_module": "sysctl", "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	v := rules.community_module(tree, node)
	v.rule_id == "L005"
	v.resolved_fqcn == "community.general.sysctl"
	v.original_module == "sysctl"
}

test_L005_does_not_fire_for_builtin_fqcn if {
	tree := {"nodes": [{"type": "taskcall", "module": "ansible.builtin.copy", "original_module": "ansible.builtin.copy", "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	not rules.community_module(tree, node)
}

test_L005_does_not_fire_for_legacy_fqcn if {
	tree := {"nodes": [{"type": "taskcall", "module": "ansible.legacy.copy", "original_module": "ansible.legacy.copy", "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	not rules.community_module(tree, node)
}

test_L005_does_not_fire_for_short_builtin_name if {
	tree := {"nodes": [{"type": "taskcall", "module": "ansible.builtin.apt", "original_module": "apt", "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	not rules.community_module(tree, node)
}

test_L005_does_not_fire_for_unresolved_short_name if {
	tree := {"nodes": [{"type": "taskcall", "module": "yum", "original_module": "yum", "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	not rules.community_module(tree, node)
}

test_L005_does_not_fire_for_cisco_collection if {
	tree := {"nodes": [{"type": "taskcall", "module": "cisco.ios.ios_banner", "original_module": "cisco.ios.ios_banner", "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	not rules.community_module(tree, node)
}

test_L005_does_not_fire_for_ansible_posix if {
	tree := {"nodes": [{"type": "taskcall", "module": "ansible.posix.sysctl", "original_module": "ansible.posix.sysctl", "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	not rules.community_module(tree, node)
}

test_L005_does_not_fire_for_amazon_aws if {
	tree := {"nodes": [{"type": "taskcall", "module": "amazon.aws.ec2_instance", "original_module": "amazon.aws.ec2_instance", "line": [1], "key": "k", "file": "f.yml"}]}
	node := tree.nodes[0]
	not rules.community_module(tree, node)
}
