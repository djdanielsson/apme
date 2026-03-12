# Colocated tests for L029 (UseShellRule). Uses Python-object context from _test_helpers.


from apme_engine.engine.models import ExecutableType
from apme_engine.validators.native.rules._test_helpers import (
    make_context,
    make_task_call,
    make_task_spec,
)
from apme_engine.validators.native.rules.L029_command_instead_of_shell import UseShellRule


def test_L029_fires_when_resolved_is_shell() -> None:
    spec = make_task_spec(
        module="shell",
        executable="shell",
        executable_type=ExecutableType.MODULE_TYPE,
        resolved_name="ansible.builtin.shell",
    )
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = UseShellRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is True
    assert result.rule is not None and result.rule.rule_id == "L029"


def test_L029_does_not_fire_when_resolved_is_command() -> None:
    spec = make_task_spec(
        module="command",
        executable="command",
        executable_type=ExecutableType.MODULE_TYPE,
        resolved_name="ansible.builtin.command",
    )
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = UseShellRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False
