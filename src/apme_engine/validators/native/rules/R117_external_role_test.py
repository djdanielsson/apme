# Colocated tests for R117 (ExternalRoleRule).


from apme_engine.validators.native.rules._test_helpers import (
    make_context,
    make_role_call,
    make_role_spec,
)
from apme_engine.validators.native.rules.R117_external_role import ExternalRoleRule


def test_R117_fires_when_role_not_begin_and_has_galaxy_info() -> None:
    r1_spec = make_role_spec(name="internal", key="role role:internal")
    r2_spec = make_role_spec(
        name="external",
        key="role role:external",
        metadata={"galaxy_info": {"galaxy_api_url": "https://galaxy.ansible.com"}},
    )
    r1 = make_role_call(r1_spec)
    r2 = make_role_call(r2_spec)
    ctx = make_context(r2, sequence=[r1, r2])
    rule = ExternalRoleRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is True
    assert result.rule is not None and result.rule.rule_id == "R117"


def test_R117_does_not_fire_when_role_is_begin() -> None:
    spec = make_role_spec(
        name="external",
        metadata={"galaxy_info": {"galaxy_api_url": "https://galaxy.ansible.com"}},
    )
    role = make_role_call(spec)
    ctx = make_context(role, sequence=[role])
    rule = ExternalRoleRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False


def test_R117_does_not_fire_when_role_has_no_galaxy_info() -> None:
    r1_spec = make_role_spec(name="a", key="role role:a")
    r2_spec = make_role_spec(name="b", key="role role:b", metadata={})
    r1 = make_role_call(r1_spec)
    r2 = make_role_call(r2_spec)
    ctx = make_context(r2, sequence=[r1, r2])
    rule = ExternalRoleRule()
    assert rule.match(ctx)
    result = rule.process(ctx)
    assert result is not None
    assert result.verdict is False
