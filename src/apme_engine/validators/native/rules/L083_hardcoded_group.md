---
rule_id: L083
validator: native
description: Do not hardcode host group names in roles.
scope: task
---

## Hardcoded group names (L083)

Do not hardcode host group names in roles. Pass host list variables or parameterize group names.

Only fires inside `roles/` directories. Checks `yaml_lines` for `groups['literal']` patterns.

**Violation:** `groups['db_servers']` in a role — **Pass:** `groups[target_group_name]`
