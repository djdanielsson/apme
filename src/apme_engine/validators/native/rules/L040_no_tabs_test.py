# Colocated tests for L040 (NoTabsRule). Uses Python-object context from _test_helpers.


from apme_engine.validators.native.rules._test_helpers import (
    make_context,
    make_task_call,
    make_task_spec,
)
from apme_engine.validators.native.rules.L040_no_tabs import NoTabsRule


def test_L040_fires_when_yaml_has_tabs() -> None:
    spec = make_task_spec(module="ansible.builtin.copy")
    spec.yaml_lines = "- name: Copy\n\tcopy:\n  \tdest: /tmp"
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = NoTabsRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is True
    assert result.rule is not None and result.rule.rule_id == "L040"
    assert result.detail is not None
    assert "lines_with_tabs" in result.detail


def test_L040_does_not_fire_when_no_tabs() -> None:
    spec = make_task_spec(module="ansible.builtin.copy")
    spec.yaml_lines = "- name: Copy\n  copy:\n    dest: /tmp"
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = NoTabsRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False


def test_L040_does_not_fire_for_role() -> None:
    from apme_engine.validators.native.rules._test_helpers import make_role_call, make_role_spec

    role = make_role_call(make_role_spec(name="foo"))
    ctx = make_context(role)
    rule = NoTabsRule()
    assert not rule.match(ctx)
