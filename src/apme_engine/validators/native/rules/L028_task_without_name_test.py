# Colocated tests for L028 (TaskWithoutNameRule). Uses Python-object context from _test_helpers.


from apme_engine.validators.native.rules._test_helpers import (
    make_context,
    make_task_call,
    make_task_spec,
)
from apme_engine.validators.native.rules.L028_task_without_name import TaskWithoutNameRule


def test_L028_fires_when_task_has_no_name() -> None:
    spec = make_task_spec(module="copy")
    spec.name = ""
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = TaskWithoutNameRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is True
    assert result.rule is not None and result.rule.rule_id == "L028"


def test_L028_does_not_fire_when_task_has_name() -> None:
    spec = make_task_spec(name="Install package", module="ansible.builtin.apt")
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = TaskWithoutNameRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False


def test_L028_does_not_fire_for_role() -> None:
    from apme_engine.validators.native.rules._test_helpers import make_role_call, make_role_spec

    spec = make_role_spec(name="foo")
    role = make_role_call(spec)
    ctx = make_context(role)
    rule = TaskWithoutNameRule()
    assert not rule.match(ctx)
