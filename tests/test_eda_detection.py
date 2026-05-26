"""Tests for EDA rulebook detection to prevent L095 false positives."""

from __future__ import annotations

from pathlib import Path

from apme_engine.engine.awx_utils import could_be_eda_rulebook, could_be_playbook
from apme_engine.engine.finder import could_be_playbook_detail
from apme_engine.engine.models import YAMLValue

# ---------------------------------------------------------------------------
# EDA Rulebook Detection
# ---------------------------------------------------------------------------


class TestEdaRulebookDetection:
    """Tests for EDA rulebook detection functions."""

    def test_could_be_eda_rulebook_with_sources_and_rules(self, tmp_path: Path) -> None:
        """Verify file with sources and rules is detected as EDA rulebook.

        Args:
            tmp_path: Pytest fixture providing temporary directory.
        """
        content = """\
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
        rulebook.write_text(content)
        assert could_be_eda_rulebook(str(rulebook)) is True

    def test_could_be_eda_rulebook_path_pattern_rulebooks(self, tmp_path: Path) -> None:
        """Verify file in rulebooks/ directory is detected as EDA.

        Args:
            tmp_path: Pytest fixture providing temporary directory.
        """
        rulebooks_dir = tmp_path / "rulebooks"
        rulebooks_dir.mkdir()
        content = "---\n- name: Test\n  hosts: localhost\n"
        rulebook = rulebooks_dir / "test.yml"
        rulebook.write_text(content)
        assert could_be_eda_rulebook(str(rulebook)) is True

    def test_could_be_eda_rulebook_path_pattern_extensions_eda(self, tmp_path: Path) -> None:
        """Verify file in extensions/eda/ directory is detected as EDA.

        Args:
            tmp_path: Pytest fixture providing temporary directory.
        """
        eda_dir = tmp_path / "extensions" / "eda" / "rulebooks"
        eda_dir.mkdir(parents=True)
        content = "---\n- name: Test\n  hosts: localhost\n"
        rulebook = eda_dir / "test.yml"
        rulebook.write_text(content)
        assert could_be_eda_rulebook(str(rulebook)) is True

    def test_playbook_not_detected_as_eda_rulebook(self, tmp_path: Path) -> None:
        """Verify standard playbook is not detected as EDA rulebook.

        Args:
            tmp_path: Pytest fixture providing temporary directory.
        """
        content = """\
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
        playbook.write_text(content)
        assert could_be_eda_rulebook(str(playbook)) is False

    def test_non_yaml_file_not_eda_rulebook(self, tmp_path: Path) -> None:
        """Verify non-YAML files are not detected as EDA rulebooks.

        Args:
            tmp_path: Pytest fixture providing temporary directory.
        """
        readme = tmp_path / "README.md"
        readme.write_text("# Rulebook documentation")
        assert could_be_eda_rulebook(str(readme)) is False


# ---------------------------------------------------------------------------
# Playbook Detection Excludes EDA
# ---------------------------------------------------------------------------


class TestPlaybookDetectionExcludesEda:
    """Tests that playbook detection excludes EDA rulebooks."""

    def test_could_be_playbook_excludes_eda_rulebook(self, tmp_path: Path) -> None:
        """Verify EDA rulebook is not detected as playbook.

        Args:
            tmp_path: Pytest fixture providing temporary directory.
        """
        content = """\
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
        debug:
"""
        rulebook = tmp_path / "rulebook.yml"
        rulebook.write_text(content)
        # EDA rulebook should not be considered a playbook
        assert could_be_playbook(str(rulebook)) is False

    def test_could_be_playbook_includes_standard_playbook(self, tmp_path: Path) -> None:
        """Verify standard playbook is still detected correctly.

        Args:
            tmp_path: Pytest fixture providing temporary directory.
        """
        content = """\
---
- name: Install packages
  hosts: all
  tasks:
    - name: Install nginx
      ansible.builtin.package:
        name: nginx
"""
        playbook = tmp_path / "site.yml"
        playbook.write_text(content)
        assert could_be_playbook(str(playbook)) is True


# ---------------------------------------------------------------------------
# Playbook Detail Detection Excludes EDA
# ---------------------------------------------------------------------------


class TestPlaybookDetailExcludesEda:
    """Tests that could_be_playbook_detail excludes EDA content."""

    def test_eda_rulebook_not_playbook_detail(self) -> None:
        """Verify EDA content with sources/rules is not detected as playbook."""
        body = """\
- name: Hello Events
  hosts: localhost
  sources:
    - ansible.eda.range:
        limit: 5
  rules:
    - name: Say Hello
      condition: event.i == 1
"""
        data: YAMLValue = [
            {
                "name": "Hello Events",
                "hosts": "localhost",
                "sources": [{"ansible.eda.range": {"limit": 5}}],
                "rules": [{"name": "Say Hello", "condition": "event.i == 1"}],
            }
        ]
        assert could_be_playbook_detail(body=body, data=data) is False

    def test_eda_rulebook_with_only_sources(self) -> None:
        """Verify content with sources key is not detected as playbook."""
        body = """\
- name: Event Source
  hosts: localhost
  sources:
    - ansible.eda.webhook:
        port: 5000
"""
        data: YAMLValue = [
            {
                "name": "Event Source",
                "hosts": "localhost",
                "sources": [{"ansible.eda.webhook": {"port": 5000}}],
            }
        ]
        assert could_be_playbook_detail(body=body, data=data) is False

    def test_eda_rulebook_with_only_rules(self) -> None:
        """Verify content with rules key is not detected as playbook."""
        body = """\
- name: Rules Only
  hosts: localhost
  rules:
    - name: Test
      condition: "true"
"""
        data: YAMLValue = [
            {
                "name": "Rules Only",
                "hosts": "localhost",
                "rules": [{"name": "Test", "condition": "true"}],
            }
        ]
        assert could_be_playbook_detail(body=body, data=data) is False

    def test_standard_playbook_still_detected(self) -> None:
        """Verify standard playbook with tasks is still detected."""
        body = """\
- name: Install packages
  hosts: all
  tasks:
    - name: Install nginx
      ansible.builtin.package:
        name: nginx
"""
        data: YAMLValue = [
            {
                "name": "Install packages",
                "hosts": "all",
                "tasks": [{"name": "Install nginx", "ansible.builtin.package": {"name": "nginx"}}],
            }
        ]
        assert could_be_playbook_detail(body=body, data=data) is True

    def test_import_playbook_still_detected(self) -> None:
        """Verify import_playbook directive is still detected."""
        body = "- import_playbook: other.yml\n"
        data: YAMLValue = [{"import_playbook": "other.yml"}]
        assert could_be_playbook_detail(body=body, data=data) is True
