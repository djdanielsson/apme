# Colocated tests for R115 (FileDeletionRule). Rule uses annotations; test no fire without annotation.

from apme_engine.validators.native.rules._test_helpers import make_context, make_task_call, make_task_spec
from apme_engine.validators.native.rules.R115_file_deletion import FileDeletionRule


def test_R115_does_not_fire_when_no_annotation() -> None:
    spec = make_task_spec(module="file", resolved_name="ansible.builtin.file")
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = FileDeletionRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False
