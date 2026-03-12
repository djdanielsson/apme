"""Ansible validator: runs checks that require an ansible-core runtime (venv).

Rules are colocated under rules/ and follow the same pattern as native and OPA validators.
Each rule module exports a run() function that returns a list of violation dicts.
"""

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from apme_engine.validators.base import ScanContext

from .rules import L057_syntax, L058_argspec_doc, L059_argspec_mock, M001_M004_introspect


@dataclass
class AnsibleRuleTiming:
    rule_id: str = ""
    elapsed_ms: float = 0.0
    violations: int = 0


@dataclass
class AnsibleRunResult:
    violations: list[dict[str, Any]] = field(default_factory=list)
    rule_timings: list[AnsibleRuleTiming] = field(default_factory=list)


def _extract_task_nodes(hierarchy_payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract all taskcall nodes from the hierarchy payload."""
    nodes = []
    for tree in hierarchy_payload.get("hierarchy", []):
        for node in tree.get("nodes", []):
            if node.get("type") == "taskcall":
                nodes.append(node)
    return nodes


class AnsibleValidator:
    """Validator that runs ansible-core checks via pre-built venvs.

    Rules:
      L057 - Syntax check (ansible-playbook --syntax-check)
      L058 - Argspec validation (docstring-based)
      L059 - Argspec validation (mock/patch-based)
      M001 - FQCN resolution
      M002 - Deprecated module
      M003 - Module redirect
      M004 - Removed/tombstoned module
    """

    def __init__(
        self,
        venv_root: Path,
        env_extra: dict[str, str] | None = None,
    ):
        self._venv_root = venv_root
        self._env_extra = env_extra

    def run(self, context: ScanContext) -> list[dict[str, Any]]:
        """Run all ansible checks and return violation dicts."""
        return self.run_with_timing(context).violations

    def run_with_timing(self, context: ScanContext) -> AnsibleRunResult:
        """Run all ansible checks and return violations + per-rule timing."""
        violations: list[dict[str, Any]] = []
        rule_timings: list[AnsibleRuleTiming] = []
        root_dir = Path(context.root_dir) if context.root_dir else None

        if root_dir and root_dir.is_dir():
            t0 = time.monotonic()
            l057 = L057_syntax.run(
                venv_root=self._venv_root,
                root_dir=root_dir,
                env_extra=self._env_extra,
            )
            elapsed = (time.monotonic() - t0) * 1000
            violations.extend(l057)
            rule_timings.append(AnsibleRuleTiming(rule_id="L057", elapsed_ms=elapsed, violations=len(l057)))
            sys.stderr.write(f"  L057 (syntax): {len(l057)} issue(s) in {elapsed:.1f}ms\n")

        task_nodes = _extract_task_nodes(context.hierarchy_payload) if context.hierarchy_payload else []
        if not task_nodes:
            sys.stderr.write(f"Ansible validator: total {len(violations)} violation(s)\n")
            sys.stderr.flush()
            return AnsibleRunResult(violations=violations, rule_timings=rule_timings)

        sys.stderr.write(f"Ansible validator: checking {len(task_nodes)} task(s)\n")

        t0 = time.monotonic()
        m_violations = M001_M004_introspect.run(
            task_nodes=task_nodes,
            venv_root=self._venv_root,
            env_extra=self._env_extra,
        )
        elapsed = (time.monotonic() - t0) * 1000
        violations.extend(m_violations)
        rule_timings.append(AnsibleRuleTiming(rule_id="M001-M004", elapsed_ms=elapsed, violations=len(m_violations)))
        sys.stderr.write(f"  M001-M004 (introspection): {len(m_violations)} issue(s) in {elapsed:.1f}ms\n")

        t0 = time.monotonic()
        l058 = L058_argspec_doc.run(
            task_nodes=task_nodes,
            venv_root=self._venv_root,
            env_extra=self._env_extra,
        )
        elapsed = (time.monotonic() - t0) * 1000
        violations.extend(l058)
        rule_timings.append(AnsibleRuleTiming(rule_id="L058", elapsed_ms=elapsed, violations=len(l058)))
        sys.stderr.write(f"  L058 (argspec-doc): {len(l058)} issue(s) in {elapsed:.1f}ms\n")

        t0 = time.monotonic()
        l059 = L059_argspec_mock.run(
            task_nodes=task_nodes,
            venv_root=self._venv_root,
            env_extra=self._env_extra,
        )
        elapsed = (time.monotonic() - t0) * 1000
        violations.extend(l059)
        rule_timings.append(AnsibleRuleTiming(rule_id="L059", elapsed_ms=elapsed, violations=len(l059)))
        sys.stderr.write(f"  L059 (argspec-mock): {len(l059)} issue(s) in {elapsed:.1f}ms\n")

        sys.stderr.write(f"Ansible validator: total {len(violations)} violation(s)\n")
        sys.stderr.flush()
        return AnsibleRunResult(violations=violations, rule_timings=rule_timings)
