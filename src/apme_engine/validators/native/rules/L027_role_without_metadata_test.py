# Colocated tests for L027 (RoleWithoutMetadataRule). Uses Python-object context from _test_helpers.


from apme_engine.validators.native.rules._test_helpers import (
    make_context,
    make_role_call,
    make_role_spec,
)
from apme_engine.validators.native.rules.L027_role_without_metadata import RoleWithoutMetadataRule


def test_L027_fires_when_role_has_no_metadata() -> None:
    spec = make_role_spec(name="foo", metadata=None)
    role = make_role_call(spec)
    ctx = make_context(role)
    rule = RoleWithoutMetadataRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is True
    assert result.rule is not None and result.rule.rule_id == "L027"


def test_L027_fires_when_role_metadata_empty_dict() -> None:
    spec = make_role_spec(name="foo", metadata={})
    role = make_role_call(spec)
    ctx = make_context(role)
    rule = RoleWithoutMetadataRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is True


def test_L027_does_not_fire_when_role_has_metadata() -> None:
    spec = make_role_spec(name="foo", metadata={"galaxy_info": {"author": "me"}})
    role = make_role_call(spec)
    ctx = make_context(role)
    rule = RoleWithoutMetadataRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False


def test_L027_does_not_fire_for_task() -> None:
    from apme_engine.validators.native.rules._test_helpers import make_task_call, make_task_spec

    spec = make_task_spec(module="copy")
    task = make_task_call(spec)
    ctx = make_context(task)
    rule = RoleWithoutMetadataRule()
    assert not rule.match(ctx)
