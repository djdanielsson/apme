# Architecture

## Overview

APME is a multi-container gRPC microservice deployed as a single Podman pod. The Primary service runs the engine (parse → annotate → hierarchy), then fans validation out in parallel to six independent validator backends over a unified gRPC contract. The CLI is ephemeral — run on-the-fly with the project directory mounted.

**Key principles:**
- All inter-service communication is **gRPC** — no REST, no message queue, no service discovery
- Containers in the same pod share **localhost**; addresses are fixed by convention
- All gRPC servers use **grpc.aio** (fully async)
- Blocking work is dispatched via `asyncio.get_event_loop().run_in_executor()`
- Each request carries a **request_id** (correlation ID) for end-to-end tracing

## Container Topology

```
┌──────────────────────────────────── apme-pod ──────────────────────────────────┐
│                                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Primary  │  │  Native  │  │   OPA    │  │ Ansible  │  │ Gitleaks │        │
│  │  :50051  │  │  :50055  │  │  :50054  │  │  :50053  │  │  :50056  │        │
│  │          │  │          │  │          │  │          │  │          │        │
│  │ engine + │  │ Python   │  │ OPA bin  │  │ ansible- │  │ gitleaks │        │
│  │ orchestr │  │ rules on │  │ + gRPC   │  │ core     │  │ + gRPC   │        │
│  │ session  │  │ scandata │  │ wrapper  │  │ venvs    │  │ wrapper  │        │
│  │  venvs   │  │          │  │          │  │ (ro)     │  │          │        │
│  └────┬─────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
│       │                                                                         │
│       │         ┌──────────────┐  ┌──────────────┐                              │
│       │         │ Coll. Health │  │  Dep Audit   │                              │
│       │         │    :50058    │  │    :50059    │                              │
│       │         └──────────────┘  └──────────────┘                              │
│       │                                                                         │
│  ┌────┴─────────────────────────────────────┐  ┌──────────┐                    │
│  │      Galaxy Proxy :8765 (PEP 503)       │  │ Abbenay  │                    │
│  │  Ansible Galaxy → Python wheels on      │  │  :50057  │                    │
│  │  demand; caching handled by proxy + uv  │  └──────────┘                    │
│  └──────────────────────────────────────────┘                                   │
│  ┌──────────────────────┐  ┌──────────┐                                        │
│  │ Gateway :50060/:8080 │  │ UI :8081 │                                        │
│  │ REST + gRPC + DB     │  │ (nginx)  │                                        │
│  └──────────────────────┘  └──────────┘                                        │
└─────────────────────────────────────────────────────────────────────────────────┘

     ┌──────────┐
     │   CLI    │  podman run --rm --pod apme-pod
     │ (on-the  │  -v $(pwd):/workspace:ro,Z
     │  -fly)   │  apme-cli:latest apme check .
     └──────────┘
```

## Services

