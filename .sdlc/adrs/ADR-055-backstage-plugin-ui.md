# ADR-055: Replace Standalone UI with Backstage Plugin

## Status

Accepted

## Date

2026-04

## Context

APME currently ships a standalone React/PatternFly SPA served by nginx on port 8081.
This UI talks exclusively to the APME Gateway REST API.  Meanwhile, the Ansible
self-service automation portal (built on Red Hat Developer Hub / Backstage) is
becoming the standard operational interface for Ansible Automation Platform.
Running a separate UI alongside the portal creates deployment overhead, duplicated
auth flows, and a fragmented user experience.

The portal already hosts plugins for AAP operations (`backstage-rhaap`), self-service
templates, catalog sync, and scaffolder actions via
[ansible-backstage-plugins](https://github.com/ansible/ansible-backstage-plugins),
deployed by the
[ansible-portal-chart](https://github.com/ansible-automation-platform/ansible-portal-chart)
Helm chart.

## Options Considered

| Option | Pros | Cons |
|--------|------|------|
| Keep standalone UI | No cross-repo work, full control | Duplicate auth, separate deployment, fragmented UX |
| Embed APME UI in iframe | Quick integration | No shared auth, CORS issues, poor UX |
| Backstage plugin (chosen) | Unified auth (AAP OAuth), single deployment, standard plugin patterns, sidebar integration | Cross-repo work, must support SSE/WS proxying, port 16 pages |

## Decision

**Replace the standalone APME UI with a Backstage frontend plugin (`plugin-apme`) and
a backend proxy module (`plugin-apme-backend`).** These live in the
`ansible-backstage-plugins` monorepo alongside existing Ansible plugins.

The APME engine stack (Primary, validators, Galaxy Proxy, Gateway) deploys as an
**optional Kubernetes Deployment** in the portal Helm chart, gated by `apme.enabled`.

### Key design choices

1. **Backend proxy pattern**: The Backstage backend module proxies all Gateway
   REST, SSE, and WebSocket traffic.  The frontend plugin never calls the Gateway
   directly — all requests go through Backstage's backend, which forwards the
   authenticated user identity via `X-Backstage-User`.

2. **Separate Deployment, not sidecar**: The APME engine runs as its own
   Deployment with a ClusterIP Service (`apme-gateway:8080`).  This preserves
   the existing pod-as-a-unit scaling model (ADR-012) and keeps the RHDH pod
   simple.

3. **All 16 pages ported**: Dashboard, Projects (list/detail), Analytics,
   Playground, Activity (list/detail), Sessions (list/detail), Health, Rules,
   Collections (list/detail), Python Packages (list/detail), Settings.

4. **Overlap resolution**: Portal's PAH collection catalog sync and APME's
   per-project dependency/health analysis are complementary.  Auth uses the
   portal's AAP OAuth; the Gateway gets identity headers for future enforcement.
   All scanning, remediation, rules, playground, analytics, and session features
   are APME-specific with no portal overlap.

5. **Dynamic plugin support**: Both plugins export dynamic plugin metadata
   (`export-dynamic`) so they can be loaded via RHDH's OCI or tarball plugin
   delivery without rebuilding the portal image.

## Consequences

- The standalone `apme-ui` container and `containers/ui/` directory remain for
  local Podman pod development but are no longer the primary UI for production.
- The Gateway must accept an `X-Backstage-User` header and configurable CORS
  origins (`APME_CORS_ORIGINS`).
- Container images for the engine stack must be published to a registry
  accessible by the Kubernetes cluster.
- Future UI features target the Backstage plugin, not the standalone SPA.

## Related

- ADR-012: Scale Pods Not Services
- ADR-029: Gateway REST API
- ADR-030: UI Architecture
- ADR-037: UI-Gateway Communication
- ADR-054: Production Deployment
