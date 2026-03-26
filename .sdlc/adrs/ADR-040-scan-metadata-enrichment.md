# ADR-040: Scan Metadata Enrichment

## Status

Accepted

## Date

2026-03-25

## Context

During a project scan, the engine discovers significant information about the project beyond violations: which Ansible collections are used (and their versions), which Python packages are in the session environment, what `requirements.yml` and `requirements.txt` contain, what ansible-core version was used, and how FQCNs resolved. The Galaxy Proxy also resolves the full transitive dependency tree when building session venvs.

Today, nearly all of this knowledge is discarded. The `FixCompletedEvent` primarily exposes violations and diagnostics (alongside scan/session identifiers, logs, and hierarchy payload), but does not carry any dependency or manifest metadata. The Gateway persists violations and computes health scores, but has no record of what collections or Python packages a project depends on.

This matters for two reasons:

1. **Consumers need project context, not just violations.** ADR-038 established the Gateway REST API as the public data-sharing interface. Consumers like Controller and CI/CD systems need to know *what* a project depends on — not just what's wrong with it. A pre-flight gate might ask "does this project use any collection with Critical findings?" Today the Gateway can't answer that question because it doesn't know what collections the project uses.

2. **Derivative analysis requires dependency data.** Collection health scanning (running collections through the engine), Python CVE checking (pip-audit / OSV), SBOM generation (DR-002), and drift detection all need a project's dependency manifest as input. Without persisted metadata, each of these tools would need to independently discover dependencies — duplicating work the engine already does.

### What the engine already knows

| Data | Source | Currently surfaced? |
|------|--------|-------------------|
| Collections used (FQCN → collection) | M001-M004 resolution, L026 | Only as violation metadata |
| Collection versions | Session venv (`uv pip list`) | No |
| Python packages + versions | Session venv | No |
| Transitive collection deps | Galaxy Proxy resolution | No |
| `requirements.yml` contents | Project file parsing | No |
| `requirements.txt` / EE definition | Project file parsing | No |
| ansible-core version | Session venv build | Partially (session_id) |

The data exists. The contract doesn't carry it.

## Decision

**We will extend the scan reporting contract to include a project dependency manifest, persist it in the Gateway, and expose it via the REST API.**

### Manifest structure

The engine emits a `ProjectManifest` alongside violations in `FixCompletedEvent` (ADR-039):

```protobuf
message CollectionRef {
  string fqcn = 1;           // e.g. "community.general"
  string version = 2;        // e.g. "8.0.0"
  string source = 3;         // "specified", "learned", or "dependency"
}

message PythonPackageRef {
  string name = 1;            // e.g. "jmespath"
  string version = 2;         // e.g. "1.0.1"
}

message ProjectManifest {
  string ansible_core_version = 1;
  repeated CollectionRef collections = 2;
  repeated PythonPackageRef python_packages = 3;
  repeated string requirements_files = 4;   // paths found in project
  string dependency_tree = 5;               // raw `uv pip tree` output
}
```

### Data flow

```
Engine (check/remediate via FixSession)
  ├── resolves FQCNs → collections
  ├── enumerates session venv → packages
  └── emits FixCompletedEvent + ProjectManifest
        │
        ▼
Gateway (persist)
  ├── stores manifest in scan_manifests table
  ├── updates project ↔ collection associations
  └── exposes via REST API
        │
        ▼
Consumers (query)
  ├── GET /api/v1/projects/{id}/dependencies
  ├── GET /api/v1/collections (all known collections)
  └── GET /api/v1/collections/{fqcn}/projects (who uses this?)
```

### REST API extensions (planned, per ADR-038)

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/projects/{id}/dependencies` | Collections and Python packages for a project |
| `GET /api/v1/collections` | All collections seen across projects, with usage counts |
| `GET /api/v1/collections/{fqcn}` | Collection detail: version, projects using it, health score |
| `GET /api/v1/collections/{fqcn}/projects` | Projects that depend on this collection |
| `GET /api/v1/python-packages` | All Python packages seen across projects, with usage counts |
| `GET /api/v1/python-packages/{name}` | Package detail: version(s), projects using it, CVE status |

## Alternatives Considered

### Alternative 1: Derive dependencies from violations only

**Description**: Infer collection usage from M001-M004 violation metadata (which already includes `resolved_fqcn`). No proto change needed.

**Pros**:
- No contract change
- Works today for collections that trigger violations

**Cons**:
- Only captures collections that have *problems*. A clean collection with no violations would be invisible.
- No Python package data
- No version information
- Fragile — depends on violation metadata structure

**Why not chosen**: Incomplete. A project using 10 collections where 2 have violations would only show 2 collections.

### Alternative 2: Gateway discovers dependencies independently

**Description**: Gateway parses `requirements.yml` and project files itself, bypassing the engine.

**Pros**:
- No engine changes
- Gateway controls the logic

**Cons**:
- Duplicates parsing that the engine already does
- Gateway doesn't have a session venv — can't resolve transitive deps or enumerate installed packages
- Galaxy Proxy resolution happens during engine session setup, not in the Gateway

**Why not chosen**: The engine already has the data. Duplicating discovery is wasteful and less accurate.

## Consequences

### Positive

- The Gateway gains a complete picture of project dependencies, enabling collection health correlation, SBOM generation, and drift detection.
- Derivative analysis tools (collection scanner, CVE checker) can query the Gateway API for input data instead of independently discovering dependencies.
- ADR-038's public API becomes significantly more useful — consumers can ask "what does this project depend on?" not just "what's wrong with it?"

### Negative

- Proto change requires regeneration and version coordination across engine and Gateway.
- `ProjectManifest` adds payload size to `FixCompletedEvent`. For large projects with many collections, this could be significant. Mitigation: manifest is per-scan, not per-violation.
- Gateway schema migration needed for new tables (collection refs, package refs, project associations).

### Neutral

- The engine's scan latency is unaffected — it already resolves this data during scanning. Emitting it is serialization cost only.
- The Galaxy Proxy is unchanged. It already resolves dependencies; the engine just surfaces what the proxy discovered.

## Implementation Notes

### Engine changes

1. After session venv build, enumerate installed collections and Python packages (`uv pip list --format json` or `importlib.metadata`).
2. During FQCN resolution (M001-M004), collect resolved collection references.
3. Populate `ProjectManifest` and attach to `FixCompletedEvent`.

### Gateway changes

1. New DB tables: `scan_manifests`, `scan_collections`, `scan_python_packages` (scan-scoped; project views derived from latest scan).
2. `grpc_reporting/servicer.py`: Extract and persist manifest from `FixCompletedEvent`.
3. New REST endpoints under `/api/v1/`.

### Galaxy Proxy (no changes)

The proxy already resolves transitive dependencies. The engine reads the installed result from the session venv.

## Related Decisions

- ADR-020: Reporting service and event delivery (the transport for `FixCompletedEvent`)
- ADR-029: Web Gateway architecture (persistence layer, REST API)
- ADR-037: Project-centric UI model (project entity that manifests attach to)
- ADR-038: Public data API (the REST API surface these endpoints extend)
- DR-002: SBOM generation (deferred; manifest data is the prerequisite)

## References

- PR #93: Original REQ-010 proposal (dependency scanning)
- REQ-010: Dependency Health Assessment (builds on this ADR)

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-03-25 | Brad (cidrblock) | Initial proposal |
