# REQ-015: Detect Debug Statements Logging Sensitive Variables

## Metadata

- **Phase**: PHASE-001 - CLI Scanner
- **Status**: Implemented
- **Created**: 2026-05-14
- **Rule ID**: L110

## Problem Statement

Ansible playbooks frequently use the `debug` module to output variable values during development and troubleshooting. When developers debug sensitive variables (passwords, tokens, secrets, API keys), these values are logged to the console and potentially to CI/CD logs, creating a security exposure.

### Current Gap

| Rule | What it Detects | Gap |
|------|-----------------|-----|
| L047 | Password-like *parameter names* (e.g., `password=foo`) without `no_log: true` | Does NOT detect `{{ password }}` in debug msg |
| SEC:* (Gitleaks) | Actual hardcoded secrets | Filters OUT Jinja references like `{{ token }}` as false positives |

Example NOT detected by current rules:
```yaml
- name: Debug the database password
  ansible.builtin.debug:
    msg: "Password is {{ db_password }}"
  # No no_log: true — password will appear in logs
```

## User Stories

1. **As a Platform Engineer**, I want APME to detect debug statements that log sensitive variables so that I can prevent credentials from leaking into CI/CD logs.

2. **As a Security Auditor**, I want visibility into playbooks that debug sensitive data so that I can assess credential exposure risk before deployment.

3. **As a Developer**, I want to be warned when I accidentally debug a password variable so that I can add `no_log: true` or remove the debug statement before committing.

## Acceptance Criteria

### AC1: Detect sensitive variables in debug msg
```gherkin
GIVEN a playbook with a debug task
  AND the msg parameter contains a Jinja reference to a sensitive variable
  AND no_log is not set to true
WHEN APME scans the playbook
THEN a violation is reported with rule ID L110
  AND the message explains the sensitive variable exposure risk
  AND the file path and line number are included
```

### AC2: Detect sensitive variables in debug var
```gherkin
GIVEN a playbook with a debug task
  AND the var parameter references a sensitive variable name
  AND no_log is not set to true
WHEN APME scans the playbook
THEN a violation is reported with rule ID L110
```

### AC3: Respect no_log inheritance
```gherkin
GIVEN a playbook with a debug task inside a block
  AND the block sets no_log: true
  AND the debug msg contains a sensitive variable
WHEN APME scans the playbook
THEN no violation is reported (inherited no_log)
```

### AC4: Sensitive variable patterns
The rule shall detect variables matching these patterns (case-insensitive):
- `password`, `passwd`, `pwd`
- `secret`, `secrets`
- `token`, `auth_token`, `access_token`, `api_token`
- `api_key`, `apikey`, `key` (when in context)
- `credential`, `credentials`, `cred`
- `private_key`, `ssh_key`

### AC5: False positive avoidance
```gherkin
GIVEN a debug task with msg: "Hello {{ username }}"
WHEN APME scans the playbook
THEN no violation is reported (username is not sensitive)
```

## Technical Design

### Rule Location
- **Validator**: Native (Python-based graph rule)
- **File**: `src/apme_engine/validators/native/rules/L110_debug_sensitive_vars_graph.py`
- **Pattern**: Follows L047_no_log_password_graph.py structure

### Detection Algorithm
1. Match nodes where `node_type` is TASK or HANDLER
2. Check if module is `debug`, `ansible.builtin.debug`, or `ansible.legacy.debug`
3. Extract `msg` and `var` from module_options
4. Scan for Jinja variable references: `{{ var_name }}`
5. Check if any referenced variable name matches sensitive patterns
6. Verify `no_log: true` is not set on task or any ancestor scope
7. Report violation if sensitive variable found without no_log protection

### Severity
- **Level**: HIGH (same as L047)
- **Tags**: SYSTEM, SECURITY

## Dependencies

- **Internal**: L047_no_log_password_graph.py (reuse `_no_log_true_in_scope` helper)
- **Architectural compatibility**: Verified (no invariant conflicts)

## Out of Scope

- Detecting sensitive data in `register` variables (separate rule)
- Detecting sensitive data in template files (Gitleaks handles static secrets)
- Auto-remediation (validators are read-only per ADR-009)

## Open Questions

None currently. Rule follows established L047 pattern.

## Related Artifacts

- [ADR-008](/.sdlc/adrs/ADR-008-rule-id-conventions.md) - Rule ID conventions
- [ADR-009](/.sdlc/adrs/ADR-009-remediation-engine.md) - Validators read-only
- [L047_no_log_password_graph.py](/src/apme_engine/validators/native/rules/L047_no_log_password_graph.py) - Reference implementation
