---
rule_id: L077
validator: native
description: Roles should have meta/argument_specs.yml for fail-fast parameter validation.
scope: role
---

## Role argument specs (L077)

Roles should have `meta/argument_specs.yml` (Ansible 2.11+) for fail-fast parameter validation.

### Example: violation

A role directory without `meta/argument_specs.yml`.

### Example: pass

A role directory with `meta/argument_specs.yml` defining expected parameters.
