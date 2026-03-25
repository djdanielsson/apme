---
rule_id: L095
validator: native
description: YAML file does not match expected schema structure.
scope: playbook
---

## Schema validation (L095)

Basic structural schema validation for playbooks and galaxy.yml. Checks for required keys and rejects unknown play-level keys.

Maps to ansible-lint `schema` rule.

Requires `play_data`/`metadata` attributes not yet on the engine model. Currently disabled.

**Violation:** galaxy.yml missing `namespace` — **Pass:** all required keys present
