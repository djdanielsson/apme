---
rule_id: L097
validator: native
description: Task names should be unique within a play.
scope: playbook
---

## Name unique (L097)

Each task name should be unique within the same play to make log output and debugging clear.

Maps to ansible-lint `name[unique]`.

Requires `ctx.siblings` to be populated by the engine for play-level deduplication.

**Violation:** two tasks named "Install packages" — **Pass:** unique names per task
