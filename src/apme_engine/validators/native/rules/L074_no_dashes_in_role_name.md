---
rule_id: L074
validator: native
description: Role names should not contain dashes.
scope: role
---

## No dashes in role names (L074)

Role names should not contain dashes as they cause issues with collection packaging.

### Example: violation

Role directory named `my-web-role`.

### Example: pass

Role directory named `my_web_role`.
