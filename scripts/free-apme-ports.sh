#!/usr/bin/env bash
set -euo pipefail

PORTS_STR="8080 8081 8765 50051 50053 50054 50055 50056 50057 50058 50059 50060"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

log() {
  printf '[apme-cleanup] %s\n' "$*"
}

list_apme_listeners() {
  ss -ltnpH 2>/dev/null | awk -v ports="${PORTS_STR}" '
    BEGIN {
      count = split(ports, items, " ")
      for (i = 1; i <= count; i++) {
        wanted[items[i]] = 1
      }
    }
    {
      addr = $4
      port = addr
      sub(/^.*:/, "", port)
      if (port in wanted) {
        print
      }
    }
  '
}

collect_apme_pids() {
  list_apme_listeners | awk '
    {
      line = $0
      while (match(line, /pid=[0-9]+/)) {
        pid = substr(line, RSTART + 4, RLENGTH - 4)
        print pid
        line = substr(line, RSTART + RLENGTH)
      }
    }
  ' | sort -u
}

log "Stopping APME pod via tox if possible..."
if command -v tox >/dev/null 2>&1 && [[ -f "${REPO_ROOT}/tox.ini" ]]; then
  (
    cd "${REPO_ROOT}"
    tox -e down >/dev/null 2>&1 || true
  )
fi

log "Removing podman pod apme-pod if it still exists..."
if command -v podman >/dev/null 2>&1; then
  podman pod rm -f apme-pod >/dev/null 2>&1 || true
fi

mapfile -t pids < <(collect_apme_pids || true)

if ((${#pids[@]} > 0)); then
  log "Sending SIGTERM to lingering listener PIDs: ${pids[*]}"
  kill "${pids[@]}" 2>/dev/null || true
  sleep 1
fi

mapfile -t remaining < <(collect_apme_pids || true)

if ((${#remaining[@]} > 0)); then
  log "Escalating to SIGKILL for stubborn PIDs: ${remaining[*]}"
  kill -9 "${remaining[@]}" 2>/dev/null || true
  sleep 1
fi

leftovers="$(list_apme_listeners || true)"
if [[ -n "${leftovers}" ]]; then
  log "Some APME ports are still busy:"
  printf '%s\n' "${leftovers}"
  exit 1
fi

log "APME ports are free: ${PORTS_STR}"
