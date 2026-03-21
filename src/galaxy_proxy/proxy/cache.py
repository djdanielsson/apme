"""Wheel and metadata cache backed by XDG_CACHE_HOME."""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


def _default_cache_dir() -> Path:
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "ansible-collection-proxy"


@dataclass
class CachedMetadata:
    """Cached Galaxy version listing for a collection.

    Attributes:
        versions: Available collection version strings from Galaxy.
        fetched_at: Unix timestamp when the listing was fetched.
    """

    versions: list[str]
    fetched_at: float


class ProxyCache:
    """Manages cached wheels and version metadata on disk."""

    def __init__(self, cache_dir: Path | None = None, metadata_ttl: float = 600.0) -> None:
        """Initialise cache directories under *cache_dir* (or XDG default).

        Args:
            cache_dir: Root directory for cached data. If None, uses XDG cache default.
            metadata_ttl: Seconds before cached metadata is considered stale.
        """
        self.root = cache_dir or _default_cache_dir()
        self.wheels_dir = self.root / "wheels"
        self.metadata_dir = self.root / "metadata"
        self.metadata_ttl = metadata_ttl

        self.wheels_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, base: Path, filename: str) -> Path:
        """Resolve a filename under base, rejecting traversal attempts.

        Args:
            base: Base directory the file must reside under.
            filename: Untrusted filename to resolve.

        Returns:
            Resolved path confirmed to be under base.

        Raises:
            ValueError: When the resolved path escapes the base directory.
        """
        resolved = (base / filename).resolve()
        if not resolved.is_relative_to(base.resolve()):
            msg = f"Path escapes cache directory: {filename!r}"
            raise ValueError(msg)
        return resolved

    def get_wheel(self, filename: str) -> bytes | None:
        """Return cached wheel bytes, or None if not cached.

        Args:
            filename: Wheel filename under the wheels cache directory.

        Returns:
            Cached wheel bytes, or None if the file is not present.
        """
        path = self._safe_path(self.wheels_dir, filename)
        if path.exists():
            return path.read_bytes()
        return None

    def put_wheel(self, filename: str, data: bytes) -> Path:
        """Write a wheel to the cache atomically and return its path.

        Args:
            filename: Destination filename under the wheels cache.
            data: Raw wheel bytes to write.

        Returns:
            Path to the written wheel file.

        Raises:
            OSError: When the temporary file cannot be written or renamed.
        """
        path = self._safe_path(self.wheels_dir, filename)
        fd, tmp = tempfile.mkstemp(dir=self.wheels_dir, suffix=".tmp")
        tmp_path = Path(tmp)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            tmp_path.rename(path)
        except OSError:
            tmp_path.unlink(missing_ok=True)
            raise
        return path

    def wheel_path(self, filename: str) -> Path | None:
        """Return the path to a cached wheel if it exists.

        Args:
            filename: Wheel filename to look up.

        Returns:
            Path to the cached file, or None if it does not exist.
        """
        path = self._safe_path(self.wheels_dir, filename)
        return path if path.exists() else None

    def get_metadata(self, namespace: str, name: str) -> CachedMetadata | None:
        """Return cached version listing if fresh, None otherwise.

        Args:
            namespace: Collection namespace.
            name: Collection name.

        Returns:
            Cached metadata if found and within TTL, otherwise None.
        """
        path = self.metadata_dir / f"{namespace}-{name}.json"
        if not path.exists():
            return None

        data = json.loads(path.read_text())
        cached = CachedMetadata(
            versions=data["versions"],
            fetched_at=data["fetched_at"],
        )

        age = time.time() - cached.fetched_at
        if age > self.metadata_ttl:
            return None

        return cached

    def put_metadata(self, namespace: str, name: str, versions: list[str]) -> None:
        """Cache a version listing for a collection.

        Args:
            namespace: Collection namespace.
            name: Collection name.
            versions: Version strings to persist.
        """
        path = self.metadata_dir / f"{namespace}-{name}.json"
        data = {
            "versions": versions,
            "fetched_at": time.time(),
        }
        path.write_text(json.dumps(data, indent=2))

    def clear(self) -> None:
        """Remove all cached files."""
        import shutil

        if self.root.exists():
            shutil.rmtree(self.root)
        self.wheels_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
