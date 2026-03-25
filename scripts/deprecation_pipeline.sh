#!/usr/bin/env bash
# deprecation_pipeline.sh — Full pipeline: scrape → generate → report
#
# Usage:
#   ./scripts/deprecation_pipeline.sh              # full pipeline
#   ./scripts/deprecation_pipeline.sh --scrape-only # scrape only (update JSON)
#   ./scripts/deprecation_pipeline.sh --gen-only    # generate rules only (from existing data)
#   ./scripts/deprecation_pipeline.sh --dry-run     # preview without writing rule files
#   ./scripts/deprecation_pipeline.sh --ci          # CI mode: scrape, generate, exit 0/1

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON="${PYTHON:-python3}"
SCRAPE_ONLY=false
GEN_ONLY=false
CI_MODE=false
DRY_RUN=""
MIN_VERSION=""
RULES=""
FORCE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scrape-only) SCRAPE_ONLY=true; shift ;;
    --gen-only) GEN_ONLY=true; shift ;;
    --ci) CI_MODE=true; shift ;;
    --dry-run) DRY_RUN="--dry-run"; shift ;;
    --force) FORCE="--force"; shift ;;
    --min-version) MIN_VERSION="--min-version $2"; shift 2 ;;
    --rules) RULES="--rules $2"; shift 2 ;;
    -h|--help)
      cat <<EOF
Usage: $0 [OPTIONS]

Full pipeline: scrape ansible-core devel → update deprecations.json → generate M-rule scaffolds

Options:
  --scrape-only   Only run the scraper (update deprecations.json)
  --gen-only      Only generate rules (from existing deprecation_rules.yaml)
  --ci            CI mode: scrape + generate, exit 1 if new rules were created
  --dry-run       Preview what would be generated without writing files
  --force         Overwrite existing rule files
  --min-version   Filter scrape results to >= this version (e.g. 2.21)
  --rules         Only generate specific rules (comma-separated: M014,M015)
EOF
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

echo "╔══════════════════════════════════════════════════════╗"
echo "║  APME Deprecation Pipeline                          ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# Step 1: Scrape
if [[ "$GEN_ONLY" == "false" ]]; then
  echo "▶ Step 1: Scraping ansible-core devel for deprecation notices…"
  echo ""
  # shellcheck disable=SC2086
  $PYTHON scripts/scrape_ansible_deprecations.py \
    --audience content \
    $MIN_VERSION
  echo ""
  echo "  ✓ Deprecation data written to src/apme_engine/data/deprecations.json"
  echo ""
fi

if [[ "$SCRAPE_ONLY" == "true" ]]; then
  echo "Done (scrape-only mode)."
  exit 0
fi

# Step 2: Generate rule scaffolds
echo "▶ Step 2: Generating M-rule scaffolds…"
echo ""

GEN_ARGS="$DRY_RUN $RULES $FORCE"
if [[ "$CI_MODE" == "true" ]]; then
  GEN_ARGS="$GEN_ARGS --check"
fi

# shellcheck disable=SC2086
if $PYTHON scripts/generate_deprecation_rules.py $GEN_ARGS; then
  GEN_EXIT=0
else
  GEN_EXIT=$?
fi
echo ""

# Step 3: Summary
echo "▶ Step 3: Summary"
echo ""

OPA_COUNT=$(find src/apme_engine/validators/opa/bundle -name 'M*.rego' ! -name '*_test*' 2>/dev/null | wc -l | tr -d ' ')
NATIVE_COUNT=$(find src/apme_engine/validators/native/rules -name 'M*.py' 2>/dev/null | wc -l | tr -d ' ')

echo "  OPA M-rules:    $OPA_COUNT"
echo "  Native M-rules: $NATIVE_COUNT"
echo "  Total M-rules:  $((OPA_COUNT + NATIVE_COUNT))"
echo ""

if [[ "$CI_MODE" == "true" ]]; then
  if [[ "$GEN_EXIT" -ne 0 ]]; then
    echo "CI: New rules detected — a PR should be created."
    exit 1
  else
    echo "CI: No new rules to generate."
    exit 0
  fi
fi

echo "Next steps:"
echo "  1. Review generated rule files"
echo "  2. Run tests: pytest / opa test"
echo "  3. Update docs/ANSIBLE_CORE_MIGRATION.md"
echo "  4. Run: python scripts/generate_rule_catalog.py"
echo ""
echo "Done."
