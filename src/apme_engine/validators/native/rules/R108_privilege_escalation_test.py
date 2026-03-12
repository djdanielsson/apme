# Colocated tests for R108 (PrivilegeEscalationRule). Rule uses annotations; test no fire without annotation.

from apme_engine.validators.native.rules._test_helpers import make_context, make_task_call, make_task_spec
from apme_engine.validators.native.rules.R108_privilege_escalation import PrivilegeEscalationRule


def test_R108_does_not_fire_when_no_annotation() -> None:
    spec = make_task_spec(module="become", resolved_name="ansible.builtin.become")
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = PrivilegeEscalationRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False
