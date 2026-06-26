---
rule_id: R404
validator: native
description: Expose variable_set for the task.
scope: task
status: implemented
---

## Show variables (R404)

Expose variable_set for the task. This is an **informational/debug rule**
intended for development and troubleshooting. **Disabled by default.**

Uses `VariableProvenanceResolver` to expose the full variable set available
to each task, including variable origin (local, play, role_default, etc.).
To avoid persisting secrets through debug/audit surfaces, values are reported
in redacted form and sensitive names under an effective ``no_log`` scope are
reported as ``[REDACTED]``.

### Example: violation

```yaml
- name: Example play
  hosts: localhost
  connection: local
  vars:
    server_port: 443
  tasks:
    - name: Show scope
      ansible.builtin.debug:
        msg: "test"
```

### Example: pass

```yaml
- name: Example play
  hosts: localhost
  connection: local
  tasks:
    - name: Ok
      ansible.builtin.command: whoami
```
