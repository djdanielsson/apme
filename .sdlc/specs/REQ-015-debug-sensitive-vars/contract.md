# REQ-015: Contract

## Rule Contract

### Input
- ContentGraph with parsed playbook nodes
- Node ID of TASK or HANDLER type

### Output
- `GraphRuleResult` with:
  - `verdict`: True if violation found
  - `detail`: Message explaining the sensitive variable detected
  - `node_id`: Affected task node
  - `file`: Tuple of (file_path, line_number)

### Violation Format

```json
{
  "rule_id": "L110",
  "severity": "high",
  "message": "Debug task logs sensitive variable '{{ db_password }}'; set no_log: true",
  "file": "playbook.yml",
  "line": 15,
  "scope": "task"
}
```

## API Compatibility

No changes to existing APIs. Rule integrates via standard GraphRule discovery.
