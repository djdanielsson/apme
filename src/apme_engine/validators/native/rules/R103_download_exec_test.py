# Colocated tests for R103 (DownloadExecRule). Rule uses annotations and ctx.before(); test no fire without annotation.

from apme_engine.validators.native.rules._test_helpers import make_context, make_task_call, make_task_spec
from apme_engine.validators.native.rules.R103_download_exec import DownloadExecRule


def test_R103_does_not_fire_when_no_annotation() -> None:
    spec = make_task_spec(module="get_url", resolved_name="ansible.builtin.get_url")
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = DownloadExecRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False
