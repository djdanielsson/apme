"""Unit tests for GraphRule L110: debug tasks logging sensitive variables."""

from __future__ import annotations

from typing import cast

from apme_engine.engine.content_graph import (
    ContentGraph,
    ContentNode,
    EdgeType,
    NodeIdentity,
    NodeScope,
    NodeType,
)
from apme_engine.engine.graph_scanner import scan
from apme_engine.engine.models import YAMLDict
from apme_engine.validators.native.rules.graph_rule_base import GraphRule
from apme_engine.validators.native.rules.L110_debug_sensitive_vars_graph import (
    DebugSensitiveVarsGraphRule,
    _extract_jinja_vars,
    _find_sensitive_vars_in_debug,
    _var_looks_sensitive,
)


def _make_debug_graph(
    *,
    msg: str | None = None,
    var: str | None = None,
    no_log: bool | None = None,
    block_no_log: bool | None = None,
    play_no_log: bool | None = None,
) -> tuple[ContentGraph, str]:
    """Build a playbook > play > [block >] task graph for L110 testing.

    Args:
        msg: Debug msg parameter.
        var: Debug var parameter.
        no_log: Task-level no_log setting.
        block_no_log: Block-level no_log setting.
        play_no_log: Play-level no_log setting.

    Returns:
        Tuple of (graph, task_node_id).
    """
    g = ContentGraph()

    pb = ContentNode(
        identity=NodeIdentity(path="site.yml", node_type=NodeType.PLAYBOOK),
        file_path="site.yml",
        scope=NodeScope.OWNED,
    )

    play = ContentNode(
        identity=NodeIdentity(path="site.yml/plays[0]", node_type=NodeType.PLAY),
        file_path="site.yml",
        line_start=1,
        no_log=play_no_log,
        scope=NodeScope.OWNED,
    )

    g.add_node(pb)
    g.add_node(play)
    g.add_edge(pb.node_id, play.node_id, EdgeType.CONTAINS)

    parent_id = play.node_id

    if block_no_log is not None:
        block = ContentNode(
            identity=NodeIdentity(path="site.yml/plays[0]/block[0]", node_type=NodeType.BLOCK),
            file_path="site.yml",
            line_start=5,
            no_log=block_no_log,
            scope=NodeScope.OWNED,
        )
        g.add_node(block)
        g.add_edge(play.node_id, block.node_id, EdgeType.CONTAINS)
        parent_id = block.node_id

    module_options: YAMLDict = {}
    if msg is not None:
        module_options["msg"] = msg
    if var is not None:
        module_options["var"] = var

    task = ContentNode(
        identity=NodeIdentity(path="site.yml/plays[0]/tasks[0]", node_type=NodeType.TASK),
        file_path="site.yml",
        line_start=10,
        module="ansible.builtin.debug",
        module_options=module_options,
        no_log=no_log,
        scope=NodeScope.OWNED,
    )
    g.add_node(task)
    g.add_edge(parent_id, task.node_id, EdgeType.CONTAINS)

    return g, task.node_id


class TestExtractJinjaVars:
    """Tests for _extract_jinja_vars helper."""

    def test_single_var(self) -> None:
        """Extract single variable from Jinja template."""
        result = _extract_jinja_vars("{{ password }}")
        assert result == {"password"}

    def test_multiple_vars(self) -> None:
        """Extract multiple variables from template."""
        result = _extract_jinja_vars("{{ user }} has {{ api_key }}")
        assert result == {"user", "api_key"}

    def test_no_jinja(self) -> None:
        """Plain text returns empty set."""
        result = _extract_jinja_vars("just plain text")
        assert result == set()

    def test_nested_var(self) -> None:
        """Extract var from nested expression (first var only)."""
        result = _extract_jinja_vars("{{ db_password | default('') }}")
        assert "db_password" in result

    def test_non_string_input(self) -> None:
        """Non-string input returns empty set."""
        result = _extract_jinja_vars(123)  # type: ignore[arg-type]
        assert result == set()


