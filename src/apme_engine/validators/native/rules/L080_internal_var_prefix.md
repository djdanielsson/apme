---
rule_id: L080
validator: native
description: Internal role variables should be prefixed with __ (double underscore).
scope: task
---

## Internal variable prefix (L080)

Internal role variables (from `set_fact` or `register`) should be prefixed with `__` to signal they are private.

Only fires inside `roles/` directories. Checks `set_fact` keys for missing `__` prefix.

**Violation:** `set_fact: temp_value: ...` inside a role — **Pass:** `set_fact: __temp_value: ...`
