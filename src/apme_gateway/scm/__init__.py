"""SCM provider abstraction for post-remediation PR creation (ADR-050).

This package defines the ``ScmProvider`` protocol and concrete provider
implementations.  Phase 1 ships with GitHub; Phase 2 adds GitLab and
Bitbucket via the same protocol.
"""

from apme_gateway.scm.base import PullRequestResult, ScmProvider, detect_provider
from apme_gateway.scm.registry import get_provider

__all__ = [
    "PullRequestResult",
    "ScmProvider",
    "detect_provider",
    "get_provider",
]
