"""Validate CI workflow files for common hygiene issues.

Catches problems like deprecated action versions and unpinned image tags
before they cause CI failures in production.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
CONTAINERS_DIR = REPO_ROOT / "containers"

KNOWN_ACTION_MINIMUM_VERSIONS: dict[str, int] = {
    "actions/checkout": 6,
    "docker/setup-buildx-action": 4,
    "docker/login-action": 4,
    "docker/metadata-action": 6,
    "docker/build-push-action": 7,
}


def _parse_action_ref(uses: str) -> tuple[str, str]:
    """Split a 'uses' value into (action_name, ref).

    Args:
        uses: The full action reference string (e.g. 'actions/checkout@abc123 # v6').

    Returns:
        Tuple of (action_name, ref_or_sha).
    """
    comment_stripped = uses.split("#")[0].strip()
    if "@" not in comment_stripped:
        return comment_stripped, ""
    action, ref = comment_stripped.rsplit("@", 1)
    return action, ref.strip()


def _extract_version_comment(line: str) -> int | None:
    """Extract major version from a trailing # vN comment.

    Args:
        line: YAML line containing a uses directive.

    Returns:
        The major version number or None if no comment found.
    """
    match = re.search(r"#\s*v(\d+)", line)
    if match:
        return int(match.group(1))
    return None


def _collect_workflow_actions() -> list[tuple[Path, str, str, int | None]]:
    """Collect all action references from workflow files.

    Returns:
        List of (file_path, action_name, ref, version_from_comment) tuples.
    """
    results: list[tuple[Path, str, str, int | None]] = []
    if not WORKFLOWS_DIR.exists():
        return results

    for wf_path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        content = wf_path.read_text()
        lines = content.splitlines()
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- uses:") or stripped.startswith("uses:"):
                uses_value = stripped.split("uses:", 1)[1].strip()
                action, ref = _parse_action_ref(uses_value)
                version = _extract_version_comment(line)
                results.append((wf_path, action, ref, version))
    return results


@pytest.fixture  # type: ignore[untyped-decorator]
def workflow_actions() -> list[tuple[Path, str, str, int | None]]:
    """All action references found in workflow files.

    Returns:
        List of (path, action, ref, version) tuples.
    """
    return _collect_workflow_actions()


class TestActionVersions:
    """Ensure GitHub Actions are pinned to supported major versions."""

    def test_actions_pinned_to_sha(self, workflow_actions: list[tuple[Path, str, str, int | None]]) -> None:
        """All actions must be pinned to a full SHA, not a mutable tag.

        This prevents supply-chain attacks from tag re-pointing.

        Args:
            workflow_actions: Collected action references from workflows.
        """
        unpinned: list[str] = []
        for path, action, ref, _version in workflow_actions:
            if not action.startswith(".") and not re.match(r"^[0-9a-f]{40}$", ref):
                unpinned.append(f"{path.name}: {action}@{ref}")
        assert not unpinned, "Actions must be pinned to full SHA:\n" + "\n".join(unpinned)

    def test_actions_have_version_comments(self, workflow_actions: list[tuple[Path, str, str, int | None]]) -> None:
        """SHA-pinned actions must have a # vN comment for auditability.

        Args:
            workflow_actions: Collected action references from workflows.
        """
        missing_comments: list[str] = []
        for path, action, ref, version in workflow_actions:
            if action.startswith("."):
                continue
            if re.match(r"^[0-9a-f]{40}$", ref) and version is None:
                missing_comments.append(f"{path.name}: {action}@{ref[:12]}...")
        assert not missing_comments, "SHA-pinned actions need version comments (# vN):\n" + "\n".join(missing_comments)

    def test_actions_meet_minimum_versions(self, workflow_actions: list[tuple[Path, str, str, int | None]]) -> None:
        """Actions must meet minimum required major versions.

        This catches deprecated Node.js runtime issues before CI runs.

        Args:
            workflow_actions: Collected action references from workflows.
        """
        outdated: list[str] = []
        for path, action, _ref, version in workflow_actions:
            if action in KNOWN_ACTION_MINIMUM_VERSIONS and version is not None:
                min_ver = KNOWN_ACTION_MINIMUM_VERSIONS[action]
                if version < min_ver:
                    outdated.append(f"{path.name}: {action} is v{version}, minimum required is v{min_ver}")
        assert not outdated, "Actions below minimum supported versions:\n" + "\n".join(outdated)


class TestDockerfileImagePinning:
    """Ensure Dockerfiles use pinned image versions."""

    @pytest.fixture  # type: ignore[untyped-decorator]
    def dockerfiles(self) -> list[Path]:
        """All Dockerfiles in containers/.

        Returns:
            List of Dockerfile paths.
        """
        return sorted(CONTAINERS_DIR.glob("*/Dockerfile"))

    def test_no_latest_tags(self, dockerfiles: list[Path]) -> None:
        """FROM directives must not use :latest — pin to a specific version.

        Unpinned tags cause non-reproducible builds and intermittent failures
        when upstream images change or registry pulls become inconsistent.

        Args:
            dockerfiles: Paths to all Dockerfiles under containers/.
        """
        violations: list[str] = []
        for df in dockerfiles:
            content = df.read_text()
            for i, line in enumerate(content.splitlines(), 1):
                if re.match(r"^\s*FROM\s+\S+:latest(\s|$)", line):
                    violations.append(f"{df.relative_to(REPO_ROOT)}:{i}: {line.strip()}")
        assert not violations, "Dockerfiles must pin image versions (not :latest):\n" + "\n".join(violations)

    def test_no_untagged_images(self, dockerfiles: list[Path]) -> None:
        """FROM directives must specify a tag or use a build arg.

        Images without tags implicitly pull :latest.

        Args:
            dockerfiles: Paths to all Dockerfiles under containers/.
        """
        violations: list[str] = []
        for df in dockerfiles:
            content = df.read_text()
            for i, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                if not stripped.startswith("FROM "):
                    continue
                image_ref = stripped.split()[1]
                if image_ref.startswith("$"):
                    continue
                if ":" not in image_ref and "@" not in image_ref:
                    violations.append(f"{df.relative_to(REPO_ROOT)}:{i}: {stripped} (missing tag/digest)")
        assert not violations, "Dockerfiles must specify image tags:\n" + "\n".join(violations)
