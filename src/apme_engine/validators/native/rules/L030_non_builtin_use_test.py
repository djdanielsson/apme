# Colocated tests for L030 (NonBuiltinUseRule). Uses Python-object context from _test_helpers.


from apme_engine.engine.models import ExecutableType
from apme_engine.validators.native.rules._test_helpers import (
    make_context,
    make_task_call,
    make_task_spec,
)
from apme_engine.validators.native.rules.L030_non_builtin_use import NonBuiltinUseRule


def test_L030_fires_when_module_not_builtin() -> None:
    spec = make_task_spec(
        module="copy",
        executable_type=ExecutableType.MODULE_TYPE,
        resolved_name="community.general.copy",
    )
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = NonBuiltinUseRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is True
    assert result.rule is not None and result.rule.rule_id == "L030"


def test_L030_does_not_fire_when_builtin() -> None:
    spec = make_task_spec(
        module="ansible.builtin.copy",
        executable_type=ExecutableType.MODULE_TYPE,
        resolved_name="ansible.builtin.copy",
    )
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = NonBuiltinUseRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False