| Service | Image | Port | Role |
|---------|-------|------|------|
| **Primary** | apme-primary | 50051 | Runs the engine (parse → annotate → hierarchy); manages session-scoped venvs (`VenvSessionManager`); fans out `ValidateRequest` to all validators in parallel; merges, deduplicates, and returns violations |
| **Native** | apme-native | 50055 | Python rules operating on deserialized scandata (the full in-memory model). Rules L026–L060, M005/M010, P001–P004, R101–R501 |
| **OPA** | apme-opa | 50054 | OPA binary (invoked via subprocess) + Python gRPC wrapper. Rego rules L003–L025, M006/M008/M009/M011, R118 on the hierarchy JSON |
| **Ansible** | apme-ansible | 50053 | Ansible-runtime checks using session-scoped venvs (shared read-only via `/sessions` volume). Rules L057–L059, M001–M004 |
| **Gitleaks** | apme-gitleaks | 50056 | Gitleaks binary + Python gRPC wrapper. Scans raw files for hardcoded secrets, API keys, private keys. Filters vault-encrypted content and Jinja2 expressions. Rules SEC:* (800+ patterns) |
| **Collection Health** | apme-collection-health | 50058 | Scans installed Ansible collections for quality issues (deprecated modules, missing argument specs, FQCN violations). Findings cached by FQCN+version |
| **Dep Audit** | apme-dep-audit | 50059 | Python dependency auditor via pip-audit. Checks packages in session venvs against CVE databases |
| **Galaxy Proxy** | apme-galaxy-proxy | 8765 | PEP 503 simple repository API that converts Galaxy collection tarballs to pip-installable Python wheels. Caching is the proxy's concern — the engine has zero cache management code |
| **Gateway** | apme-gateway | 50060 (gRPC), 8080 (HTTP) | REST API + gRPC Reporting service + SQLAlchemy/SQLite persistence. Receives engine events via `GrpcReportingSink`; serves scan history, project management, and rule catalog to UI and external consumers (ADR-029, ADR-038) |
| **UI** | apme-ui | 8081 | nginx-served React/PatternFly SPA. Consumes Gateway REST API. No direct engine communication (ADR-030, ADR-037) |
| **Abbenay** | abbenay | 50057 | AI provider for Tier 2 remediation. Receives fix requests from Primary, queries LLM providers, returns proposed patches |
| **CLI** | apme-cli | — | Ephemeral. Reads project files, chunks uploads, drives **`FixSession`** for user **check** and **remediate** (ADR-039). Run with `--pod apme-pod` and CWD mounted |

---

## gRPC Service Contracts

Proto definitions live in `proto/apme/v1/`. Generated Python stubs in `src/apme/v1/`.

### Primary (`primary.proto`)

```protobuf
service Primary {
  rpc Scan(ScanRequest) returns (ScanResponse);
  rpc Format(FormatRequest) returns (FormatResponse);
  rpc FormatStream(stream ScanChunk) returns (FormatResponse);
  rpc FixSession(stream SessionCommand) returns (stream SessionEvent);
  rpc Health(HealthRequest) returns (HealthResponse);
  rpc ListAIModels(ListAIModelsRequest) returns (ListAIModelsResponse);
}
```

**`ScanStream` removed (ADR-039).** User-facing **check** and **remediate** both use **`FixSession`**: without `fix_options` on the first chunk the engine runs check (format → convergence in dry-run); with `FixOptions` it runs full remediation (Tier 1 apply, optional AI, approvals). The unary **`Scan`** RPC and **`ScanRequest` / `ScanResponse` / `scan_id`** remain for engine semantics and compatible clients.

For unary `Scan`, the CLI (or another client) sends a `ScanRequest` with project files as `repeated File`, optional `ScanOptions`, and `scan_id`. Primary returns `ScanResponse` with merged violations and `ScanDiagnostics` (engine + validator timing data).

### Validator (`validate.proto`) — Unified Contract

```protobuf
service Validator {
  rpc Validate(ValidateRequest) returns (ValidateResponse);
  rpc Health(HealthRequest) returns (HealthResponse);
}
```

Every validator container implements this service. The `ValidateRequest` carries everything any validator might need:

| Field | Type | Used by |
|-------|------|---------|
| `project_root` | string | All |
| `files` | repeated File | Ansible (writes to temp dir), Gitleaks (writes to temp dir) |
| `hierarchy_payload` | bytes (JSON) | OPA, Ansible |
| `scandata` | bytes (jsonpickle) | Native |
| `ansible_core_version` | string | Ansible |
| `collection_specs` | repeated string | Ansible |
| `request_id` | string | All (correlation ID for logging/tracing) |

The `ValidateResponse` echoes back `request_id` for correlation and includes a `ValidatorDiagnostics` message with timing data, violation counts, and validator-specific metadata.

Each validator ignores the data fields it doesn't need. This keeps the contract uniform — adding a new validator means implementing one RPC and choosing which fields to consume.

### Common Types (`common.proto`)

