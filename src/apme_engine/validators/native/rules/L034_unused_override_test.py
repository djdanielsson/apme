# Colocated tests for L034 (UnusedOverrideRule / R203).

from apme_engine.engine.models import Variable, VariableType
from apme_engine.validators.native.rules._test_helpers import (
    make_context,
    make_task_call,
    make_task_spec,
)
from apme_engine.validators.native.rules.L034_unused_override import UnusedOverrideRule


def test_L034_does_not_fire_when_no_defined_vars() -> None:
    spec = make_task_spec(module="ansible.builtin.copy")
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = UnusedOverrideRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False
    assert result.rule is not None and result.rule.rule_id == "L034"


def test_L034_fires_when_new_definition_has_lower_precedence() -> None:
    spec = make_task_spec(module="ansible.builtin.set_fact")
    spec.set_facts = {"my_var": "x"}
    task = make_task_call(spec)
    task.variable_set["my_var"] = [
        Variable(name="my_var", value="a", type=VariableType.SetFacts, setter="task:1"),
        Variable(name="my_var", value="b", type=VariableType.RoleDefaults, setter="task:2"),
    ]
    ctx = make_context(task)
    rule = UnusedOverrideRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is True
    assert result.detail is not None
    assert len(result.detail["variables"]) == 1
    assert result.detail["variables"][0]["new_precedence"] == VariableType.RoleDefaults


def test_L034_does_not_fire_when_single_definition() -> None:
    spec = make_task_spec(module="ansible.builtin.set_fact")
    spec.set_facts = {"my_var": "x"}
    task = make_task_call(spec)
    task.variable_set["my_var"] = [Variable(name="my_var", value="x", setter="task:1")]
    ctx = make_context(task)
    rule = UnusedOverrideRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False
