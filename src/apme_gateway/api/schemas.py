"""Pydantic response models for the REST API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SessionSummary(BaseModel):  # type: ignore[misc]
    """Session list item.

    Attributes:
        session_id: Deterministic project hash.
        project_path: Filesystem path of the project.
        first_seen: ISO 8601 timestamp of first event.
        last_seen: ISO 8601 timestamp of most recent event.
    """

    session_id: str
    project_path: str
    first_seen: str
    last_seen: str


class ScanSummary(BaseModel):  # type: ignore[misc]
    """Scan list item.

    Attributes:
        scan_id: UUID of the scan run.
        session_id: Owning session hash.
        project_path: Project root path.
        source: Origin of the scan (cli, ci, gateway).
        created_at: ISO 8601 timestamp.
        scan_type: Either "scan" or "fix".
        total_violations: Total violation count.
        auto_fixable: Count of tier-1 fixable violations.
        ai_candidate: Count of tier-2 AI-candidate violations.
        manual_review: Count of tier-3 manual violations.
        fixed_count: Number of violations fixed (fix scans only).
    """

    scan_id: str
    session_id: str
    project_path: str
    source: str
    created_at: str
    scan_type: str
    total_violations: int
    auto_fixable: int
    ai_candidate: int
    manual_review: int
    fixed_count: int = 0


class ViolationDetail(BaseModel):  # type: ignore[misc]
    """Violation row.

    Attributes:
        id: Auto-increment ID.
        rule_id: Rule identifier (e.g. L001).
        level: Severity level string.
        message: Human-readable description.
        file: Relative file path.
        line: Line number or None.
        path: YAML path within the file.
        remediation_class: Numeric remediation tier.
        scope: Numeric rule scope.
    """

    id: int
    rule_id: str
    level: str
    message: str
    file: str
    line: int | None
    path: str
    remediation_class: int
    scope: int


class ProposalDetail(BaseModel):  # type: ignore[misc]
    """Proposal row.

    Attributes:
        id: Auto-increment ID.
        proposal_id: Engine-generated proposal UUID.
        rule_id: Rule that triggered the proposal.
        file: File the proposal targets.
        tier: Proposal tier (2 or 3).
        confidence: AI confidence score.
        status: approved, rejected, or pending.
    """

    id: int
    proposal_id: str
    rule_id: str
    file: str
    tier: int
    confidence: float
    status: str


class LogEntry(BaseModel):  # type: ignore[misc]
    """Pipeline log entry.

    Attributes:
        id: Auto-increment ID.
        message: Log message text.
        phase: Pipeline subsystem.
        progress: Progress fraction 0.0-1.0.
        level: Numeric log level.
    """

    id: int
    message: str
    phase: str
    progress: float
    level: int


class ScanDetail(BaseModel):  # type: ignore[misc]
    """Full scan with violations, proposals, and logs.

    Attributes:
        scan_id: UUID of the scan run.
        session_id: Owning session hash.
        project_path: Project root path.
        source: Origin of the scan.
        created_at: ISO 8601 timestamp.
        scan_type: Either "scan" or "fix".
        total_violations: Total violation count.
        auto_fixable: Count of tier-1 fixable violations.
        ai_candidate: Count of tier-2 AI-candidate violations.
        manual_review: Count of tier-3 manual violations.
        fixed_count: Number of violations fixed (fix scans only).
        diagnostics_json: Raw diagnostics JSON string.
        violations: List of violation rows.
        proposals: List of proposal rows.
        logs: List of log entries.
    """

    scan_id: str
    session_id: str
    project_path: str
    source: str
    created_at: str
    scan_type: str
    total_violations: int
    auto_fixable: int
    ai_candidate: int
    manual_review: int
    fixed_count: int = 0
    diagnostics_json: str | None
    violations: list[ViolationDetail]
    proposals: list[ProposalDetail]
    logs: list[LogEntry]


class SessionDetail(BaseModel):  # type: ignore[misc]
    """Session with its scans.

    Attributes:
        session_id: Deterministic project hash.
        project_path: Filesystem path.
        first_seen: First event timestamp.
        last_seen: Most recent event timestamp.
        scans: List of scans in this session.
    """

    session_id: str
    project_path: str
    first_seen: str
    last_seen: str
    scans: list[ScanSummary]


class TopViolation(BaseModel):  # type: ignore[misc]
    """Top-violated rule.

    Attributes:
        rule_id: Rule identifier.
        count: Number of times the rule was violated.
    """

    rule_id: str
    count: int


class TrendPoint(BaseModel):  # type: ignore[misc]
    """Violation trend data point for a session.

    Attributes:
        scan_id: UUID of the scan run.
        created_at: ISO 8601 timestamp.
        total_violations: Total violation count.
        auto_fixable: Count of auto-fixable violations.
        scan_type: Either "scan" or "fix".
    """

    scan_id: str
    created_at: str
    total_violations: int
    auto_fixable: int
    scan_type: str


class FixRateEntry(BaseModel):  # type: ignore[misc]
    """Fix frequency for a specific rule.

    Attributes:
        rule_id: Rule identifier.
        fix_count: Number of times this rule appeared in fix scans.
    """

    rule_id: str
    fix_count: int


class AiAcceptanceEntry(BaseModel):  # type: ignore[misc]
    """AI proposal acceptance statistics per rule.

    Attributes:
        rule_id: Rule identifier.
        approved: Count of approved proposals.
        rejected: Count of rejected proposals.
        pending: Count of pending proposals.
        avg_confidence: Average AI confidence score.
    """

    rule_id: str
    approved: int
    rejected: int
    pending: int
    avg_confidence: float


class PaginatedResponse(BaseModel):  # type: ignore[misc]
    """Wrapper for paginated list responses.

    Attributes:
        total: Total number of items matching the query.
        limit: Page size.
        offset: Current offset.
        items: List of result items.
    """

    total: int
    limit: int
    offset: int
    items: list[SessionSummary] | list[ScanSummary] | list[TopViolation] | list[ProjectSummary]


class AiModelInfo(BaseModel):  # type: ignore[misc]
    """AI model available from the Abbenay daemon.

    Attributes:
        id: Model identifier (e.g. ``anthropic/claude-sonnet-4``).
        provider: LLM provider engine name.
        name: Human-readable model name.
    """

    id: str
    provider: str
    name: str


class ComponentHealth(BaseModel):  # type: ignore[misc]
    """Health status for a single service component.

    Attributes:
        name: Human-readable component name.
        status: Health status (ok, unavailable, or degraded).
        address: Network address of the component.
    """

    name: str
    status: str
    address: str


class HealthStatus(BaseModel):  # type: ignore[misc]
    """Gateway health response.

    Attributes:
        status: Overall health (ok or degraded).
        database: Database connectivity status.
        components: Health status of each upstream service.
    """

    status: str
    database: str
    components: list[ComponentHealth] = Field(default_factory=list)


# ── Project schemas (ADR-037) ────────────────────────────────────────


class ProjectSummary(BaseModel):  # type: ignore[misc]
    """Summary representation of a project for list views.

    Attributes:
        id: Unique identifier.
        name: Display label.
        repo_url: SCM clone URL.
        branch: Target branch.
        created_at: ISO-8601 creation timestamp.
        health_score: Computed 0-100 score.
        total_violations: Count from latest scan.
        violation_trend: Direction indicator.
        scan_count: Number of completed scans.
        last_scanned_at: ISO timestamp of most recent scan.
    """

    id: str
    name: str
    repo_url: str
    branch: str
    created_at: str
    health_score: int
    total_violations: int = 0
    violation_trend: str = "stable"
    scan_count: int = 0
    last_scanned_at: str | None = None


class ProjectDetail(ProjectSummary):
    """Full project representation with latest scan detail.

    Attributes:
        latest_scan: Summary of the most recent scan, if any.
        severity_breakdown: Violation counts keyed by severity level.
    """

    latest_scan: ScanSummary | None = None
    severity_breakdown: dict[str, int] = Field(default_factory=dict)


class CreateProjectRequest(BaseModel):  # type: ignore[misc]
    """Request body for creating a project.

    Attributes:
        name: Display label.
        repo_url: HTTPS clone URL.
        branch: Branch to clone (default main).
    """

    name: str
    repo_url: str
    branch: str = "main"


class UpdateProjectRequest(BaseModel):  # type: ignore[misc]
    """Partial update for project fields.

    Attributes:
        name: New display label.
        repo_url: New clone URL.
        branch: New branch.
    """

    name: str | None = None
    repo_url: str | None = None
    branch: str | None = None


class ScanRequestOptions(BaseModel):  # type: ignore[misc]
    """Per-operation scan/fix options (ADR-037).

    Attributes:
        ansible_version: Target ansible-core version.
        collection_specs: Galaxy collection install specs.
        enable_ai: Enable AI remediation tier.
        ai_model: Specific model identifier.
    """

    ansible_version: str = ""
    collection_specs: list[str] = Field(default_factory=list)
    enable_ai: bool = False
    ai_model: str = ""


class DashboardSummary(BaseModel):  # type: ignore[misc]
    """Cross-project aggregate statistics (ADR-037).

    Attributes:
        total_projects: Number of defined projects.
        total_scans: Number of completed scans across all projects.
        total_violations: Cumulative violations across all scans.
        current_violations: Violations from each project's latest scan.
        total_fixed: Sum of auto-fixable violations.
        avg_health_score: Mean health score across projects.
    """

    total_projects: int
    total_scans: int
    total_violations: int
    current_violations: int
    total_fixed: int
    avg_health_score: int


class ProjectRanking(BaseModel):  # type: ignore[misc]
    """Project ranking entry for dashboard tables (ADR-037).

    Attributes:
        id: Project identifier.
        name: Display label.
        health_score: Computed 0-100 score.
        total_violations: Latest scan violation count.
        scan_count: Number of completed scans.
        last_scanned_at: ISO timestamp of most recent scan.
        days_since_last_scan: Age in days since last scan.
    """

    id: str
    name: str
    health_score: int
    total_violations: int
    scan_count: int
    last_scanned_at: str | None = None
    days_since_last_scan: int | None = None
