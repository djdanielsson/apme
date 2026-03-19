# Deployment

## Podman Pod (Recommended)

The primary deployment target is a **Podman pod**. All backend services run in a single pod sharing localhost; the CLI is run on-the-fly outside the pod with the project directory mounted.

### Prerequisites

- **Podman** (rootless)
- `loginctl enable-linger $USER` (for rootless runtime directory)
- **SELinux**: volume mounts use `:Z` for private labeling

### Build

From the repo root:

```bash
./containers/podman/build.sh
```

This builds six images:

| Image | Dockerfile | Purpose |
|-------|------------|---------|
| `apme-primary:latest` | `containers/primary/Dockerfile` | Orchestrator + engine |
| `apme-native:latest` | `containers/native/Dockerfile` | Native Python validator |
| `apme-opa:latest` | `containers/opa/Dockerfile` | OPA + gRPC wrapper |
| `apme-ansible:latest` | `containers/ansible/Dockerfile` | Ansible validator with pre-built venvs |
| `apme-cache-maintainer:latest` | `containers/cache-maintainer/Dockerfile` | Collection cache manager |
| `apme-cli:latest` | `containers/cli/Dockerfile` | CLI client |

### Start the Pod

```bash
./containers/podman/up.sh
```

This runs `podman play kube containers/podman/pod.yaml`, which starts the pod `apme-pod` with five containers (Primary, Native, OPA, Ansible, Cache Maintainer). A cache directory (`apme-cache/`) is created in the repo root.

### Run CLI Commands

```bash
cd /path/to/your/ansible/project
/path/to/apme/containers/podman/run-cli.sh              # scan (default)
/path/to/apme/containers/podman/run-cli.sh scan --json . # JSON output
/path/to/apme/containers/podman/run-cli.sh fix --check . # dry-run fix
/path/to/apme/containers/podman/run-cli.sh fix .         # apply Tier 1 fixes
/path/to/apme/containers/podman/run-cli.sh format --check .
/path/to/apme/containers/podman/run-cli.sh health-check
```

The CLI container joins `apme-pod`, mounts CWD as `/workspace:Z` (read-write for `fix`/`format`), and communicates with Primary at `127.0.0.1:50051` via gRPC.

The `fix` command uses a **bidirectional streaming RPC** (`FixSession`, ADR-028) for real-time progress and interactive AI proposal review.

### Stop the Pod

```bash
podman pod stop apme-pod
podman pod rm apme-pod
```

### Health Check

```bash
apme-scan health-check --primary-addr 127.0.0.1:50051
```

Reports status of all services (Primary, Native, OPA, Ansible, Cache Maintainer) with latency.

---

## Container Configuration

### Environment Variables

#### Primary

| Variable | Default | Description |
|----------|---------|-------------|
| `APME_PRIMARY_LISTEN` | `0.0.0.0:50051` | gRPC listen address |
| `NATIVE_GRPC_ADDRESS` | — | Native validator address (e.g., `127.0.0.1:50055`) |
| `OPA_GRPC_ADDRESS` | — | OPA validator address (e.g., `127.0.0.1:50054`) |
| `ANSIBLE_GRPC_ADDRESS` | — | Ansible validator address (e.g., `127.0.0.1:50053`) |

> If a validator address is unset, that validator is skipped during fan-out.

#### Native

| Variable | Default | Description |
|----------|---------|-------------|
| `APME_NATIVE_VALIDATOR_LISTEN` | `0.0.0.0:50055` | gRPC listen address |

#### OPA

| Variable | Default | Description |
|----------|---------|-------------|
| `APME_OPA_VALIDATOR_LISTEN` | `0.0.0.0:50054` | gRPC listen address |

> The OPA binary runs internally on `localhost:8181`; the gRPC wrapper proxies to it.

#### Ansible

| Variable | Default | Description |
|----------|---------|-------------|
| `APME_ANSIBLE_VALIDATOR_LISTEN` | `0.0.0.0:50053` | gRPC listen address |
| `APME_CACHE_ROOT` | `/cache` | Collection cache mount point |

#### Cache Maintainer

| Variable | Default | Description |
|----------|---------|-------------|
| `APME_CACHE_MAINTAINER_LISTEN` | `0.0.0.0:50052` | gRPC listen address |
| `APME_CACHE_ROOT` | `/cache` | Collection cache directory |

### Volumes

