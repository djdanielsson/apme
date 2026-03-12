# Colocated tests for L036 (UnnecessaryIncludeVarsRule).

from apme_engine.engine.models import ExecutableType
from apme_engine.validators.native.rules._test_helpers import (
    make_context,
    make_task_call,
    make_task_spec,
)
from apme_engine.validators.native.rules.L036_unnecessary_include_vars import UnnecessaryIncludeVarsRule


def test_L036_fires_when_include_vars_no_tags_no_when() -> None:
    spec = make_task_spec(
        module="ansible.builtin.include_vars",
        executable_type=ExecutableType.MODULE_TYPE,
        resolved_name="ansible.builtin.include_vars",
        options={},  # no tags, no when
    )
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = UnnecessaryIncludeVarsRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is True
    assert result.rule is not None and result.rule.rule_id == "L036"


def test_L036_does_not_fire_when_include_vars_has_tags() -> None:
    spec = make_task_spec(
        module="ansible.builtin.include_vars",
        executable_type=ExecutableType.MODULE_TYPE,
        resolved_name="ansible.builtin.include_vars",
        options={"tags": ["config"]},
    )
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = UnnecessaryIncludeVarsRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False


def test_L036_does_not_fire_when_include_vars_has_when() -> None:
    spec = make_task_spec(
        module="ansible.builtin.include_vars",
        executable_type=ExecutableType.MODULE_TYPE,
        resolved_name="ansible.builtin.include_vars",
        options={"when": "x"},
    )
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = UnnecessaryIncludeVarsRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False


def test_L036_does_not_fire_for_non_include_vars() -> None:
    spec = make_task_spec(
        module="ansible.builtin.copy",
        resolved_name="ansible.builtin.copy",
    )
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = UnnecessaryIncludeVarsRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False
