# Colocated tests for R101 (CommandExecRule). Rule uses annotations; test no fire without annotation.

from apme_engine.validators.native.rules._test_helpers import make_context, make_task_call, make_task_spec
from apme_engine.validators.native.rules.R101_command_exec import CommandExecRule


def test_R101_does_not_fire_when_no_annotation() -> None:
    spec = make_task_spec(module="ansible.builtin.command", resolved_name="ansible.builtin.command")
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = CommandExecRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False


def test_R101_match_only_tasks() -> None:
    from apme_engine.validators.native.rules._test_helpers import make_role_call, make_role_spec

    role = make_role_call(make_role_spec(name="foo"))
    ctx = make_context(role)
    rule = CommandExecRule()
    assert not rule.match(ctx)
