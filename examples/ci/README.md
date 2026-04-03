# CI/CD Integration Examples

Copy-paste ready examples for integrating APME into your CI/CD pipelines.

## Overview

APME provides several CLI commands suitable for CI/CD:

| Command | Purpose | Exit Code |
|---------|---------|-----------|
| `apme check .` | Scan for violations | 0 = pass, 1 = violations |
| `apme format --check .` | Check YAML formatting | 0 = clean, 1 = changes needed |
| `apme remediate .` | Auto-fix Tier 1 violations | 0 = success |

## Output Formats

```bash
apme check .                    # Terminal output (default)
apme check . --json             # JSON for automation
apme check . --json > results.json  # Save to file
```

## Installation

APME requires Python 3.10+ and can be installed via pip:

```bash
pip install apme-engine
```

## Examples

| Directory | Description |
|-----------|-------------|
| [github-actions/](github-actions/) | GitHub Actions workflow examples |
| [pre-commit/](pre-commit/) | Pre-commit hook configuration |

## Quick Start

### GitHub Actions

Copy one of these workflows to `.github/workflows/` in your Ansible repo:

```bash
# Download the basic check workflow
curl -o .github/workflows/apme.yml \
  https://raw.githubusercontent.com/ansible/apme/main/examples/ci/github-actions/apme-check.yml
```

### Pre-commit

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: apme-check
        name: APME Ansible check
        entry: apme check
        language: system
        types: [yaml]
        pass_filenames: false
```

See [pre-commit/README.md](pre-commit/README.md) for full setup instructions.
