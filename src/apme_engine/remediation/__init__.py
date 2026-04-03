"""Remediation engine — graph-based convergence + AI escalation for scan violations."""

from apme_engine.remediation.ai_provider import AIProposal, AIProvider, AISkipped
from apme_engine.remediation.graph_engine import FilePatch, GraphFixReport
from apme_engine.remediation.partition import is_finding_resolvable
from apme_engine.remediation.registry import (
    TransformFn,
    TransformRegistry,
    TransformResult,
)

__all__ = [
    "AIProposal",
    "AIProvider",
    "AISkipped",
    "FilePatch",
    "GraphFixReport",
    "TransformFn",
    "TransformRegistry",
    "TransformResult",
    "is_finding_resolvable",
]
