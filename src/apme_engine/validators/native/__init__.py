"""ARI native validator: runs in-tree rules on context.scandata. Built-in rules in this package."""

import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from apme_engine.engine.risk_detector import detect
from apme_engine.validators.base import ScanContext

RULES_REQUIRING_ANSIBLE: tuple[str, ...] = ("P001", "P002", "P003", "P004")


@dataclass
class NativeRuleTiming:
    rule_id: str = ""
    elapsed_ms: float = 0.0
    violations: int = 0


@dataclass
class NativeRunResult:
    violations: list[dict[str, Any]] = field(default_factory=list)
    rule_timings: list[NativeRuleTiming] = field(default_factory=list)


def _default_rules_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "rules")


def _extract_results(data_report: dict[str, Any]) -> NativeRunResult:
    """Convert ARI detect() report to violations + per-rule timing."""
    violations: list[dict[str, Any]] = []
    timing_accum: dict[str, dict[str, float | int]] = defaultdict(lambda: {"elapsed_ms": 0.0, "violations": 0})

    ari_result = data_report.get("ari_result")
    if not ari_result or not hasattr(ari_result, "targets"):
        return NativeRunResult()

    for target in ari_result.targets:
        for node_result in getattr(target, "nodes", []) or []:
            for r in getattr(node_result, "rules", []) or []:
                rule_meta = getattr(r, "rule", None)
                rule_id = getattr(rule_meta, "rule_id", "") if rule_meta else ""
                duration_ms = getattr(r, "duration", 0.0) or 0.0

                timing_accum[rule_id]["elapsed_ms"] += duration_ms

                if not getattr(r, "verdict", False):
                    continue

                timing_accum[rule_id]["violations"] += 1

                severity = getattr(rule_meta, "severity", "") or "medium"
                description = getattr(rule_meta, "description", "") or ""
                detail = getattr(r, "detail", None)
                message = detail["message"] if isinstance(detail, dict) and detail.get("message") else description
                file_info = getattr(r, "file", None)
                if isinstance(file_info, (list, tuple)) and len(file_info) >= 1:
                    file_path = str(file_info[0]) if file_info[0] else ""
                    line = file_info[1] if len(file_info) > 1 else None
                else:
                    file_path = ""
                    line = None
                node = getattr(node_result, "node", None)
                path = ""
                if node and hasattr(node, "spec") and hasattr(node.spec, "key"):
                    path = getattr(node.spec, "key", "") or ""
                violations.append(
                    {
                        "rule_id": f"native:{rule_id}" if rule_id else "native:unknown",
                        "level": severity,
                        "message": message,
                        "file": file_path,
                        "line": line,
                        "path": path,
                    }
                )

    rule_timings = [
        NativeRuleTiming(
            rule_id=rid,
            elapsed_ms=v["elapsed_ms"],
            violations=int(v["violations"]),
        )
        for rid, v in sorted(timing_accum.items())
    ]
    return NativeRunResult(violations=violations, rule_timings=rule_timings)


class NativeValidator:
    """Validator that runs in-tree native (Python) rules on context.scandata (no second parse)."""

    def __init__(self, rules_dir: str = "", exclude_rule_ids: tuple[str, ...] | None = None) -> None:
        self._rules_dir = rules_dir or _default_rules_dir()
        self._exclude_rule_ids = (
            list(exclude_rule_ids) if exclude_rule_ids is not None else list(RULES_REQUIRING_ANSIBLE)
        )

    def run(self, context: ScanContext) -> list[dict[str, Any]]:
        """Run native rules on context.scandata; return list of violation dicts."""
        result = self.run_with_timing(context)
        return result.violations

    def run_with_timing(self, context: ScanContext) -> NativeRunResult:
        """Run native rules and return violations + per-rule timing."""
        scandata = context.scandata
        if not scandata:
            return NativeRunResult()
        contexts = getattr(scandata, "contexts", None) or []
        if not contexts:
            return NativeRunResult()
        if not os.path.isdir(self._rules_dir):
            return NativeRunResult()
        data_report, _ = detect(
            contexts,
            rules_dir=self._rules_dir,
            rules=[],
            rules_cache=[],
            save_only_rule_result=False,
            exclude_rule_ids=self._exclude_rule_ids,
        )
        return _extract_results(data_report)
