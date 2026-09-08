"""Unit tests for SubmitRequest branch-name validation (finding #44)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from apme_gateway.api.schemas import SubmitRequest


def test_branch_name_defaults_to_none() -> None:
    """Omitted branch_name selects the auto-generated default."""
    assert SubmitRequest().branch_name is None


@pytest.mark.parametrize(  # type: ignore[untyped-decorator]
    "name",
    [
        "apme/remediate-abc123",
        "feature/my-fix_2.0",
        "release-1",
    ],
)
def test_branch_name_accepts_safe_names(name: str) -> None:
    """Safe branch names validate unchanged."""
    assert SubmitRequest(branch_name=name).branch_name == name


@pytest.mark.parametrize(  # type: ignore[untyped-decorator]
    "name",
    [
        "",
        "   ",
        "../escape",
        "a/b/../../c",
        "has space",
        "semi;colon",
        "x" * 101,
        "back\\slash",
    ],
)
def test_branch_name_rejects_unsafe_names(name: str) -> None:
    """Traversal, blank, overlong, and out-of-charset names fail with 422-shape errors."""
    with pytest.raises(ValidationError):
        SubmitRequest(branch_name=name)
