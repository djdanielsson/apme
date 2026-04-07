"""ScmProvider protocol and shared types (ADR-050)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse


@dataclass(frozen=True)
class PullRequestResult:
    """Result of a successful PR creation.

    Attributes:
        pr_url: Web URL of the newly created pull request.
        branch_name: Name of the head branch that was created.
        provider: SCM provider identifier (e.g. ``github``).
    """

    pr_url: str
    branch_name: str
    provider: str


class ScmProvider(Protocol):
    """Protocol for SCM platform integrations (ADR-050).

    Each method receives an explicit *token* so the caller controls
    hierarchical token resolution (project → global fallback).
    """

    async def create_branch(
        self,
        repo_url: str,
        base_branch: str,
        new_branch: str,
        token: str,
    ) -> None:
        """Create a new branch from the tip of *base_branch*.

        Args:
            repo_url: HTTPS clone URL of the repository.
            base_branch: Branch to fork from.
            new_branch: Name for the new branch.
            token: Authentication token.
        """
        ...

    async def push_files(
        self,
        repo_url: str,
        branch: str,
        files: dict[str, bytes],
        commit_message: str,
        token: str,
    ) -> str:
        """Push file contents to *branch* and return the commit SHA.

        Args:
            repo_url: HTTPS clone URL of the repository.
            branch: Target branch (must already exist).
            files: Mapping of relative path → file content.
            commit_message: Commit message for the push.
            token: Authentication token.

        Returns:
            The SHA of the new commit.
        """
        ...

    async def create_pull_request(
        self,
        repo_url: str,
        base_branch: str,
        head_branch: str,
        title: str,
        body: str,
        token: str,
    ) -> PullRequestResult:
        """Open a pull request from *head_branch* into *base_branch*.

        Args:
            repo_url: HTTPS clone URL of the repository.
            base_branch: Target branch for the PR.
            head_branch: Source branch with changes.
            title: PR title.
            body: PR body (Markdown).
            token: Authentication token.

        Returns:
            PullRequestResult with the PR URL.
        """
        ...


_PROVIDER_HOSTS: dict[str, str] = {
    "github.com": "github",
    "gitlab.com": "gitlab",
    "bitbucket.org": "bitbucket",
}


def detect_provider(repo_url: str) -> str | None:
    """Infer the SCM provider from a repository URL.

    Args:
        repo_url: HTTPS clone URL.

    Returns:
        Provider identifier or None if unrecognised.
    """
    try:
        host = urlparse(repo_url).hostname or ""
    except Exception:
        return None
    host = host.lower()
    for known, provider in _PROVIDER_HOSTS.items():
        if host == known or host.endswith("." + known):
            return provider
    return None
