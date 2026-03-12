# Colocated tests for R401 (ListAllInboundSrcRule).

from apme_engine.validators.native.rules._test_helpers import (
    make_context,
    make_task_call,
    make_task_spec,
)
from apme_engine.validators.native.rules.R401_list_all_inbound_src import ListAllInboundSrcRule


def test_R401_does_not_fire_when_not_end() -> None:
    spec = make_task_spec(module="ansible.builtin.copy")
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = ListAllInboundSrcRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False
    assert result.rule is not None and result.rule.rule_id == "R401"


def test_R401_does_not_fire_at_end_when_no_inbound_sources() -> None:
    spec = make_task_spec(module="ansible.builtin.copy")
    task = make_task_call(spec)
    ctx = make_context(task, sequence=[task])
    rule = ListAllInboundSrcRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False
