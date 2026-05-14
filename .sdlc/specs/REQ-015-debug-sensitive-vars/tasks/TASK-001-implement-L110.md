# TASK-001: Implement L110 Debug Sensitive Variables Rule

## Status

Completed

## Description

Create the L110_debug_sensitive_vars_graph.py rule that detects debug tasks logging sensitive variables without no_log protection.

## Implementation

### Files Created

1. `src/apme_engine/validators/native/rules/L110_debug_sensitive_vars_graph.py`
   - GraphRule subclass following L047 pattern
   - Detects debug module with msg/var containing sensitive variable patterns
   - Respects no_log inheritance from task/block/play scope

2. `tests/test_L110_debug_sensitive_vars_graph.py`
   - 28 unit tests covering all acceptance criteria
   - Tests for helpers: `_extract_jinja_vars`, `_var_looks_sensitive`, `_find_sensitive_vars_in_debug`
   - Tests for rule: match conditions, violations, no_log inheritance, false positives

### Sensitive Patterns Detected

- password, passwd, pwd
- secret, secrets
- token, auth_token, access_token, api_token
- api_key, apikey
- credential, credentials, cred
- private_key, ssh_key

## Verification

- [x] `tox -e lint` passes
- [x] `tox -e unit -- tests/test_L110_debug_sensitive_vars_graph.py` passes (28/28 tests)
- [x] Rule auto-registered in Native validator (via module discovery)
- [x] RULE_CATALOG.md auto-updated by lint hook

## Completion Date

2026-05-14
