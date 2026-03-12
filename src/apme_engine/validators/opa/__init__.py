"""OPA validator: runs Rego policy on hierarchy payload. Built-in bundle in this package."""

from __future__ import annotations

import os
from typing import Any

from apme_engine.opa_client import run_opa
from apme_engine.validators.base import ScanContext


def _default_bundle_path() -> str:
    return os.path.join(os.path.dirname(__file__), "bundle")


class OpaValidator:
    """Validator that runs OPA eval on context.hierarchy_payload."""

    def __init__(
        self,
        bundle_path: str | None = None,
        entrypoint: str = "data.apme.rules.violations",
    ):
        self.bundle_path = bundle_path or _default_bundle_path()
        self.entrypoint = entrypoint

    def run(self, context: ScanContext) -> list[dict[str, Any]]:
        """Run OPA on hierarchy_payload; return list of violation dicts."""
        return run_opa(
            context.hierarchy_payload,
            self.bundle_path,
            entrypoint=self.entrypoint,
        )
