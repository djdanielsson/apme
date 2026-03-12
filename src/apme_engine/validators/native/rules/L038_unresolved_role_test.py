# Colocated tests for L038 (UnresolvedRoleRule).

from apme_engine.engine.models import ExecutableType
from apme_engine.validators.native.rules._test_helpers import (
    make_context,
    make_task_call,
    make_task_spec,
)
from apme_engine.validators.native.rules.L038_unresolved_role import UnresolvedRoleRule


def test_L038_fires_when_role_unresolved() -> None:
    spec = make_task_spec(
        module="some_role",
        executable="some_role",
        executable_type=ExecutableType.ROLE_TYPE,
        resolved_name="",  # unresolved
    )
    spec.resolved_name = ""  # override helper fallback so role stays unresolved
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = UnresolvedRoleRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is True
    assert result.rule is not None and result.rule.rule_id == "L038"


def test_L038_does_not_fire_when_role_resolved() -> None:
    spec = make_task_spec(
        module="geerlingguy.docker",
        executable_type=ExecutableType.ROLE_TYPE,
        resolved_name="geerlingguy.docker",
    )
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = UnresolvedRoleRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False


def test_L038_does_not_fire_for_module_task() -> None:
    spec = make_task_spec(module="copy", executable_type=ExecutableType.MODULE_TYPE)
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = UnresolvedRoleRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False
