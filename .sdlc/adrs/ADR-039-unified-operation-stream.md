# ADR-039: Unified Operation Stream — Check and Remediate

## Status

Implemented

## Date

2026-03-24

## Context

### Divergent scan paths produce inconsistent results

APME had two separate gRPC RPCs for analyzing content:

1. **`ScanStream`** (ADR-024): streams raw file bytes, runs `_scan_pipeline`
   once, classifies violations, returns `ScanResponse` with a `ScanSummary`.

2. **`FixSession`** (ADR-028): streams file bytes wrapped in `SessionCommand`,
   **formats files first** (YAML normalization), then runs a
   `RemediationEngine` convergence loop with Tier 1 transforms.

The formatting step in `FixSession` normalizes content before scanning, which
can expose violations that raw content does not trigger. Identical repository
content produces different violation counts depending on which RPC is called.

| Aspect | ScanStream / Scan (removed) | FixSession |
|--------|-----------|------------|
| Format files first | No | Yes |
| Scan passes | 1 | N (convergence loop) |
| Tier 1 transforms | No | Yes |
| AI proposals | No | Yes (if enabled) |
| Result type | `SessionResult` (via check mode) | `SessionResult` |

### User mental model: check = remediate without the remediation

Users expect that **checking** a project and then **remediating** it should
report the same violations. The only difference should be whether remediation
is applied — not whether formatting occurs or how many scan passes run.

This led to reframing the two operations as:

- **Check** — full Tier 1 pipeline in dry-run mode. Format, run convergence
  loop, classify remaining violations. Reports what *would* be fixed.
- **Remediate** — same pipeline with changes applied, plus optional AI
  proposals and persistence.

This mirrors established conventions: Ansible `--check`, Terraform `plan/apply`.

### Terminology rename

| Old term | New term | Scope |
|----------|----------|-------|
| scan | check | CLI, UI, API routes, WebSocket protocol |
| fix | remediate | CLI, UI, API routes, WebSocket protocol |
| Scans (history) | Activity | UI navigation, API routes |
| scan_type="scan" | scan_type="check" | DB values (new records) |
| scan_type="fix" | scan_type="remediate" | DB values (new records) |

DB column names (`scan_id`, `scan_type`, `scans` table) are unchanged to
avoid migration. Queries accept both old and new values for backward
compatibility with existing data.

## Decision

### 1. `FixSession` is the single code path

Both check and remediate use `FixSession` gRPC. The distinction is whether
`fix_options` are attached to the first chunk:

- **Check mode** (`remediate=False`): no `fix_options`. The engine's
  `_session_process` runs format → Tier 1 convergence loop → classify →
  report. Without an AI provider, no proposals are generated and the session
  completes immediately.

- **Remediate mode** (`remediate=True`): `FixOptions` attached. Full Tier 1
  convergence loop applies transforms, followed by optional AI proposals and
  approval flow.

### 2. Legacy scan RPCs and reporting events removed

`ScanStream`, the unary `Scan` RPC, `ScanRequest`, `ScanResponse`, and
`ScanEvent` message types are all removed from the proto and server
implementation. On the reporting side, `ScanCompletedEvent` and
`ReportScanCompleted` are removed — the engine emits only
`FixCompletedEvent` via `ReportFixCompleted` for both check and remediate
operations. Clients must use `FixSession` without `fix_options` for check
mode.

### 3. CLI: `apme check` and `apme remediate`

- `apme check` replaces `apme scan`. Uses `FixSession` without `fix_options`.
  Reports violations with auto-fixable, AI-candidate, and manual-review counts.
- `apme remediate` replaces `apme fix`. Uses `FixSession` with `FixOptions`.
- No backward-compatible aliases (`scan`/`fix` are removed).

### 4. Gateway: single `run_project_operation` driver

`run_project_scan` and `run_project_fix` are merged into
`run_project_operation(remediate=bool)`. Both always use `FixSession` gRPC.
The WebSocket handler uses `remediate` instead of `fix` in the protocol.

### 5. API routes: `/scans` → `/activity`

- `GET /activity` — list all activity records
- `GET /activity/{id}` — activity detail
- `DELETE /activity/{id}` — delete activity record
- `GET /projects/{id}/activity` — project activity
- `GET /stats/remediation-rates` replaces `/stats/fix-rates`

### 6. Frontend

- `ScanSummary` → `ActivitySummary`, `ScanDetail` → `ActivityDetail`
- `ScansPage` → `ActivityPage`, `ScanDetailPage` → `ActivityDetailPage`
- Navigation: "Activity" replaces "Scans" in sidebar
- Buttons: "Check" / "Remediate" replace "Scan" / "Scan & Fix"
- `ScanOptionsForm` → `CheckOptionsForm`

## Consequences

### Positive

- **Consistent results**: check and remediate report the same violations
  because both paths format first and run the full Tier 1 convergence loop.
- **Single code path**: `ScanStream` implementation replaced by delegation;
  gateway driver deduplicated.
- **Intuitive terminology**: "check" and "remediate" align with established
  tool conventions and clearly communicate intent.
- **Check reports fixability**: check results include auto-fixable,
  AI-candidate, and manual-review counts — users know what remediation
  would accomplish before running it.
- **No DB migration**: column names unchanged.

### Negative

- **Check is slightly slower**: running the full Tier 1 convergence loop adds
  overhead vs. a single scan pass. In practice this is small for typical
  projects and the consistency benefit outweighs the cost.
- **Legacy scan RPC removal is a breaking change**: existing clients using
  `ScanStream` or the unary `Scan` RPC must migrate to `FixSession` without
  `fix_options`. Clients consuming `ScanCompletedEvent` via the Reporting
  service must switch to `FixCompletedEvent`.
- **Old DB data invisible**: existing records with `scan_type` "scan"/"fix"
  will not appear in queries that filter on "check"/"remediate".

## References

- ADR-024: CLI as thin gRPC client
- ADR-028: Session-based fix workflow with bidirectional streaming
- ADR-036: Two-pass remediation engine
- ADR-037: Project-centric UI model