class TestVarLooksSensitive:
    """Tests for _var_looks_sensitive helper."""

    def test_password_variants(self) -> None:
        """Password variants are sensitive."""
        assert _var_looks_sensitive("password")
        assert _var_looks_sensitive("db_password")
        assert _var_looks_sensitive("PASSWORD")
        assert _var_looks_sensitive("passwd")
        assert _var_looks_sensitive("user_pwd")

    def test_secret_variants(self) -> None:
        """Secret variants are sensitive."""
        assert _var_looks_sensitive("secret")
        assert _var_looks_sensitive("app_secret")
        assert _var_looks_sensitive("secrets")

    def test_token_variants(self) -> None:
        """Token variants are sensitive."""
        assert _var_looks_sensitive("token")
        assert _var_looks_sensitive("auth_token")
        assert _var_looks_sensitive("access_token")
        assert _var_looks_sensitive("api_token")

    def test_api_key_variants(self) -> None:
        """API key variants are sensitive."""
        assert _var_looks_sensitive("api_key")
        assert _var_looks_sensitive("apikey")

    def test_credential_variants(self) -> None:
        """Credential variants are sensitive."""
        assert _var_looks_sensitive("credential")
        assert _var_looks_sensitive("credentials")
        assert _var_looks_sensitive("db_cred")

    def test_key_variants(self) -> None:
        """Key variants are sensitive."""
        assert _var_looks_sensitive("private_key")
        assert _var_looks_sensitive("ssh_key")

    def test_non_sensitive(self) -> None:
        """Non-sensitive names return False."""
        assert not _var_looks_sensitive("username")
        assert not _var_looks_sensitive("hostname")
        assert not _var_looks_sensitive("port")
        assert not _var_looks_sensitive("config")

    def test_false_positive_avoidance(self) -> None:
        """Substring matches that are not word-bounded are rejected."""
        assert not _var_looks_sensitive("secretary_name")
        assert not _var_looks_sensitive("tokenized_value")
        assert not _var_looks_sensitive("accreditation")
        assert not _var_looks_sensitive("passwords_enabled")


class TestFindSensitiveVarsInDebug:
    """Tests for _find_sensitive_vars_in_debug helper."""

    def test_sensitive_in_msg(self) -> None:
        """Find sensitive var in msg parameter."""
        node = ContentNode(
            identity=NodeIdentity(path="test", node_type=NodeType.TASK),
            module="ansible.builtin.debug",
            module_options={"msg": "Password is {{ db_password }}"},
        )
        result = _find_sensitive_vars_in_debug(node)
        assert "db_password" in result

    def test_sensitive_in_var(self) -> None:
        """Find sensitive var in var parameter."""
        node = ContentNode(
            identity=NodeIdentity(path="test", node_type=NodeType.TASK),
            module="ansible.builtin.debug",
            module_options={"var": "api_token"},
        )
        result = _find_sensitive_vars_in_debug(node)
        assert "api_token" in result

    def test_multiple_sensitive(self) -> None:
        """Find multiple sensitive vars."""
        node = ContentNode(
            identity=NodeIdentity(path="test", node_type=NodeType.TASK),
            module="ansible.builtin.debug",
            module_options={"msg": "{{ password }} and {{ secret }}"},
        )
        result = _find_sensitive_vars_in_debug(node)
        assert "password" in result
        assert "secret" in result

    def test_no_sensitive(self) -> None:
        """No sensitive vars returns empty list."""
        node = ContentNode(
            identity=NodeIdentity(path="test", node_type=NodeType.TASK),
            module="ansible.builtin.debug",
            module_options={"msg": "Hello {{ username }}"},
        )
        result = _find_sensitive_vars_in_debug(node)
        assert result == []


