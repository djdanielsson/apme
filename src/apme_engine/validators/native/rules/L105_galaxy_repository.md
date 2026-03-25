---
rule_id: L105
validator: native
description: galaxy.yml should have a repository key.
scope: collection
---

## Galaxy repository (L105)

The `galaxy.yml` file should include a `repository` key pointing to the source code repository. This helps users find the project and contribute.

Maps to ansible-lint `galaxy[no-repository]`.

Requires collection-level target type not yet in the engine. Currently disabled.

**Violation:** galaxy.yml without `repository` key — **Pass:** `repository: https://...`