| Type | Fields |
|------|--------|
| `Violation` | rule_id, level, message, file, line (int or range), path |
| `File` | path (relative), content (bytes) |
| `HealthRequest` / `HealthResponse` | status string |
| `RuleTiming` | per-rule timing: rule_id, elapsed_ms, violations count |
| `ValidatorDiagnostics` | per-validator summary: name, request_id, total_ms, file/violation counts, rule timings, metadata map |

---

## Parallel Validator Fan-Out

Primary calls all configured validators concurrently using `asyncio.gather()` with async gRPC stubs:

```
              ┌─► Native          ─── violations ──┐
              │                                     │
              ├─► OPA             ─── violations ──┤
              │                                     │
Primary ──────┼─► Ansible         ─── violations ──┼──► merge + dedup + sort
  (async)     │                                     │
              ├─► Gitleaks        ─── violations ──┤
              │                                     │
              ├─► Collection Hlth ─── findings ────┤
              │                                     │
              └─► Dep Audit       ─── findings ────┘
```

**Wall-clock time = max(validators)** instead of sum.

Each validator is discovered by environment variable (`NATIVE_GRPC_ADDRESS`, `OPA_GRPC_ADDRESS`, `ANSIBLE_GRPC_ADDRESS`, `GITLEAKS_GRPC_ADDRESS`, `COLLECTION_HEALTH_GRPC_ADDRESS`, `DEP_AUDIT_GRPC_ADDRESS`). If a variable is unset, that validator is skipped.

---

## Concurrency Model

All gRPC servers use **grpc.aio** (fully async). This means multiple scan requests can be handled concurrently without thread exhaustion.

| Service | Concurrency strategy | `maximum_concurrent_rpcs` |
|---------|---------------------|---------------------------|
| Primary | `asyncio.gather()` fan-out; engine scan via `run_in_executor()` | 16 |
| Native | CPU-bound rules via `run_in_executor()` | 32 |
| OPA | Blocking subprocess via `run_in_executor()` | 32 |
| Ansible | Blocking venv build + subprocess via `run_in_executor()` | 8 |
| Gitleaks | Blocking subprocess via `run_in_executor()` | 16 |

Each service's `maximum_concurrent_rpcs` is configurable via environment variable (e.g., `APME_PRIMARY_MAX_RPCS`).

---

## Session-Scoped Venvs

The Primary orchestrator manages session-scoped venvs via `VenvSessionManager`. Within each session, venvs are keyed by `ansible_core_version` — like tox matrix entries. Collections discovered by FQCN auto-discovery (ADR-032) are installed incrementally via the Galaxy Proxy. Venvs are shared read-only with validators via a `/sessions` volume.

- **Single writer, many readers**: Primary owns venv creation/updates (rw); validators mount read-only
- **Additive, never destructive**: Collections are only added; a new core version creates a sibling venv
- **Idempotent installs**: `uv pip install` is a no-op for already-installed packages — warm sessions pay near-zero cost
- **Client-controlled identity**: `session_id` is always client-provided (VS Code workspace hash, CI job ID)
- **TTL-based reaping**: Individual core-version venvs can expire independently

---

## Session Tracking (request_id)

Every scan request carries a `request_id` (derived from `ScanRequest.scan_id`) that propagates through the entire system:

```
CLI → Primary (scan_id) → ValidateRequest.request_id → each validator logs [req=xxx]
                                                      → ValidateResponse.request_id (echo)
```

All validator logs are prefixed with `[req=xxx]` for end-to-end correlation across concurrent requests.

---

## Serialization

| Data | Format | Wire type | Producer | Consumer |
|------|--------|-----------|----------|----------|
| Hierarchy payload | JSON (`json.dumps`) | bytes in protobuf | Engine (Primary) | OPA, Ansible |
| Scandata | jsonpickle (`jsonpickle.encode`) | bytes in protobuf | Engine (Primary) | Native |
| Violations | Protobuf `Violation` messages | gRPC | All validators | Primary |
| Project files | Protobuf `File` messages | gRPC | CLI | Primary, Ansible |

