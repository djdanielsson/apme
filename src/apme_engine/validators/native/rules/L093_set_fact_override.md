---
rule_id: L093
validator: native
description: Do not override role defaults/vars with set_fact.
scope: task
---

## set_fact override (L093)

Do not override role defaults/vars with `set_fact`. Use a different variable name to avoid confusion.

Requires role context with `role_defaults`/`role_vars` populated by the engine.

**Violation:** `set_fact: app_port: 9090` when `app_port` is in role defaults — **Pass:** `set_fact: __computed_port: 9090`
