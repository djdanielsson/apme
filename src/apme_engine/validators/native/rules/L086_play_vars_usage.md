---
rule_id: L086
validator: native
description: Avoid playbook/play vars for routine config; use inventory vars.
scope: play
---

## Play vars usage (L086)

Avoid defining many variables at the play level (`vars:` section). Use inventory `group_vars` or `host_vars` for routine configuration.

### Example: violation

```yaml
- name: Deploy app
  hosts: all
  vars:
    db_host: db.example.com
    db_port: 5432
    db_name: myapp
    db_user: admin
    app_port: 8080
    app_workers: 4
  tasks: []
```

### Example: pass

Move variables to `group_vars/all/database.yml` and `group_vars/all/app.yml`.
