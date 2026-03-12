# Colocated tests for R402 (ListAllUsedVariablesRule).

from apme_engine.validators.native.rules._test_helpers import (
    make_context,
    make_task_call,
    make_task_spec,
)
from apme_engine.validators.native.rules.R402_list_all_used_variables import ListAllUsedVariablesRule


def test_R402_fires_at_end_and_includes_variable_use_keys() -> None:
    spec = make_task_spec(module="ansible.builtin.copy")
    task = make_task_call(spec)
    task.variable_use["my_var"] = []
    ctx = make_context(task, sequence=[task])
    rule = ListAllUsedVariablesRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is True
    assert result.rule is not None and result.rule.rule_id == "R402"
    assert result.detail is not None
    assert "variables" in result.detail
    assert "my_var" in result.detail["variables"]


def test_R402_does_not_fire_when_not_end() -> None:
    spec = make_task_spec(module="ansible.builtin.copy")
    task = make_task_call(spec)
    ctx = make_context(task)  # sequence empty
    rule = ListAllUsedVariablesRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False