`jsonpickle` is used for scandata because the engine's in-memory model (`SingleScan`) contains complex Python objects (trees, contexts, specs, annotations) that standard JSON cannot represent. `jsonpickle` preserves types for round-trip deserialization.

---

## OPA Container Internals

The OPA container invokes the OPA binary directly via subprocess — no OPA REST server is required:

1. **OPA binary** is installed in the container image with the Rego bundle mounted
2. **apme-opa-validator** (Python gRPC wrapper) starts on port 50054, receives `ValidateRequest`, extracts `hierarchy_payload`, invokes `opa eval` as a subprocess with the hierarchy JSON as input, parses the JSON output, and converts it to `ValidateResponse`

This avoids the overhead of running a persistent OPA server while presenting a uniform gRPC contract to Primary.

---

## Gitleaks Container Internals

The Gitleaks container follows a similar multi-stage pattern:

1. **Gitleaks binary** is copied from the official `zricethezav/gitleaks` image into a Python 3.12 slim image
2. **apme-gitleaks-validator** (Python gRPC wrapper) starts on port 50056, receives `ValidateRequest`, writes files to a temp directory, runs `gitleaks detect --no-git --report-format json`, parses the JSON report, and converts findings to `ValidateResponse`

The wrapper adds **Ansible-aware filtering**:
- **Vault filtering**: files containing `$ANSIBLE_VAULT;` headers are excluded
- **Jinja filtering**: matches that are pure Jinja2 expressions (`{{ var }}`) are filtered out as false positives
- **Rule ID mapping**: Gitleaks rule IDs are prefixed with `SEC:` (e.g., `SEC:aws-access-key-id`) and can be mapped to stable APME rule IDs via `RULE_ID_MAP`

---

## Volumes

| Volume | Mount | Services | Access |
|--------|-------|----------|--------|
| `sessions` | `/sessions` | Primary (rw), Ansible (ro) | Session-scoped venvs with ansible-core + collections |
| `workspace` | `/workspace` | CLI (ro) | Project being scanned (mounted from host CWD) |

---

## Port Map

| Port | Service | Protocol |
|------|---------|----------|
| 50051 | Primary | gRPC |
| 50053 | Ansible | gRPC |
| 50054 | OPA | gRPC (wrapper; OPA binary invoked via subprocess) |
| 50055 | Native | gRPC |
| 50056 | Gitleaks | gRPC (wrapper; gitleaks binary for detection) |
| 50057 | Abbenay | gRPC (AI provider for Tier 2 remediation) |
| 50058 | Collection Health | gRPC |
| 50059 | Dep Audit | gRPC |
| 50060 | Gateway | gRPC (Reporting service) |
| 8080 | Gateway | HTTP (REST API) |
| 8081 | UI | HTTP (nginx-served SPA) |
| 8765 | Galaxy Proxy | HTTP (PEP 503 simple repository API) |

---

## Scaling

**Scale pods, not services within a pod.** Each pod is a self-contained stack (Primary + Native + OPA + Ansible + Gitleaks + Collection Health + Dep Audit + Galaxy Proxy) that can process a scan request end-to-end.

```
                    ┌─────────────┐
  ScanRequest ────► │ Load        │
                    │ Balancer    │
                    │ (K8s Svc)   │
                    └──┬──┬──┬────┘
                       │  │  │
              ┌────────┘  │  └────────┐
              ▼           ▼           ▼
         ┌─────────┐ ┌─────────┐ ┌─────────┐
         │ Pod 1   │ │ Pod 2   │ │ Pod 3   │
         │ (full   │ │ (full   │ │ (full   │
         │  stack) │ │  stack) │ │  stack) │
         └─────────┘ └─────────┘ └─────────┘
```