class TestDebugSensitiveVarsGraphRule:
    """Tests for the L110 GraphRule."""

    def test_sensitive_var_in_msg_fires(self) -> None:
        """Rule fires when debug msg contains sensitive variable."""
        graph, task_id = _make_debug_graph(msg="Password: {{ db_password }}")
        rule = DebugSensitiveVarsGraphRule()

        assert rule.match(graph, task_id)
        result = rule.process(graph, task_id)

        assert result is not None
        assert result.verdict is True
        assert "db_password" in str(result.detail)

    def test_sensitive_var_in_var_fires(self) -> None:
        """Rule fires when debug var is a sensitive variable name."""
        graph, task_id = _make_debug_graph(var="api_secret")
        rule = DebugSensitiveVarsGraphRule()

        assert rule.match(graph, task_id)
        result = rule.process(graph, task_id)

        assert result is not None
        assert result.verdict is True

    def test_no_log_on_task_passes(self) -> None:
        """Rule passes when no_log is set on task."""
        graph, task_id = _make_debug_graph(
            msg="Password: {{ db_password }}",
            no_log=True,
        )
        rule = DebugSensitiveVarsGraphRule()

        result = rule.process(graph, task_id)

        assert result is not None
        assert result.verdict is False

    def test_no_log_on_block_passes(self) -> None:
        """Rule passes when no_log is set on containing block."""
        graph, task_id = _make_debug_graph(
            msg="Password: {{ db_password }}",
            block_no_log=True,
        )
        rule = DebugSensitiveVarsGraphRule()

        result = rule.process(graph, task_id)

        assert result is not None
        assert result.verdict is False

    def test_no_log_on_play_passes(self) -> None:
        """Rule passes when no_log is set on containing play."""
        graph, task_id = _make_debug_graph(
            msg="Password: {{ db_password }}",
            play_no_log=True,
        )
        rule = DebugSensitiveVarsGraphRule()

        result = rule.process(graph, task_id)

        assert result is not None
        assert result.verdict is False

    def test_non_sensitive_var_passes(self) -> None:
        """Rule passes when debug msg contains only non-sensitive vars."""
        graph, task_id = _make_debug_graph(msg="User: {{ username }}")
        rule = DebugSensitiveVarsGraphRule()

        result = rule.process(graph, task_id)

        assert result is not None
        assert result.verdict is False

    def test_no_msg_or_var_no_match(self) -> None:
        """Rule does not match debug tasks without msg or var."""
        g = ContentGraph()
        task = ContentNode(
            identity=NodeIdentity(path="test", node_type=NodeType.TASK),
            file_path="test.yml",
            module="ansible.builtin.debug",
            module_options={},
            scope=NodeScope.OWNED,
        )
        g.add_node(task)
        rule = DebugSensitiveVarsGraphRule()

        assert not rule.match(g, task.node_id)

    def test_non_debug_module_no_match(self) -> None:
        """Rule does not match non-debug modules."""
        g = ContentGraph()
        task = ContentNode(
            identity=NodeIdentity(path="test", node_type=NodeType.TASK),
            file_path="test.yml",
            module="ansible.builtin.command",
            module_options={"cmd": "echo {{ password }}"},
            scope=NodeScope.OWNED,
        )
        g.add_node(task)
        rule = DebugSensitiveVarsGraphRule()

        assert not rule.match(g, task.node_id)

    def test_scanner_integration(self) -> None:
        """Rule integrates correctly with graph scanner."""
        graph, _ = _make_debug_graph(msg="Token: {{ auth_token }}")
        rules: list[GraphRule] = [DebugSensitiveVarsGraphRule()]

        report = scan(graph, rules, owned_only=True)

        violations = [r for nr in report.node_results for r in nr.rule_results if r.verdict]
        assert len(violations) == 1
        assert violations[0].rule is not None
        assert violations[0].rule.rule_id == "L110"

    def test_multiple_sensitive_vars_all_listed(self) -> None:
        """All sensitive vars are listed in violation message."""
        graph, task_id = _make_debug_graph(msg="{{ password }} and {{ api_key }} and {{ secret }}")
        rule = DebugSensitiveVarsGraphRule()

        result = rule.process(graph, task_id)

        assert result is not None
        assert result.verdict is True
        detail = result.detail or {}
        sensitive_vars = cast(list[str], detail.get("sensitive_vars", []))
        assert "password" in sensitive_vars
        assert "api_key" in sensitive_vars
        assert "secret" in sensitive_vars

    def test_legacy_debug_module_name(self) -> None:
        """Rule matches legacy 'debug' module name."""
        g = ContentGraph()
        task = ContentNode(
            identity=NodeIdentity(path="test", node_type=NodeType.TASK),
            file_path="test.yml",
            module="debug",
            module_options={"msg": "{{ password }}"},
            scope=NodeScope.OWNED,
        )
        g.add_node(task)
        rule = DebugSensitiveVarsGraphRule()

        assert rule.match(g, task.node_id)
        result = rule.process(g, task.node_id)
        assert result is not None
        assert result.verdict is True

    def test_ansible_legacy_debug_module(self) -> None:
        """Rule matches ansible.legacy.debug module."""
        g = ContentGraph()
        task = ContentNode(
            identity=NodeIdentity(path="test", node_type=NodeType.TASK),
            file_path="test.yml",
            module="ansible.legacy.debug",
            module_options={"var": "credentials"},
            scope=NodeScope.OWNED,
        )
        g.add_node(task)
        rule = DebugSensitiveVarsGraphRule()

        assert rule.match(g, task.node_id)
        result = rule.process(g, task.node_id)
        assert result is not None
        assert result.verdict is True
