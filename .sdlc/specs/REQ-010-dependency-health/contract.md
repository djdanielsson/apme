# REQ-010: Dependency Health Assessment — Contract

## Status

Placeholder — to be completed during implementation planning.

## Contract Notes

- Gateway REST API endpoints for dependency queries (`GET /api/v1/collections`, `GET /api/v1/python-packages`)
- Health assessment write-back endpoints (`POST /api/v1/collections/{fqcn}/health`, `POST /api/v1/python-packages/{name}/health`)
- `ProjectManifest` protobuf message in `FixCompletedEvent` (ADR-040)
- CVE finding data model for Python package assessments
- Collection health score computation from engine scan results
