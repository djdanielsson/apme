# REQ-015: Design

## Overview

Graph-based rule implementation following L047 pattern.

## Components

### L110_debug_sensitive_vars_graph.py

```python
# Pseudocode - actual implementation in tasks

SENSITIVE_PATTERNS = frozenset({
    "password", "passwd", "pwd",
    "secret", "secrets",
    "token", "auth_token", "access_token", "api_token",
    "api_key", "apikey",
    "credential", "credentials", "cred",
    "private_key", "ssh_key",
})

DEBUG_MODULES = frozenset({
    "debug",
    "ansible.builtin.debug",
    "ansible.legacy.debug",
})

class DebugSensitiveVarsGraphRule(GraphRule):
    rule_id = "L110"
    severity = Severity.HIGH
    
    def match(self, graph, node_id):
        # Match debug tasks with msg or var
        
    def process(self, graph, node_id):
        # Extract Jinja refs from msg/var
        # Check for sensitive patterns
        # Verify no_log scope
        # Return violation if found
```

## Integration Points

- Defines own `_no_log_true_in_scope` helper (respects no_log: false override)
- Registers in Native validator rule discovery
- No proto changes required

## Testing Strategy

- Unit tests with example playbooks
- Integration test using `examples/secrets_example.yml`
