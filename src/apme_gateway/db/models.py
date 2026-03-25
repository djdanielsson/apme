"""SQLAlchemy ORM models for gateway persistence (ADR-029, ADR-037).

The ``projects`` table is the top-level user-facing entity (ADR-037).
The ``sessions`` table remains for reporting-servicer compatibility with
CLI-initiated scans but is not exposed in user-facing APIs.
"""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):  # type: ignore[misc]
    """Declarative base for all gateway models."""


class Project(Base):
    """An SCM-backed project — the top-level user entity (ADR-037).

    Attributes:
        id: UUID hex primary key.
        name: User-facing display label.
        repo_url: HTTPS clone URL for the repository.
        branch: Branch to clone (default ``main``).
        created_at: ISO 8601 creation timestamp.
        health_score: Computed 0-100 health score from latest scan.
        scans: Related scan rows.
    """

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    repo_url: Mapped[str] = mapped_column(Text, nullable=False)
    branch: Mapped[str] = mapped_column(Text, nullable=False, default="main")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    health_score: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    scans: Mapped[list[Scan]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Session(Base):
    """A project session, keyed by the deterministic session_id hash.

    Attributes:
        session_id: Deterministic 16-char hex SHA-256 of the project root.
        project_path: Filesystem path of the scanned project.
        first_seen: ISO 8601 timestamp of the first event.
        last_seen: ISO 8601 timestamp of the most recent event.
        scans: Related scan rows.
    """

    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_path: Mapped[str] = mapped_column(Text, nullable=False)
    first_seen: Mapped[str] = mapped_column(Text, nullable=False)
    last_seen: Mapped[str] = mapped_column(Text, nullable=False)

    scans: Mapped[list[Scan]] = relationship(back_populates="session", cascade="all, delete-orphan")


class Scan(Base):
    """An individual scan or fix run.

    Attributes:
        scan_id: UUID of the scan run.
        session_id: Owning session hash (FK to sessions).
        project_id: Owning project UUID (FK to projects, nullable for CLI/playground).
        project_path: Project root path.
        source: Origin of the scan (cli, ci, gateway).
        trigger: How the scan was initiated (cli, ui, playground).
        created_at: ISO 8601 timestamp of creation.
        scan_type: Either "check" or "remediate".
        total_violations: Total violation count.
        auto_fixable: Count of tier-1 fixable violations.
        ai_candidate: Count of tier-2 AI-candidate violations.
        manual_review: Count of tier-3 manual violations.
        fixed_count: Number of violations fixed (fix scans only).
        ai_proposed: Count of AI proposals generated.
        ai_declined: Count of AI proposals declined.
        ai_accepted: Count of AI proposals accepted by the user.
        diagnostics_json: JSON-serialised ScanDiagnostics.
        session: Back-reference to owning Session.
        project: Back-reference to owning Project (ADR-037).
        violations: Related violation rows.
        proposals: Related proposal rows.
        logs: Related log rows.
        patches: Related patch rows (per-file diffs).
    """

    __tablename__ = "scans"

    scan_id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(Text, ForeignKey("sessions.session_id"), nullable=False)
    project_id: Mapped[str | None] = mapped_column(Text, ForeignKey("projects.id"), nullable=True)
    project_path: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="cli")
    trigger: Mapped[str] = mapped_column(Text, nullable=False, default="cli")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    scan_type: Mapped[str] = mapped_column(Text, nullable=False, default="check")
    total_violations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    auto_fixable: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_candidate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    manual_review: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fixed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_proposed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_declined: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_accepted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    diagnostics_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    session: Mapped[Session] = relationship(back_populates="scans")
    project: Mapped[Project | None] = relationship(back_populates="scans")
    violations: Mapped[list[Violation]] = relationship(back_populates="scan", cascade="all, delete-orphan")
    proposals: Mapped[list[Proposal]] = relationship(back_populates="scan", cascade="all, delete-orphan")
    logs: Mapped[list[ScanLog]] = relationship(back_populates="scan", cascade="all, delete-orphan")
    patches: Mapped[list[ScanPatch]] = relationship(back_populates="scan", cascade="all, delete-orphan")


class Violation(Base):
    """A single violation recorded during a scan.

    Attributes:
        id: Auto-increment primary key.
        scan_id: Owning scan UUID (FK to scans).
        rule_id: Rule identifier (e.g. L001).
        level: Severity level string.
        message: Human-readable violation description.
        file: Relative file path.
        line: Line number or None.
        path: YAML path within the file.
        remediation_class: Numeric remediation tier.
        scope: Numeric rule scope.
        scan: Back-reference to owning Scan.
    """

    __tablename__ = "violations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_id: Mapped[str] = mapped_column(Text, ForeignKey("scans.scan_id"), nullable=False)
    rule_id: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    file: Mapped[str] = mapped_column(Text, nullable=False, default="")
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    remediation_class: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scope: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    scan: Mapped[Scan] = relationship(back_populates="violations")


class Proposal(Base):
    """An AI proposal outcome from a fix session.

    Attributes:
        id: Auto-increment primary key.
        scan_id: Owning scan UUID (FK to scans).
        proposal_id: Engine-generated proposal UUID.
        rule_id: Rule that triggered the proposal.
        file: File the proposal targets.
        tier: Proposal tier (2 or 3).
        confidence: AI confidence score (0.0-1.0).
        status: Outcome (approved, rejected, pending).
        scan: Back-reference to owning Scan.
    """

    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_id: Mapped[str] = mapped_column(Text, ForeignKey("scans.scan_id"), nullable=False)
    proposal_id: Mapped[str] = mapped_column(Text, nullable=False)
    rule_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    file: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")

    scan: Mapped[Scan] = relationship(back_populates="proposals")


class ScanLog(Base):
    """A structured log entry from the scan pipeline (ADR-033).

    Attributes:
        id: Auto-increment primary key.
        scan_id: Owning scan UUID (FK to scans).
        message: Log message text.
        phase: Pipeline subsystem (engine, native, opa, etc.).
        progress: Progress fraction 0.0-1.0.
        level: Numeric log level.
        scan: Back-reference to owning Scan.
    """

    __tablename__ = "scan_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_id: Mapped[str] = mapped_column(Text, ForeignKey("scans.scan_id"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    phase: Mapped[str] = mapped_column(Text, nullable=False, default="")
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    scan: Mapped[Scan] = relationship(back_populates="logs")


class ScanPatch(Base):
    """A per-file diff produced during a check or remediate operation.

    Attributes:
        id: Auto-increment primary key.
        scan_id: Owning scan UUID (FK to scans).
        file: Relative file path.
        diff: Unified diff text.
        scan: Back-reference to owning Scan.
    """

    __tablename__ = "scan_patches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_id: Mapped[str] = mapped_column(Text, ForeignKey("scans.scan_id"), nullable=False)
    file: Mapped[str] = mapped_column(Text, nullable=False)
    diff: Mapped[str] = mapped_column(Text, nullable=False, default="")

    scan: Mapped[Scan] = relationship(back_populates="patches")
