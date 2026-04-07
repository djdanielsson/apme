"""SCM provider registry (ADR-050).

Maps provider identifiers to concrete implementations.  Phase 1 ships
only the GitHub provider; Phase 2 adds GitLab and Bitbucket.
"""

from __future__ import annotations

from apme_gateway.scm.base import ScmProvider
from apme_gateway.scm.github import GitHubProvider

_PROVIDERS: dict[str, type[ScmProvider]] = {
    "github": GitHubProvider,
}


def get_provider(provider_type: str, *, api_base_url: str | None = None) -> ScmProvider:
    """Resolve a provider instance by type identifier.

    Args:
        provider_type: One of ``github``, ``gitlab``, ``bitbucket``.
        api_base_url: Override the default API URL for the provider.

    Returns:
        A concrete ScmProvider instance.

    Raises:
        ValueError: If the provider type is not supported.
    """
    cls = _PROVIDERS.get(provider_type)
    if cls is None:
        supported = ", ".join(sorted(_PROVIDERS))
        msg = f"Unsupported SCM provider '{provider_type}'. Supported: {supported}"
        raise ValueError(msg)
    if api_base_url and provider_type == "github":
        return GitHubProvider(api_base_url=api_base_url)
    return cls()
