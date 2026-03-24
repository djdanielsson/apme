# ADR-035: Secret Externalization for Ansible Content

## Status

Proposed — implementation approach superseded by ADR-036

## Date

2026-03-23

## Context

Ansible playbooks frequently contain hardcoded credentials in `vars:` blocks:
API keys, database passwords, SSH private keys, tokens, and other sensitive
material. These secrets should be externalized into Ansible Vault-encrypted
files and referenced via `vars_files:`.

Detecting hardcoded secrets is non-trivial because:

1. **High-entropy values** (real API keys, PEM blocks) are caught by
   entropy-based scanners like gitleaks, but **low-entropy placeholder
   values** (e.g. `password: "admin123"`) are often missed.
2. **Variable names** carry strong signal (`db_password`, `aws_secret_key`,
   `ssh_private_key`) but name heuristics alone produce false positives on
   non-secret variables that happen to match patterns.
3. **Multi-line block scalars** (PEM keys) span many lines and require
   careful line-range mapping to associate gitleaks findings with the
   correct YAML key.

### Detection approach

A two-pass union strategy provides the best coverage:

1. **Gitleaks pass** — 800+ value patterns with entropy filtering. Catches
   real high-entropy credentials and PEM keys. Uses
   `apme_engine.validators.gitleaks.scanner.run_gitleaks()`.

2. **Variable-name heuristics** — regex matching against YAML key names
   (`password`, `token`, `secret`, `*_key`, `*_credential`, etc.). Catches
   low-entropy placeholder values whose names signal credential storage.

The union of both passes ensures that:
- Real secrets are caught by gitleaks even when their names are generic
- Placeholder secrets are caught by name heuristics even when their values
  have low entropy

### Externalization output

Given a playbook with hardcoded secrets, externalization produces:

| Output | Contents |
|--------|----------|
| Modified playbook | Secret vars removed from `vars:`; `vars_files:` entry added pointing to the vault file |
| Vault variables file | Extracted key-value pairs with `ansible-vault encrypt` guidance |

The original source file is never modified — a `.externalized.yml` copy
is produced (or, in the engine-integrated path, patches are proposed for
approval).

## Decision

**Secret externalization is a valid remediation concern that should be
integrated into the APME remediation engine as a project-level
deterministic transform (see ADR-036), not a standalone CLI subcommand.**

The detection logic (gitleaks + name heuristics union) and YAML round-trip
editing approach described here are sound. The implementation approach
(standalone `externalize-secrets` subcommand) is superseded by ADR-036,
which folds this transform into the two-pass remediation engine where it
benefits from:

- Existing scan results (SEC violations already detected by the Gitleaks
  validator)
- Cross-file deduplication of common secrets across playbooks
- The approval workflow (patches shown for review before applying)
- The "next steps" protocol (vault setup instructions without exposing
  secret values over the wire)

## Reference Implementation

PR #70 (`feat/externalize-secrets`) contains a proof-of-concept
implementation as a standalone CLI subcommand:

- `src/apme_engine/cli/externalize.py` — detection logic, YAML round-trip
  editing, two-file output
- `tests/test_externalize.py` — 70 unit tests covering detection helpers,
  edge cases, and regression scenarios
- `.sdlc/specs/REQ-005-secret-externalization/` — requirement specification

Key implementation patterns from PR #70 that should carry forward into the
engine-integrated transform:

- `ruamel.yaml` round-trip mode (`YAML(typ="rt")`) for comment preservation
- Line-number overlap mapping between gitleaks findings and YAML keys
- `CommentedMap.insert()` for `vars_files:` injection
- Union of `_SECRET_NAME_RE` matches with gitleaks line-range intersections

## Alternatives Considered

### Alternative 1: Standalone CLI subcommand (PR #70)

**Pros**: Works without a running daemon; zero proto changes.

**Cons**: Duplicates gitleaks detection that the Gitleaks validator already
performs; builds YAML transform logic outside the remediation engine;
creates two code paths for the same problem; directory mode has a
shared-file overwrite bug.

**Why superseded**: Secret externalization is a cross-file remediation
transform that belongs in the engine, not a parallel path.

### Alternative 2: Server-side gRPC RPC

**Pros**: Consistent with ADR-001.

**Cons**: Significant proto churn for a transformation that maps cleanly
to the existing fix pipeline's patch model once the engine supports
project-level transforms.

**Why not chosen**: ADR-036's two-pass engine provides the right
abstraction without new RPCs.

## Consequences

### Positive

- Establishes detection requirements and approach for secret externalization
- Documents the gitleaks + name-heuristic union strategy
- PR #70 provides validated implementation patterns for the engine transform

### Negative

- Standalone subcommand implementation (PR #70) cannot be merged as-is;
  code must be refactored into a project-level transform

## Related Decisions

- ADR-009: Remediation Engine (tiered architecture)
- ADR-010: Gitleaks as gRPC Validator (reuses `run_gitleaks`)
- ADR-036: Two-Pass Remediation Engine (supersedes this ADR's
  implementation approach)

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-03-23 | Vinny Valdez | Original proposal as standalone subcommand (PR #70) |
| 2026-03-23 | Bradley A. Thornton | Renumbered from ADR-034; implementation approach superseded by ADR-036 |
