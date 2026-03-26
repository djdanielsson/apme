# APME Agent Configurations

This document defines the specialized agents used in APME development. It is the
operational companion to `CLAUDE.md` (the project constitution). Read both before
touching code.

**User-facing CLI (binary remains `apme-scan`):** **`check`** for assessment, **`remediate`** for applying fixes. Both use the bidirectional `FixSession` RPC under the hood (ADR-039). The **Engine Agent** below owns the internal scan pipeline; that is not the same as the CLI subcommand name.

## Architectural Invariants

These are non-negotiable. Violating any of them will break the system or create
debt that compounds across services. Do **not** work around them — if you think
one needs to change, write an ADR first.

1. **Validators are read-only** (ADR-009). Validators detect; they never modify
   files. Remediation is a separate engine with its own convergence loop.
   The one planned exception is third-party plugins (ADR-042), which may
   implement `Transform` — but that is explicitly scoped outside built-in
   validators and requires its own ADR approval.

2. **gRPC everywhere between backend services** (ADR-001). No REST, no message
   queues, no direct function calls between services. The only HTTP endpoints
   are Galaxy Proxy (PEP 503) and Gateway REST (for the UI/external consumers).

3. **Async servers with executor discipline** (ADR-007). All gRPC servers use
   `grpc.aio`. Blocking work (engine scan, subprocess calls, venv builds) goes
   through `run_in_executor()`. Never block the event loop.

4. **Unified Validator contract** (`validate.proto`). Every validator implements
   `Validator.Validate` + `Validator.Health`. Adding a validator means
   implementing one RPC and setting an env var — not changing Primary's code.

5. **Stateless engine, persistence at the edge** (ADR-020, ADR-029). The engine
   pod has zero database code. Persistence lives in the Gateway (SQLAlchemy +
   SQLite). The `GrpcReportingSink` is best-effort and health-gated — the scan
   path never blocks on reporting.

6. **Scale pods, not individual services** (ADR-012). One pod = full stack
   (Primary + validators + Galaxy Proxy). Horizontal scaling replicates the
   entire pod. Do not extract individual validators into separate deployments.

7. **Session venvs are Primary-owned** (ADR-022). Primary is the single writer
   to `/sessions`. Ansible validator mounts it read-only. No other service
   writes to venvs.

8. **Rule IDs follow ADR-008**: `L` = Lint, `M` = Modernize, `R` = Risk,
   `P` = Policy, `SEC` = Secrets (via Gitleaks). Plugin rules use `EXT-` prefix
   (ADR-042).

9. **OPA uses subprocess, not REST** (verified in code). The OPA validator
   invokes `opa eval` via subprocess — there is no OPA REST server on 8181.
   Do not introduce httpx or HTTP client dependencies for OPA.

10. **`FixSession` is the unified client path** (ADR-039). Both `check` and
    `remediate` use the bidirectional `FixSession` RPC. The unary `Scan` RPC
    exists for backward-compatible engine-aligned clients only. New features
    target `FixSession`.

## Agent Roles

### 1. Spec Writer Agent

**Purpose**: Creates and maintains specification documents.

**Context Files**:
- `CLAUDE.md`
- `.sdlc/templates/requirement.md`
- `.sdlc/templates/task.md`
- `.sdlc/context/project-overview.md`
- `.sdlc/context/workflow.md`

**Capabilities**:
- Write requirement specifications
- Create task breakdowns
- Draft architecture decision records
- Ensure spec completeness and traceability

**Constraints**:
- Must use templates from `.sdlc/templates/`
- Must link related specs (REQ -> TASK -> ADR/DR)
- Must include acceptance criteria
- Must verify phase assignment matches `.sdlc/phases/README.md`
- Verification steps must use `prek run --all-files`, not individual tools

---

### 2. Engine Agent

**Purpose**: Implements the ARI-based scanning engine and Primary orchestrator.

**Context Files**:
- `CLAUDE.md`
- `.sdlc/specs/REQ-001-scanning-engine/`
- `.sdlc/context/architecture.md`
- `proto/apme/v1/primary.proto`
- `proto/apme/v1/validate.proto`

**Scope**: `src/apme_engine/engine/`, `src/apme_engine/daemon/primary_server.py`, `src/apme_engine/runner.py`

**Capabilities**:
- Integrate with the vendored ARI engine (ADR-003)
- Parse → annotate → hierarchy pipeline
- Fan-out to validators via `asyncio.gather()` with `return_exceptions=True`
- Manage `VenvSessionManager` (session-scoped venvs)
- Implement `FixSession` bidirectional streaming

