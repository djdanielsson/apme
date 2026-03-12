# Colocated tests for R113 (PkgInstallRule). Rule uses annotations; test no fire without annotation.

from apme_engine.validators.native.rules._test_helpers import make_context, make_task_call, make_task_spec
from apme_engine.validators.native.rules.R113_parameterized_pkg_install import PkgInstallRule


def test_R113_does_not_fire_when_no_annotation() -> None:
    spec = make_task_spec(module="yum", resolved_name="ansible.builtin.yum")
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = PkgInstallRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False
