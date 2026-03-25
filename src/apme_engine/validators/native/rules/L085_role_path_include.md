---
rule_id: L085
validator: native
description: Use explicit role_path prefix in include paths within roles.
scope: task
---

## Role path include (L085)

Use `{{ role_path }}/...` prefix for include paths containing variables within roles to avoid search-path surprises.

Only fires inside `roles/` directories for include_tasks/include_vars with variable paths.

**Violation:** `file: "{{ platform }}/vars.yml"` in a role — **Pass:** `file: "{{ role_path }}/vars/{{ platform }}/vars.yml"`
