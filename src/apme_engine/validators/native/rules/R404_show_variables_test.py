# Colocated tests for R404 (ShowVariablesRule).

from apme_engine.validators.native.rules._test_helpers import (
    make_context,
    make_task_call,
    make_task_spec,
)
from apme_engine.validators.native.rules.R404_show_variables import ShowVariablesRule


def test_R404_always_fires_and_exposes_variable_set() -> None:
    spec = make_task_spec(module="ansible.builtin.copy")
    task = make_task_call(spec)
    task.variable_set["foo"] = []
    ctx = make_context(task)
    rule = ShowVariablesRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is True
    assert result.rule is not None and result.rule.rule_id == "R404"
    assert result.detail is not None
    assert result.detail["variables"] == {"foo": []}


def test_R404_empty_variable_set() -> None:
    spec = make_task_spec(module="ansible.builtin.copy")
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = ShowVariablesRule()
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is True
    assert result.detail is not None
    assert "variables" in result.detail