Within a pod, containers share localhost — no config change needed. If a single validator is the bottleneck for one request, the fix is parallelism inside that validator (e.g., task-level concurrency), not more containers.

The **Galaxy Proxy** could be extracted to a shared service across pods to share a single wheel cache. For single-pod deployments this is unnecessary.

---

## Diagnostics Instrumentation

Every validator and the engine collect structured timing data on every request. Diagnostics flow through the gRPC contract — no log parsing required.

### Proto Messages

```protobuf
message RuleTiming {
  string rule_id = 1;
  double elapsed_ms = 2;
  int32  violations = 3;
}

message ValidatorDiagnostics {
  string validator_name = 1;
  string request_id = 2;
  double total_ms = 3;
  int32  files_received = 4;
  int32  violations_found = 5;
  repeated RuleTiming rule_timings = 6;
  map<string, string> metadata = 7;
}

message ScanDiagnostics {
  double engine_parse_ms = 1;
  double engine_annotate_ms = 2;
  double engine_total_ms = 3;
  int32  files_scanned = 4;
  int32  trees_built = 5;
  int32  total_violations = 6;
  repeated ValidatorDiagnostics validators = 7;
  double fan_out_ms = 8;
  double total_ms = 9;
}
```

### Per-Validator Instrumentation

| Validator | Timing granularity | Metadata |
|-----------|-------------------|----------|
| Native | Per-rule elapsed time from engine's `detect()` timing records | — |
| OPA | OPA HTTP query time; per-rule violation counts | `opa_query_ms`, `opa_response_size` |
| Ansible | Per-phase: L057 syntax, M001–M004 introspection, L058 argspec-doc, L059 argspec-mock | `ansible_core_version`, `venv_build_ms` |
| Gitleaks | Total subprocess time | `subprocess_ms`, `files_written` |

### Engine Timing

The engine (`run_scan()`) reports per-phase timing:
- `parse_ms` — target load + PRM load + metadata load
- `annotate_ms` — module annotators + variable resolution
- `tree_build_ms` — call-graph construction
- `total_ms` — wall-clock for the full engine run

### Data Flow

```
Validator → ValidateResponse.diagnostics (ValidatorDiagnostics)
                    ↓
Primary aggregates all ValidatorDiagnostics + engine timing
                    ↓
ScanResponse.diagnostics (ScanDiagnostics)
                    ↓
CLI displays with -v / -vv
```

### CLI Verbosity

| Flag | Display |
|------|---------|
| (none) | Violations only |
| `-v` | Engine time, validator summaries (tree format), top 10 slowest rules |
| `-vv` | Full per-rule breakdown for every validator, metadata, engine phase timing |

With `--json`, the `diagnostics` key is included when `-v` or `-vv` is set.

---

## Health Checks

The CLI `health-check` subcommand calls `Health` on all services and reports status:

```bash
apme health-check --primary-addr 127.0.0.1:50051
```

Primary, Native, OPA, Ansible, Gitleaks, Collection Health, and Dep Audit all implement the `Health` RPC. A service returning `status: "ok"` is healthy; any gRPC error marks it degraded.

---

## Decision Records

See [ADR Index](/.sdlc/adrs/README.md) for the full Architecture Decision Records covering all major design choices:

- [ADR-001: gRPC Communication](/.sdlc/adrs/ADR-001-grpc-communication.md)
- [ADR-004: Podman Pod Deployment](/.sdlc/adrs/ADR-004-podman-pod-deployment.md)
- [ADR-007: Async gRPC Servers](/.sdlc/adrs/ADR-007-async-grpc-servers.md)
- [ADR-012: Scale Pods Not Services](/.sdlc/adrs/ADR-012-scale-pods-not-services.md)
- [ADR-013: Structured Diagnostics](/.sdlc/adrs/ADR-013-structured-diagnostics.md)
- [ADR-039: Unified Operation Stream](/.sdlc/adrs/ADR-039-unified-operation-stream.md) — `FixSession` for check and remediate; `ScanStream` removed
