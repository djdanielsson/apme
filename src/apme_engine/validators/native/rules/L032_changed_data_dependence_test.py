# Colocated tests for L032 (ChangedDataDependenceRule / R201).

from apme_engine.engine.models import Variable
from apme_engine.validators.native.rules._test_helpers import (
    make_context,
    make_task_call,
    make_task_spec,
)
from apme_engine.validators.native.rules.L032_changed_data_dependence import ChangedDataDependenceRule


def test_L032_does_not_fire_when_no_defined_vars() -> None:
    spec = make_task_spec(module="ansible.builtin.copy")
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = ChangedDataDependenceRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False
    assert result.rule is not None and result.rule.rule_id == "L032"


def test_L032_fires_when_variable_redefined() -> None:
    spec = make_task_spec(module="ansible.builtin.set_fact")
    spec.set_facts = {"my_var": "x"}
    task = make_task_call(spec)
    task.variable_set["my_var"] = [
        Variable(name="my_var", value="a", setter="task:1"),
        Variable(name="my_var", value="b", setter="task:2"),
    ]
    ctx = make_context(task)
    rule = ChangedDataDependenceRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is True
    assert result.detail is not None
    assert len(result.detail["variables"]) == 1
    assert result.detail["variables"][0]["name"] == "my_var"
