# GitHub Actions Examples

Ready-to-use workflows for scanning Ansible content with APME.

## Available Workflows

| File | Purpose |
|------|---------|
| `apme-check.yml` | Basic check on pull requests |
| `apme-format.yml` | YAML formatting check only |
| `apme-full.yml` | Combined check + format + optional remediate |

## Usage

1. Copy the desired workflow to `.github/workflows/` in your repo
2. Commit and push
3. Open a PR to see APME run

## Workflow: Basic Check

**File:** `apme-check.yml`

Runs `apme check` on every PR that modifies YAML files. Fails if any
violations are found.

```yaml
# Copy to: .github/workflows/apme.yml
name: APME Check

on:
  pull_request:
    paths: ['**.yml', '**.yaml']

jobs:
  apme:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv pip install --system apme-engine
      - run: apme check .
```

## Workflow: Format Check

**File:** `apme-format.yml`

Checks YAML formatting without scanning for violations. Useful as a
separate job for fast feedback.

## Workflow: Full Pipeline

**File:** `apme-full.yml`

Runs format check, then full scan. Optionally runs remediation and
commits fixes (requires write permissions).

## Customization

### Scan a specific directory

```yaml
- run: apme check playbooks/
```

### JSON output for downstream processing

```yaml
- run: apme check . --json > apme-results.json
- uses: actions/upload-artifact@v4
  with:
    name: apme-results
    path: apme-results.json
```

### Target specific ansible-core version

```yaml
- run: apme check . --ansible-version 2.16
```

### Continue on violations (non-blocking)

```yaml
- run: apme check . || echo "::warning::APME found violations"
  continue-on-error: true
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | No violations found |
| 1 | Violations found, format changes needed, or error |

## Caching

UV automatically caches packages. For faster subsequent runs, the
`astral-sh/setup-uv` action handles caching automatically.
