---
rule_id: L081
validator: native
description: Do not number roles or playbooks.
scope: playbook
---

## Numbered names (L081)

Do not number roles or playbooks (e.g. `01_setup.yml`). Use descriptive names instead.

### Example: violation

Playbook file named `01_setup.yml`.

### Example: pass

Playbook file named `setup.yml`.
