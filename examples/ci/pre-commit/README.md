# Pre-commit Hook Configuration

Run APME checks locally before committing Ansible content.

## Prerequisites

1. Install pre-commit:
   ```bash
   pip install pre-commit
   # or
   uv tool install pre-commit
   ```

2. Install APME:
   ```bash
   pip install apme-engine
   # or
   uv pip install apme-engine
   ```

## Setup

1. Copy the example config to your repo:
   ```bash
   cp .pre-commit-config.yaml.example /path/to/your/repo/.pre-commit-config.yaml
   ```

2. Or add the hooks to your existing `.pre-commit-config.yaml`:
   ```yaml
   repos:
     # ... your other hooks ...

     - repo: local
       hooks:
         - id: apme-check
           name: APME Ansible check
           entry: apme check
           language: system
           types: [yaml]
           pass_filenames: false

         - id: apme-format
           name: APME YAML format
           entry: apme format --check
           language: system
           types: [yaml]
           pass_filenames: false
   ```

3. Install the hooks:
   ```bash
   pre-commit install
   ```

## Usage

### Automatic (on commit)

Once installed, hooks run automatically on `git commit`:

```bash
git add playbook.yml
git commit -m "Add new playbook"
# APME checks run here - commit blocked if violations found
```

### Manual

Run hooks manually on all files:

```bash
pre-commit run --all-files
```

Run specific hook:

```bash
pre-commit run apme-check --all-files
pre-commit run apme-format --all-files
```

## Hook Options

### Check only (default)

```yaml
- id: apme-check
  name: APME Ansible check
  entry: apme check
  language: system
  types: [yaml]
  pass_filenames: false
```

### Format check only

```yaml
- id: apme-format
  name: APME YAML format
  entry: apme format --check
  language: system
  types: [yaml]
  pass_filenames: false
```

### Specific directory

```yaml
- id: apme-check
  name: APME Ansible check
  entry: apme check playbooks/
  language: system
  pass_filenames: false
```

### Non-blocking (warn only)

```yaml
- id: apme-check
  name: APME Ansible check
  entry: apme check
  language: system
  types: [yaml]
  pass_filenames: false
  verbose: true
  stages: [manual]  # Only run with --hook-stage manual
```

## Troubleshooting

### "apme: command not found"

Ensure APME is installed and in your PATH:

```bash
which apme
# Should print path like: /usr/local/bin/apme or ~/.local/bin/apme
```

If using a virtualenv, either:
- Install APME globally: `pip install --user apme-engine`
- Or activate the venv before committing

### Slow on large repos

APME scans all YAML files by default. For large repos, scope to a specific
directory:

```yaml
entry: apme check playbooks/
```

### Skip hooks temporarily

```bash
git commit --no-verify -m "WIP: skip hooks"
```
