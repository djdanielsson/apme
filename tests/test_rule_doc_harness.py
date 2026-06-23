"""Unit tests for rule-doc integration harness helpers."""

from __future__ import annotations

import os
import tempfile

from tests.rule_doc_harness import (
    _is_safe_role_name,
    _role_names_from_playbook_yaml,
    _scaffold_inline_roles,
)


class TestRoleNamesFromPlaybookYaml:
    """Tests for _role_names_from_playbook_yaml."""

    def test_string_role_entry(self) -> None:
        """Extracts basename from slash-separated role paths."""
        yaml_content = "- hosts: all\n  roles:\n    - myorg/common\n  tasks: []\n"
        assert _role_names_from_playbook_yaml(yaml_content) == {"common"}

    def test_dict_role_entry(self) -> None:
        """Extracts role from dict entries using role or name keys."""
        yaml_content = "- hosts: all\n  roles:\n    - role: vendor/role\n    - name: other\n  tasks: []\n"
        assert _role_names_from_playbook_yaml(yaml_content) == {"role", "other"}

    def test_invalid_yaml_returns_empty(self) -> None:
        """Malformed YAML yields an empty set without raising."""
        assert _role_names_from_playbook_yaml("hosts: [unclosed") == set()


class TestIsSafeRoleName:
    """Tests for _is_safe_role_name."""

    def test_rejects_parent_directory_segments(self) -> None:
        """Rejects role names that escape roles/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            assert not _is_safe_role_name("..", tmpdir)
            assert not _is_safe_role_name(".", tmpdir)


class TestScaffoldInlineRoles:
    """Tests for _scaffold_inline_roles."""

    def test_creates_role_tree_with_metadata(self) -> None:
        """Scaffolds tasks and meta files for referenced roles."""
        yaml_content = "- hosts: all\n  roles:\n    - common\n  tasks:\n    - debug: msg=hi\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            _scaffold_inline_roles(tmpdir, yaml_content)
            role_root = os.path.join(tmpdir, "roles", "common")
            assert os.path.isfile(os.path.join(role_root, "tasks", "main.yml"))
            assert os.path.isfile(os.path.join(role_root, "meta", "main.yml"))
            assert os.path.isfile(os.path.join(role_root, "meta", "argument_specs.yml"))

    def test_skips_existing_tasks_main(self) -> None:
        """Does not overwrite an existing roles/<name>/tasks/main.yml."""
        yaml_content = "- hosts: all\n  roles:\n    - common\n  tasks: []\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_file = os.path.join(tmpdir, "roles", "common", "tasks", "main.yml")
            os.makedirs(os.path.dirname(tasks_file), exist_ok=True)
            with open(tasks_file, "w") as f:
                f.write("existing\n")
            _scaffold_inline_roles(tmpdir, yaml_content)
            with open(tasks_file) as f:
                assert f.read() == "existing\n"

    def test_parent_directory_role_does_not_escape_roles_tree(self) -> None:
        """roles: - .. must not write outside roles/."""
        yaml_content = "- hosts: all\n  roles:\n    - ..\n  tasks:\n    - debug: msg=hi\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            _scaffold_inline_roles(tmpdir, yaml_content)
            assert not os.path.exists(os.path.join(tmpdir, "tasks", "main.yml"))
            assert not os.path.exists(os.path.join(tmpdir, "roles"))