**Constraints**:
- Must not modify playbook files during scanning (validators are read-only)
- Must preserve graceful degradation on validator failure (empty result, not crash)
- Must propagate `request_id` to all validator calls
- Must use `run_in_executor()` for blocking engine work

---

### 3. Remediation Agent

**Purpose**: Implements the remediation engine — deterministic transforms and AI-assisted fixes.

**Context Files**:
- `CLAUDE.md`
- `.sdlc/specs/REQ-002-automated-remediation/`
- `src/apme_engine/remediation/`
- ADR-009, ADR-023, ADR-025, ADR-036

**Scope**: `src/apme_engine/remediation/`

**Capabilities**:
- Implement `TransformRegistry` and structured transforms (Tier 1)
- Implement `AIProvider` protocol for AI-assisted remediation (Tier 2, ADR-025)
- Convergence loop: scan → transform → re-scan until stable
- Per-finding `RemediationClass` + `RemediationResolution` (ADR-023)
- YAML transformations using `ruamel.yaml` (comment-preserving)

**Constraints**:
- Must preserve YAML comments (use `ruamel.yaml`, never `PyYAML` for writes)
- Must maintain playbook semantics — no silent behavioral changes
- Must be idempotent — repeated runs produce the same result
- `scan_fn` is injected — remediation engine does not own gRPC transport

---

### 4. Validator Agent

**Purpose**: Implements individual validator backends (Native, OPA, Ansible, Gitleaks).

**Context Files**:
- `CLAUDE.md`
- `.sdlc/context/architecture.md`
- `proto/apme/v1/validate.proto`
- ADR-002, ADR-010, ADR-022

**Scope**: `src/apme_engine/validators/`, `src/apme_engine/daemon/*_validator_*.py`

**Capabilities**:
- Implement rules within the `Validator` protocol (`validators/base.py`)
- Wire rules to `ValidatorServicer` gRPC adapters
- OPA: Rego rules on hierarchy JSON (subprocess, not REST)
- Native: Python rules on deserialized scandata
- Ansible: Runtime checks using session-scoped venvs (read-only)
- Gitleaks: Secrets scanning via gitleaks binary

**Constraints**:
- **Validators are read-only** — detection only, never modify files
- Must implement `Validator.Validate` + `Validator.Health` (unified contract)
- Must use `run_in_executor()` for blocking work
- Must return `ValidatorDiagnostics` with timing data
- Must handle errors gracefully (log + empty result, not crash)

---

### 5. Gateway & UI Agent

**Purpose**: Implements the REST Gateway and React frontend.

**Context Files**:
- `CLAUDE.md`
- `.sdlc/specs/REQ-004-enterprise-integration/`
- ADR-029, ADR-030, ADR-037, ADR-038

**Scope**: `src/apme_gateway/`, `frontend/`

**Capabilities**:
- FastAPI REST endpoints for scan management and reporting
- SQLAlchemy + aiosqlite persistence
- `ReportingServicer` (gRPC server for engine events, ADR-020)
- React/PatternFly UI for project management and scan results

**Constraints**:
- Gateway depends on engine, **not** the other way around
- Engine must never import from `apme_gateway`
- Persistence is the gateway's concern — engine stays stateless
- Must handle engine unavailability gracefully (health-gated operations)

---

### 6. Integration Agent

**Purpose**: Creates CI/CD integrations, examples, and Galaxy Proxy.

**Context Files**:
- `CLAUDE.md`
- `.sdlc/specs/REQ-003-security-compliance/`
- `.sdlc/specs/REQ-004-enterprise-integration/`
- `examples/`
- ADR-031

**Scope**: `src/galaxy_proxy/`, `containers/`, `examples/`, `.github/`

**Capabilities**:
- Create GitHub Actions workflows
- Create AAP pre-flight checks (document `apme-scan check` / `apme-scan remediate`)
- Galaxy Proxy PEP 503 implementation (ADR-031)
- Container definitions and pod configuration
- Write integration documentation and example configurations

**Constraints**:
- Must be copy-paste ready
- Must include clear documentation
- Must handle common edge cases
- Galaxy Proxy is the only service with HTTP endpoints inside the pod

---

## Agent Workflow

