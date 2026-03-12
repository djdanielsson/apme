# Colocated tests for L035 (UnnecessarySetFactRule / R204).

from apme_engine.engine.models import ExecutableType
from apme_engine.validators.native.rules._test_helpers import (
    make_context,
    make_task_call,
    make_task_spec,
)
from apme_engine.validators.native.rules.L035_unnecessary_set_fact import UnnecessarySetFactRule


def test_L035_fires_when_set_fact_with_random_in_args() -> None:
    spec = make_task_spec(
        module="ansible.builtin.set_fact",
        executable_type=ExecutableType.MODULE_TYPE,
        resolved_name="ansible.builtin.set_fact",
    )
    task = make_task_call(spec)
    task.args.raw = "something with random inside"
    ctx = make_context(task)
    rule = UnnecessarySetFactRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is True
    assert result.rule is not None and result.rule.rule_id == "L035"


def test_L035_does_not_fire_when_set_fact_without_random() -> None:
    spec = make_task_spec(
        module="ansible.builtin.set_fact",
        executable_type=ExecutableType.MODULE_TYPE,
        resolved_name="ansible.builtin.set_fact",
    )
    task = make_task_call(spec)
    task.args.raw = {"my_var": "value"}
    ctx = make_context(task)
    rule = UnnecessarySetFactRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False


def test_L035_does_not_fire_for_non_set_fact() -> None:
    spec = make_task_spec(module="ansible.builtin.copy", resolved_name="ansible.builtin.copy")
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = UnnecessarySetFactRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False
