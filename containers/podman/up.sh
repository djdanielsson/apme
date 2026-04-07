#!/usr/bin/env bash
# Start the APME pod (Primary, Native, Ansible, OPA, Gitleaks, Galaxy Proxy). Run from repo root.
# CLI is not part of the pod; use run-cli.sh to run a scan with CWD mounted.
#
# Cache host path: default is XDG cache (${XDG_CACHE_HOME:-$HOME/.cache}/apme).
# Override: APME_CACHE_HOST_PATH=/my/cache ./up.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# Default: XDG cache dir (persists across reboots); override with APME_CACHE_HOST_PATH
CACHE_PATH="${APME_CACHE_HOST_PATH:-${XDG_CACHE_HOME:-$HOME/.cache}/apme}"

if [[ "$CACHE_PATH" != /* ]]; then
  echo "ERROR: APME_CACHE_HOST_PATH must be an absolute path (got: $CACHE_PATH)" >&2
  exit 1
fi

if [[ "$CACHE_PATH" == *$'\n'* ]]; then
  echo "ERROR: APME_CACHE_HOST_PATH must not contain newlines" >&2
  exit 1
fi

mkdir -p "$CACHE_PATH"

# Load Abbenay secrets (.env) if present.
ABBENAY_ENV="$ROOT/containers/abbenay/.env"
if [[ -f "$ABBENAY_ENV" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ABBENAY_ENV"
  set +a
fi
OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"
VERTEX_ANTHROPIC_API_KEY="${VERTEX_ANTHROPIC_API_KEY:-}"
APME_AI_MODEL="${APME_AI_MODEL:-}"
APME_FEEDBACK_ENABLED="${APME_FEEDBACK_ENABLED:-true}"
APME_FEEDBACK_GITHUB_REPO="${APME_FEEDBACK_GITHUB_REPO:-}"
APME_FEEDBACK_GITHUB_TOKEN="${APME_FEEDBACK_GITHUB_TOKEN:-}"

# Optional: CA bundle for self-hosted model endpoints with internal/self-signed CAs.
# Set ABBENAY_CA_BUNDLE to the absolute path of a PEM CA bundle file.
ABBENAY_CA_BUNDLE="${ABBENAY_CA_BUNDLE:-}"
if [[ -n "$ABBENAY_CA_BUNDLE" ]]; then
  if [[ "$ABBENAY_CA_BUNDLE" != /* ]]; then
    echo "ERROR: ABBENAY_CA_BUNDLE must be an absolute path (got: $ABBENAY_CA_BUNDLE)" >&2
    exit 1
  fi
  if [[ "$ABBENAY_CA_BUNDLE" == *$'\n'* ]]; then
    echo "ERROR: ABBENAY_CA_BUNDLE must not contain newlines" >&2
    exit 1
  fi
  if [[ ! -f "$ABBENAY_CA_BUNDLE" ]]; then
    echo "ERROR: ABBENAY_CA_BUNDLE points to a file that does not exist: $ABBENAY_CA_BUNDLE" >&2
    exit 1
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: ABBENAY_CA_BUNDLE requires python3 to patch the pod YAML, but python3 was not found in PATH" >&2
    exit 1
  fi
fi

# Tear down any existing pod so we get a clean start.
if podman pod exists apme-pod 2>/dev/null; then
  echo "Stopping existing apme-pod..."
  podman pod stop apme-pod 2>/dev/null || true
  podman pod rm apme-pod 2>/dev/null || true
fi

# Pod YAML cannot use env vars; we inject values via envsubst.
# CACHE_PATH is escaped for sed since it may contain special chars;
# everything else goes through envsubst so secrets stay out of argv.
ESCAPED_PATH=$(printf '%s\n' "$CACHE_PATH" | sed -e 's/\\/\\\\/g' -e 's/[&|]/\\&/g')
export OPENROUTER_API_KEY VERTEX_ANTHROPIC_API_KEY APME_AI_MODEL APME_ROOT="$ROOT"
export APME_FEEDBACK_ENABLED APME_FEEDBACK_GITHUB_REPO APME_FEEDBACK_GITHUB_TOKEN

# Build the pod YAML: substitute cache path and env vars.
POD_YAML=$(sed "s|path: __APME_CACHE_PATH__|path: ${ESCAPED_PATH}|" containers/podman/pod.yaml \
  | envsubst '$OPENROUTER_API_KEY $VERTEX_ANTHROPIC_API_KEY $APME_AI_MODEL $APME_ROOT $APME_FEEDBACK_ENABLED $APME_FEEDBACK_GITHUB_REPO $APME_FEEDBACK_GITHUB_TOKEN')

# When a CA bundle is provided, inject NODE_EXTRA_CA_CERTS env var, volume mount,
# and volume definition into the Abbenay container section of the pod YAML.
if [[ -n "$ABBENAY_CA_BUNDLE" ]]; then
  CA_MOUNT_PATH="/etc/ssl/certs/custom-ca-bundle.pem"
  POD_YAML=$(python3 -c "
import json, sys, os
yaml = sys.stdin.read()
ca_path = os.environ['ABBENAY_CA_BUNDLE']
mount = '$CA_MOUNT_PATH'
ca_path_yaml = json.dumps(ca_path)
mount_yaml = json.dumps(mount)
env_marker = '        - name: XDG_RUNTIME_DIR'
vol_marker = '          readOnly: true\n    - name: galaxy-proxy'
if env_marker not in yaml or vol_marker not in yaml:
    print('ERROR: pod.yaml markers not found; CA bundle injection failed', file=sys.stderr)
    sys.exit(1)
yaml = yaml.replace(
    env_marker,
    '        - name: NODE_EXTRA_CA_CERTS\n'
    '          value: ' + mount_yaml + '\n'
    '        ' + env_marker.lstrip())
yaml = yaml.replace(
    vol_marker,
    '          readOnly: true\n'
    '        - name: abbenay-ca-bundle\n'
    '          mountPath: ' + mount_yaml + '\n'
    '          readOnly: true\n'
    '    - name: galaxy-proxy')
yaml = yaml.rstrip() + '\n' \
    '    - name: abbenay-ca-bundle\n' \
    '      hostPath:\n' \
    '        path: ' + ca_path_yaml + '\n' \
    '        type: File\n'
print(yaml)
" <<< "$POD_YAML")
  echo "CA bundle enabled: $ABBENAY_CA_BUNDLE -> $CA_MOUNT_PATH (inside container)"
fi

echo "$POD_YAML" | podman play kube -

echo "Pod apme-pod started (cache: $CACHE_PATH). Run a scan: containers/podman/run-cli.sh"

if [[ -n "$APME_FEEDBACK_GITHUB_REPO" && -n "$APME_FEEDBACK_GITHUB_TOKEN" ]]; then
  echo "Issue reporting enabled (repo: $APME_FEEDBACK_GITHUB_REPO)"
else
  echo "Issue reporting disabled. To enable, export APME_FEEDBACK_GITHUB_REPO and APME_FEEDBACK_GITHUB_TOKEN."
fi
