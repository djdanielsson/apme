"""Tests for EDA rulebook detection to prevent L095 false positives."""

from __future__ import annotations

from pathlib import Path

from apme_engine.engine.awx_utils import (
    could_be_eda_rulebook,
    could_be_playbook,
    is_eda_rulebook_path,
)
from apme_engine.engine.finder import (
    could_be_eda_rulebook_detail,
    could_be_playbook_detail,
    could_be_taskfile,
    label_yml_file,
)
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

    def test_playbook_with_stray_rules_key_not_eda(self, tmp_path: Path) -> None:
        """Verify playbooks with non-EDA ``rules`` entries remain playbooks for L095.

        Args:
            tmp_path: Pytest fixture providing temporary directory.
        """
        content = """\
---
- name: Bad play
  hosts: all
  rules:
    - name: Debug task
      ansible.builtin.debug:
        msg: hello
"""
        playbook = tmp_path / "bad_play.yml"
        playbook.write_text(content)
        assert could_be_eda_rulebook(str(playbook)) is False
        assert could_be_playbook(str(playbook)) is True

    def test_playbook_with_stray_sources_before_tasks_not_eda(self, tmp_path: Path) -> None:
        """Verify a stray play-level ``sources`` key does not suppress L095.

        Args:
            tmp_path: Pytest fixture providing temporary directory.
        """
        content = """\
---
- name: Bad play
  hosts: all
  sources:
    - not-an-eda-source
  tasks:
    - name: Debug task
      ansible.builtin.debug:
        msg: hello
"""
        playbook = tmp_path / "bad_sources_play.yml"
        playbook.write_text(content)
        assert could_be_eda_rulebook(str(playbook)) is False
        assert could_be_playbook(str(playbook)) is True

    def test_is_eda_rulebook_path_relative_paths(self) -> None:
        """Verify path detection works without leading directory separators."""
        assert is_eda_rulebook_path("rulebooks/foo.yml") is True
        assert is_eda_rulebook_path("extensions/eda/rulebooks/foo.yml") is True
        assert is_eda_rulebook_path("/project/rulebooks/foo.yml") is True
        assert is_eda_rulebook_path("playbooks/site.yml") is False

    def test_could_be_eda_rulebook_relative_path_without_sources(self, tmp_path: Path) -> None:
        """Verify path-only EDA files are detected when rulebooks/ has no sources/rules keys.

        Args:
            tmp_path: Pytest fixture providing temporary directory.
        """
        rulebooks_dir = tmp_path / "rulebooks"
        rulebooks_dir.mkdir()
        rulebook = rulebooks_dir / "minimal.yml"
        rulebook.write_text("---\n- name: Minimal\n  hosts: localhost\n")
        # Relative path from project root (no leading slash in segment check)
        relative = f"rulebooks/{rulebook.name}"
        assert is_eda_rulebook_path(relative) is True
        assert could_be_eda_rulebook(str(rulebook)) is True

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
# Playbook detail vs EDA exclusion at call sites
# ---------------------------------------------------------------------------


class TestPlaybookDetailVsEdaExclusion:
    """Tests playbook-detail shape detection vs explicit EDA exclusion."""

    def test_eda_rulebook_still_playbook_shaped(self) -> None:
        """Verify EDA content with hosts is playbook-shaped for detail detection."""
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
        assert could_be_playbook_detail(body=body, data=data) is True
        assert could_be_eda_rulebook_detail(body=body, data=data) is True

    def test_eda_rulebook_with_only_sources_not_classified_by_content(self) -> None:
        """Verify content-only sources keys do not hide invalid playbooks."""
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
        assert could_be_playbook_detail(body=body, data=data) is True
        assert could_be_eda_rulebook_detail(body=body, data=data) is False

    def test_eda_rulebook_with_only_rules(self) -> None:
        """Verify rules-only EDA is playbook-shaped but identified as EDA."""
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
        assert could_be_playbook_detail(body=body, data=data) is True
        assert could_be_eda_rulebook_detail(body=body, data=data) is True

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

    def test_playbook_with_stray_rules_not_eda_detail(self) -> None:
        """Verify invalid play-level ``rules`` without EDA shape is not labeled EDA."""
        body = """\
- name: Bad play
  hosts: all
  rules:
    - name: Debug task
      ansible.builtin.debug:
        msg: hello
"""
        data: YAMLValue = [
            {
                "name": "Bad play",
                "hosts": "all",
                "rules": [{"name": "Debug task", "ansible.builtin.debug": {"msg": "hello"}}],
            }
        ]
        assert could_be_playbook_detail(body=body, data=data) is True
        assert could_be_eda_rulebook_detail(body=body, data=data) is False

    def test_import_playbook_still_detected(self) -> None:
        """Verify import_playbook directive is still detected."""
        body = "- import_playbook: other.yml\n"
        data: YAMLValue = [{"import_playbook": "other.yml"}]
        assert could_be_playbook_detail(body=body, data=data) is True


# ---------------------------------------------------------------------------
# Taskfile / Label Classification Excludes EDA
# ---------------------------------------------------------------------------


class TestEdaExcludedFromTaskfileLabel:
    """Tests that EDA rulebooks are not classified as taskfiles."""

    def test_could_be_taskfile_excludes_eda_content(self) -> None:
        """Verify EDA-shaped YAML is not treated as a taskfile."""
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
        assert could_be_eda_rulebook_detail(body=body, data=data) is True
        assert could_be_taskfile(body=body, data=data) is False

    def test_label_yml_file_marks_eda_as_rulebook(self, tmp_path: Path) -> None:
        """Verify label_yml_file returns rulebook for EDA content.

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
"""
        rulebook = tmp_path / "rulebook.yml"
        rulebook.write_text(content)
        label, _, error = label_yml_file(yml_path=str(rulebook))
        assert error is None
        assert label == "rulebook"

    def test_label_yml_file_path_only_rulebook_directory(self, tmp_path: Path) -> None:
        """Verify files under rulebooks/ are labeled rulebook even without sources/rules.

        Args:
            tmp_path: Pytest fixture providing temporary directory.
        """
        rulebooks_dir = tmp_path / "rulebooks"
        rulebooks_dir.mkdir()
        rulebook = rulebooks_dir / "minimal.yml"
        rulebook.write_text("---\n- name: Minimal\n  hosts: localhost\n")
        label, _, error = label_yml_file(yml_path=str(rulebook))
        assert error is None
        assert label == "rulebook"
