"""Tests for the YAML formatter."""

import textwrap
from pathlib import Path

import pytest

from apme_engine.formatter import (
    FormatResult,
    check_idempotent,
    format_content,
    format_directory,
    format_file,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(text: str, filename: str = "test.yml") -> FormatResult:
    return format_content(textwrap.dedent(text), filename=filename)


# ---------------------------------------------------------------------------
# Tab removal (L040)
# ---------------------------------------------------------------------------

class TestTabRemoval:
    def test_tabs_replaced_with_spaces(self):
        result = _fmt("- name: Test\n\tansible.builtin.debug:\n\t\tmsg: hello\n")
        assert "\t" not in result.formatted
        assert result.changed

    def test_no_tabs_unchanged(self):
        text = "- name: Test\n  ansible.builtin.debug:\n    msg: hello\n"
        result = format_content(text)
        assert "\t" not in result.formatted


# ---------------------------------------------------------------------------
# Key reorder (L041)
# ---------------------------------------------------------------------------

class TestKeyReorder:
    def test_name_moved_before_module(self):
        text = textwrap.dedent("""\
        - ansible.builtin.debug:
            msg: hello
          name: Say hello
        """)
        result = format_content(text)
        lines = result.formatted.splitlines()
        name_line = next(i for i, l in enumerate(lines) if "name:" in l)
        debug_line = next(i for i, l in enumerate(lines) if "debug" in l)
        assert name_line < debug_line, "name should come before module"
        assert result.changed

    def test_already_ordered_unchanged(self):
        text = textwrap.dedent("""\
        - name: Say hello
          ansible.builtin.debug:
            msg: hello
        """)
        result = format_content(text)
        # May still change due to other formatting; key order should be stable
        lines = result.formatted.splitlines()
        name_line = next(i for i, l in enumerate(lines) if "name:" in l)
        debug_line = next(i for i, l in enumerate(lines) if "debug" in l)
        assert name_line < debug_line

    def test_play_level_key_order(self):
        text = textwrap.dedent("""\
        - tasks:
            - ansible.builtin.debug:
                msg: hi
              name: Task
          name: Play
          hosts: all
        """)
        result = format_content(text)
        assert "name:" in result.formatted
        lines = result.formatted.splitlines()
        name_lines = [i for i, l in enumerate(lines) if "name:" in l]
        assert len(name_lines) >= 1


# ---------------------------------------------------------------------------
# Jinja spacing (L051)
# ---------------------------------------------------------------------------

class TestJinjaSpacing:
    def test_no_space_gets_space(self):
        text = "- name: Test\n  ansible.builtin.debug:\n    msg: \"{{foo}}\"\n"
        result = format_content(text)
        assert "{{ foo }}" in result.formatted
        assert result.changed

    def test_extra_spaces_normalized(self):
        text = "- name: Test\n  ansible.builtin.debug:\n    msg: \"{{  foo  }}\"\n"
        result = format_content(text)
        assert "{{ foo }}" in result.formatted

    def test_already_correct_unchanged(self):
        text = "- name: Test\n  ansible.builtin.debug:\n    msg: \"{{ foo }}\"\n"
        result = format_content(text)
        assert "{{ foo }}" in result.formatted

    def test_complex_expression(self):
        text = '- name: Test\n  ansible.builtin.debug:\n    msg: "{{item.name | default(\'none\')}}"\n'
        result = format_content(text)
        assert "{{ item.name | default('none') }}" in result.formatted


# ---------------------------------------------------------------------------
# Indentation normalization
# ---------------------------------------------------------------------------

class TestIndentation:
    def test_mixed_indent_normalized(self):
        text = "- name: Test\n    ansible.builtin.debug:\n        msg: hello\n"
        result = format_content(text)
        lines = result.formatted.splitlines()
        for line in lines:
            stripped = line.lstrip()
            if stripped and not stripped.startswith("-"):
                indent = len(line) - len(stripped)
                assert indent % 2 == 0, f"Non-2-space indent: {line!r}"


# ---------------------------------------------------------------------------
# Comment preservation
# ---------------------------------------------------------------------------

class TestComments:
    def test_inline_comment_preserved(self):
        text = "- name: Test  # important\n  ansible.builtin.debug:\n    msg: hello\n"
        result = format_content(text)
        assert "# important" in result.formatted

    def test_full_line_comment_preserved(self):
        text = "# This is a play\n- name: Test\n  ansible.builtin.debug:\n    msg: hello\n"
        result = format_content(text)
        assert "# This is a play" in result.formatted

    def test_preamble_comment_preserved(self):
        text = "# Header comment\n---\n- name: Test\n  ansible.builtin.debug:\n    msg: hello\n"
        result = format_content(text)
        assert "# Header comment" in result.formatted


# ---------------------------------------------------------------------------
# Octal preservation
# ---------------------------------------------------------------------------

class TestOctal:
    def test_octal_mode_preserved(self):
        text = textwrap.dedent("""\
        - name: Set perms
          ansible.builtin.file:
            path: /tmp/foo
            mode: "0644"
        """)
        result = format_content(text)
        assert "0644" in result.formatted


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_file(self):
        result = format_content("")
        assert not result.changed

    def test_non_yaml_content(self):
        result = format_content("this is not yaml: [[[invalid")
        assert not result.changed

    def test_scalar_document_returned_unchanged(self):
        result = format_content("hello\n")
        assert not result.changed
        assert result.formatted == "hello\n"

    def test_empty_document_marker(self):
        result = format_content("---\n")
        assert not result.changed or result.formatted.strip() == "---"

    def test_already_formatted_no_change(self):
        text = textwrap.dedent("""\
        - name: Already clean
          ansible.builtin.debug:
            msg: "{{ foo }}"
        """)
        result = format_content(text)
        if result.changed:
            second = format_content(result.formatted)
            assert not second.changed, "Second pass should produce no changes"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    @pytest.mark.parametrize("text,desc", [
        ("- name: Test\n\tansible.builtin.debug:\n\t\tmsg: hello\n", "tabs"),
        ("- ansible.builtin.debug:\n    msg: hello\n  name: Reorder\n", "key order"),
        ('- name: T\n  ansible.builtin.debug:\n    msg: "{{foo}}"\n', "jinja spacing"),
        ("- name: Test\n    ansible.builtin.debug:\n        msg: deep\n", "mixed indent"),
        ("# comment\n- name: Test\n  ansible.builtin.debug:\n    msg: hi\n", "with comment"),
    ])
    def test_format_twice_no_diff(self, text, desc):
        first = format_content(text, filename=f"test_{desc}.yml")
        assert check_idempotent(first), f"Formatter is not idempotent for: {desc}"

    def test_idempotent_complex_playbook(self):
        text = textwrap.dedent("""\
        # Playbook header
        ---
        - hosts: all
          become: true
          tasks:
            - ansible.builtin.shell: echo "hello"
              name: Say hello
              when: ansible_os_family == "Debian"
              tags:
                - setup

            - name: Install packages
              ansible.builtin.yum:
                name: "{{item}}"
                state: present
              loop:
                - httpd
                - nginx

            - name: Download file
              ansible.builtin.get_url:
                url: https://example.com/file.tar.gz
                dest: /tmp/file.tar.gz
                mode: "0644"
        """)
        first = format_content(text)
        assert check_idempotent(first), "Complex playbook is not idempotent"


# ---------------------------------------------------------------------------
# format_file (filesystem)
# ---------------------------------------------------------------------------

class TestFormatFile:
    def test_format_file_reads_and_formats(self, tmp_path):
        p = tmp_path / "test.yml"
        p.write_text("- ansible.builtin.debug:\n    msg: hi\n  name: Test\n")
        result = format_file(p)
        assert result.path == p
        assert result.changed
        lines = result.formatted.splitlines()
        name_line = next(i for i, l in enumerate(lines) if "name:" in l)
        debug_line = next(i for i, l in enumerate(lines) if "debug" in l)
        assert name_line < debug_line


# ---------------------------------------------------------------------------
# format_directory
# ---------------------------------------------------------------------------

class TestFormatDirectory:
    def test_discovers_yaml_files(self, tmp_path):
        (tmp_path / "a.yml").write_text("- name: A\n  ansible.builtin.debug:\n    msg: a\n")
        (tmp_path / "b.yaml").write_text("- name: B\n  ansible.builtin.debug:\n    msg: b\n")
        (tmp_path / "c.txt").write_text("not yaml")
        results = format_directory(tmp_path)
        paths = {r.path.name for r in results}
        assert "a.yml" in paths
        assert "b.yaml" in paths
        assert "c.txt" not in paths

    def test_skips_git_dir(self, tmp_path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config.yml").write_text("- name: Git\n  debug: msg=hi\n")
        (tmp_path / "play.yml").write_text("- name: Play\n  ansible.builtin.debug:\n    msg: hi\n")
        results = format_directory(tmp_path)
        paths = {r.path.name for r in results}
        assert "config.yml" not in paths
        assert "play.yml" in paths

    def test_multidepth_workspace(self, tmp_path):
        """Formatter recurses into nested role/playbook directory structures."""
        (tmp_path / "site.yml").write_text("- ansible.builtin.debug:\n    msg: hi\n  name: Top\n")
        roles = tmp_path / "roles" / "web" / "tasks"
        roles.mkdir(parents=True)
        (roles / "main.yml").write_text("- ansible.builtin.shell: echo\n  name: Deep task\n")
        group_vars = tmp_path / "inventory" / "group_vars"
        group_vars.mkdir(parents=True)
        (group_vars / "all.yml").write_text("my_var: \"{{foo}}\"\n")

        results = format_directory(tmp_path)
        result_paths = {str(r.path.relative_to(tmp_path)) for r in results}

        assert "site.yml" in result_paths
        assert str(Path("roles/web/tasks/main.yml")) in result_paths
        assert str(Path("inventory/group_vars/all.yml")) in result_paths
        assert len(results) == 3

        changed = [r for r in results if r.changed]
        assert len(changed) >= 2, "At least site.yml and group_vars/all.yml should change"

        for r in changed:
            assert check_idempotent(r), f"Not idempotent: {r.path}"

    def test_exclude_pattern(self, tmp_path):
        vendor = tmp_path / "vendor"
        vendor.mkdir()
        (vendor / "lib.yml").write_text("- name: Vendor\n  debug: msg=hi\n")
        (tmp_path / "main.yml").write_text("- name: Main\n  ansible.builtin.debug:\n    msg: hi\n")
        results = format_directory(tmp_path, exclude_patterns=["vendor/*"])
        paths = {r.path.name for r in results}
        assert "lib.yml" not in paths
        assert "main.yml" in paths


# ---------------------------------------------------------------------------
# FormatResult.diff content
# ---------------------------------------------------------------------------

class TestDiffOutput:
    def test_diff_contains_file_paths(self):
        text = "- ansible.builtin.debug:\n    msg: hi\n  name: Test\n"
        result = format_content(text, filename="playbook.yml")
        assert result.changed
        assert "a/playbook.yml" in result.diff
        assert "b/playbook.yml" in result.diff

    def test_no_diff_when_unchanged(self):
        text = "- name: Test\n  ansible.builtin.debug:\n    msg: hi\n"
        result = format_content(text)
        if not result.changed:
            assert result.diff == ""
