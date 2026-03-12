# Colocated tests for sample_rule (SampleRule).

from apme_engine.engine.models import MutableContent
from apme_engine.validators.native.rules._test_helpers import (
    make_context,
    make_task_call,
    make_task_spec,
)
from apme_engine.validators.native.rules.sample_rule import SampleRule


def test_sample_rule_matches_task_and_process_returns_task_block() -> None:
    spec = make_task_spec(module="ansible.builtin.copy", name="Copy file")
    task = make_task_call(spec)
    task.content = MutableContent(_yaml="- name: Copy file\n  copy:\n    src: a\n    dest: b", _task_spec=spec)
    ctx = make_context(task)
    rule = SampleRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is True
    assert result.rule is not None and result.rule.rule_id == "Sample101"
    assert result.detail is not None
    assert "task_block" in result.detail
    assert "copy:" in result.detail["task_block"]
