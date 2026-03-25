---
rule_id: L073
validator: native
description: YAML should use 2-space indentation.
scope: playbook
---

## Indentation (L073)

YAML should use 2-space indentation consistently.

### Example: pass

```yaml
- name: Example play
  hosts: localhost
  tasks:
    - name: Ok
      ansible.builtin.debug:
        msg: hello
```
