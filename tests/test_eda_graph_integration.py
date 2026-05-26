"""Integration tests for EDA rulebook handling in the content graph."""

from __future__ import annotations

from pathlib import Path

from apme_engine.engine.awx_utils import could_be_eda_rulebook, could_be_playbook
from apme_engine.engine.content_graph import NodeType


class TestEdaGraphIntegration:
    """Tests that EDA rulebooks are handled correctly by the graph system."""

    def test_eda_rulebook_excluded_from_playbook_detection(self, tmp_path: Path) -> None:
        """Verify EDA rulebook files are not detected as playbooks.

        EDA rulebooks have 'sources' and 'rules' keys which are not valid
        playbook keywords. These files should be excluded from playbook
        detection to prevent L095 false positives.

        Args:
            tmp_path: Pytest fixture providing temporary directory.
        """
        # Create an EDA rulebook
        rulebook_content = """\
---
- name: Hello Events
  hosts: localhost
  sources:
    - ansible.eda.range:
        limit: 5
  rules:
    - name: Say Hello
      condition: event.i == 1
      action:
        run_playbook:
          name: hello.yml
"""
        rulebook = tmp_path / "rulebook.yml"
        rulebook.write_text(rulebook_content)

        # EDA rulebook should be detected as EDA
        assert could_be_eda_rulebook(str(rulebook)) is True

        # But should NOT be detected as a playbook
        assert could_be_playbook(str(rulebook)) is False

    def test_standard_playbook_still_detected(self, tmp_path: Path) -> None:
        """Verify standard playbooks are still detected correctly.

        Args:
            tmp_path: Pytest fixture providing temporary directory.
        """
        # Create a standard playbook
        playbook_content = """\
---
- name: Install packages
  hosts: all
  tasks:
    - name: Install nginx
      ansible.builtin.package:
        name: nginx
        state: present
"""
        playbook = tmp_path / "site.yml"
        playbook.write_text(playbook_content)

        # Standard playbook should NOT be detected as EDA
        assert could_be_eda_rulebook(str(playbook)) is False

        # And should still be detected as a playbook
        assert could_be_playbook(str(playbook)) is True

    def test_mixed_content_directory(self, tmp_path: Path) -> None:
        """Verify directories with both playbooks and rulebooks work correctly.

        Args:
            tmp_path: Pytest fixture providing temporary directory.
        """
        # Create a standard playbook
        playbook_content = """\
---
- name: Deploy app
  hosts: web
  tasks:
    - name: Copy files
      ansible.builtin.copy:
        src: app/
        dest: /opt/app/
"""
        playbook = tmp_path / "deploy.yml"
        playbook.write_text(playbook_content)

        # Create an EDA rulebook in rulebooks/ subdirectory
        rulebooks_dir = tmp_path / "rulebooks"
        rulebooks_dir.mkdir()
        rulebook_content = """\
---
- name: Monitor Events
  hosts: localhost
  sources:
    - ansible.eda.webhook:
        port: 5000
  rules:
    - name: Handle webhook
      condition: event.payload is defined
      action:
        run_playbook:
          name: ../deploy.yml
"""
        rulebook = rulebooks_dir / "monitor.yml"
        rulebook.write_text(rulebook_content)

        # Playbook should be detected as playbook
        assert could_be_playbook(str(playbook)) is True
        assert could_be_eda_rulebook(str(playbook)) is False

        # Rulebook should be detected as EDA, not playbook
        assert could_be_eda_rulebook(str(rulebook)) is True
        assert could_be_playbook(str(rulebook)) is False


class TestNodeTypeEnumIncludes:
    """Tests that NodeType enum includes EDA types."""

    def test_rulebook_node_type_exists(self) -> None:
        """Verify RULEBOOK node type is defined."""
        assert hasattr(NodeType, "RULEBOOK")
        assert NodeType.RULEBOOK.value == "rulebook"

    def test_ruleset_node_type_exists(self) -> None:
        """Verify RULESET node type is defined."""
        assert hasattr(NodeType, "RULESET")
        assert NodeType.RULESET.value == "ruleset"