```
┌─────────────────┐
│  Spec Writer    │ ──► Creates REQ and TASK specs
└────────┬────────┘
         │
         ▼
┌─────────────────┐     Engine, Remediation, Validator,
│  Implementation │ ──► Gateway/UI agents implement
│     Agents      │     based on specs and ADRs
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Integration    │ ──► Creates CI/CD, containers, examples
│     Agent       │
└─────────────────┘
```

## Handoff Protocol

When transitioning between agents:

1. **Completing Agent**:
   - Update task status to `Complete`
   - Document any deviations from spec
   - Note open questions for next agent
   - Verify no architectural invariants were violated (see list above)

2. **Receiving Agent**:
   - Read `CLAUDE.md` for project constitution
   - Read this file's **Architectural Invariants** section
   - Read relevant REQ and TASK specs
   - Read relevant ADRs (linked from REQ and this file)
   - Check for notes from previous agent
   - Continue from documented state

## Key Source Layout

Understanding where code lives prevents accidental duplication or misplacement.

```
src/
├── apme/v1/                     # Generated proto stubs — NEVER edit by hand
├── apme_engine/                  # Core product
│   ├── cli/                      # apme-scan: check, remediate, format, health
│   ├── daemon/                   # gRPC servers: primary, native, opa, ansible, gitleaks
│   │   └── sinks/                # Event sinks (grpc_reporting)
│   ├── engine/                   # ARI-backed: parser, scanner, models, annotators
│   ├── remediation/              # Convergence engine, transforms, AI provider
│   ├── validators/               # Rule implementations (native/, opa/, ansible/, gitleaks/)
│   └── venv_manager/             # Session-scoped venvs
├── apme_gateway/                 # FastAPI REST + SQLAlchemy DB + Reporting gRPC server
└── galaxy_proxy/                 # PEP 503 proxy (Galaxy → wheels)
```

## Project Skills

This project defines agent skills in `.agents/skills/`. When the user types a
`/slash-command`, check `.agents/skills/<command-name>/SKILL.md` **before doing
anything else**. If a matching skill exists, read it and follow its instructions.

| Command | Purpose |
|---------|---------|
| `/adr-new` | Create architectural decision record |
| `/dr-new` | Capture blocking question |
| `/dr-review` | Review decision records |
| `/lean-ci` | CI workflow helpers |
| `/phase-new` | Create project phase |
| `/pr-review` | Handle PR review feedback |
| `/prd-import` | Import product requirements |
| `/req-new` | Create requirement spec |
| `/review-contributor-pr` | Review external contributor PRs |
| `/sdlc-status` | SDLC dashboard status |
| `/submit-pr` | Create and submit pull requests |
| `/task-new` | Create implementation task |
| `/workflow` | Development workflow guidance |

## Design Thinking

### Sunk cost fallacy

Do not defend existing code simply because effort was invested in it. If a
fix requires increasingly complex workarounds — offset detection, heuristic
correction, retry loops — the underlying abstraction is likely wrong.
Discard the existing approach and redesign the interface.

**Two workarounds for the same interface = redesign the interface.**

### Design LLM contracts around LLM strengths

Never ask an LLM to be precise about line numbers, character offsets, or
positional arithmetic. LLMs are good at understanding and transforming
text. Design contracts where the LLM returns **content** and we handle
**positioning** and reassembly.

### Treat directional feedback as architectural

When a human says "we're too coupled to X" or "why do we need Y," treat
it as an architectural concern, not a narrow bug. Step back to first
principles before writing code. Ask: *"What would this look like if we
didn't have X at all?"*

### Two failed attempts = wrong abstraction

If the same class of failure recurs after two fix attempts, do not attempt
a third fix at the same level. Escalate to a design review of the
interface itself. The pattern of repeated failure is the evidence.

### Dependency direction is sacred

The engine depends on nothing outside its pod. The Gateway depends on
the engine. The UI depends on the Gateway. **Never** invert these arrows.
If you find yourself importing `apme_gateway` from `apme_engine`, or
having the engine call back to the Gateway, stop — you are violating
ADR-020 and ADR-029.

### When in doubt, read the ADR

Every major design choice has an ADR in `.sdlc/adrs/`. If you are about to
make a decision that affects service boundaries, communication patterns,
data flow, or deployment topology, check the ADR index first. If no ADR
covers it, write one before implementing.

## Quality Assurance

All agents must:

1. Follow the spec exactly
2. Run verification steps (`prek run --all-files`)
3. Update task status
4. Commit with proper message format (Conventional Commits)
5. Flag any spec ambiguities
6. Verify no architectural invariants (above) were violated
