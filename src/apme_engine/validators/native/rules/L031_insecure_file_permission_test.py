# Colocated tests for R116 (FilePermissionRule). Rule uses annotations; test no fire without annotation.

from apme_engine.validators.native.rules._test_helpers import make_context, make_task_call, make_task_spec
from apme_engine.validators.native.rules.L031_insecure_file_permission import FilePermissionRule


def test_R116_does_not_fire_when_no_annotation() -> None:
    spec = make_task_spec(module="copy", resolved_name="ansible.builtin.copy")
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = FilePermissionRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False