| Name | Host Path | Container Mount | Services | Access |
|------|-----------|-----------------|----------|--------|
| `cache` | `apme-cache/` | `/cache` | Cache Maintainer, Ansible | rw (cache-maintainer), ro (ansible) |
| `workspace` | CWD (CLI only) | `/workspace` | CLI | rw |

---

## OPA Container Details

The OPA container uses a **multi-stage Dockerfile**:

1. **Stage 1**: Copies the `opa` binary from `docker.io/openpolicyagent/opa:latest`
2. **Stage 2**: Python slim image with `grpcio`, project code, and the Rego bundle

At runtime, `entrypoint.sh`:

1. Starts OPA as a REST server: `opa run --server --addr :8181 /bundle`
2. Waits for OPA to become healthy (polls `/health`)
3. Starts the Python gRPC wrapper (`apme-opa-validator`)

The **Rego bundle is baked into the image** at build time (no volume mount needed).

---

## Ansible Container Details

The Ansible container **pre-builds venvs** for multiple ansible-core versions during `podman build`:

```
/opt/apme-venvs/
  ├── 2.18/    # venv with ansible-core==2.18.*
  ├── 2.19/    # venv with ansible-core==2.19.*
  └── 2.20/    # venv with ansible-core==2.20.*
```

`prebuild-venvs.sh` runs during the Docker build to create these. At runtime, the validator selects the appropriate venv based on `ansible_core_version` from the `ValidateRequest`.

**Collections** from the cache volume are symlinked or copied into the venv's `site-packages/ansible_collections/` directory so they're on the Python path (no `ANSIBLE_COLLECTIONS_PATH` or `ansible.cfg` needed).

---

## Local Development (Daemon Mode)

For development and testing without the Podman pod, the CLI can start a
local daemon that runs the Primary, Native, OPA, and Ansible validators
in-process (ADR-024):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"

# Start the local daemon (background process)
python -m apme_engine.cli daemon start

# Run commands (same thin CLI, talks to local daemon via gRPC)
python -m apme_engine.cli scan /path/to/project
python -m apme_engine.cli fix --check .
python -m apme_engine.cli fix .

# Stop the daemon
python -m apme_engine.cli daemon stop
```

**Daemon mode** starts a local Primary server with Native, OPA, and Ansible
validators running in-process. Gitleaks is excluded (requires the container
with the gitleaks binary). OPA runs via the local `opa` binary (no container
needed); skip it with `--no-opa` if `opa` is not installed.

The CLI is a **thin gRPC client** — it sends file bytes to the daemon and
receives results. It does not import engine internals.

---

## Troubleshooting

See `PODMAN_OPA_ISSUES.md` for common Podman rootless issues:

| Issue | Solution |
|-------|----------|
| `/run/libpod: permission denied` | Run in a real login shell, enable linger |
| Short-name resolution | Use fully qualified image names (`docker.io/...`) |
| `/bundle: permission denied` | Use `--userns=keep-id` and `:z` volume suffix |

---

## Quick Reference

### Build and Run

```bash
# Build all images
./containers/podman/build.sh

# Start the pod
./containers/podman/up.sh

# Run a scan
cd /your/project && /path/to/run-cli.sh

# Stop
podman pod stop apme-pod && podman pod rm apme-pod
```

### Port Map

| Port | Service | Listen Variable |
|------|---------|-----------------|
| 50051 | Primary | `APME_PRIMARY_LISTEN` |
| 50052 | Cache Maintainer | `APME_CACHE_MAINTAINER_LISTEN` |
| 50053 | Ansible | `APME_ANSIBLE_VALIDATOR_LISTEN` |
| 50054 | OPA | `APME_OPA_VALIDATOR_LISTEN` |
| 50055 | Native | `APME_NATIVE_VALIDATOR_LISTEN` |
| 50056 | Gitleaks | `APME_GITLEAKS_VALIDATOR_LISTEN` |

---

## Related Documents

- [ARCHITECTURE.md](/ARCHITECTURE.md) — Container topology and service contracts
- [DATA_FLOW.md](/DATA_FLOW.md) — Request lifecycle and serialization
- [ADR-004](/.sdlc/adrs/ADR-004-podman-pod-deployment.md) — Podman pod decision
- [ADR-006](/.sdlc/adrs/ADR-006-ephemeral-venvs.md) — Ephemeral venvs for Ansible
- [ADR-024](/.sdlc/adrs/ADR-024-thin-cli-daemon-mode.md) — Thin CLI with local daemon mode
- [ADR-028](/.sdlc/adrs/ADR-028-session-based-fix-workflow.md) — Session-based fix workflow (FixSession bidi stream)
