#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Sync vendored harness files from EDMC-PluginLib.

Default upstream:
  https://github.com/dwomble/EDMC-PluginLib.git (ref: main)

This script syncs:
  - tests/harness.py
  - tests/edmc/

Usage:
  scripts/sync_harness.sh [options]

Options:
  --ref <ref>           Branch/tag/commit to sync from (default: main)
  --repo-url <url>      Upstream git URL
  --plugin-root <path>  Plugin repository root (default: auto-detected)
  --dry-run             Show what would change, do not write files
  --no-delete           Do not delete local files missing upstream (tests/edmc)
  --no-record           Do not update tests/VENDORED_HARNESS_SOURCE.md
  --keep-tmp            Keep temporary clone directory for inspection
  -h, --help            Show this help
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "error: required command not found: $1" >&2
    exit 1
  fi
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_URL="https://github.com/dwomble/EDMC-PluginLib.git"
REF="main"
DRY_RUN=0
DELETE_MISSING=1
WRITE_RECORD=1
KEEP_TMP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref)
      REF="${2:-}"
      shift 2
      ;;
    --repo-url)
      REPO_URL="${2:-}"
      shift 2
      ;;
    --plugin-root)
      PLUGIN_ROOT="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --no-delete)
      DELETE_MISSING=0
      shift
      ;;
    --no-record)
      WRITE_RECORD=0
      shift
      ;;
    --keep-tmp)
      KEEP_TMP=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

require_cmd git
require_cmd rsync
require_cmd cp
require_cmd mktemp
require_cmd date

PLUGIN_ROOT="$(cd "$PLUGIN_ROOT" && pwd)"
TARGET_HARNESS="$PLUGIN_ROOT/tests/harness.py"
TARGET_EDMC_DIR="$PLUGIN_ROOT/tests/edmc"
RECORD_PATH="$PLUGIN_ROOT/tests/VENDORED_HARNESS_SOURCE.md"

if [[ ! -d "$PLUGIN_ROOT/tests" ]]; then
  echo "error: expected tests directory at: $PLUGIN_ROOT/tests" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/edmc-harness-sync.XXXXXX")"
cleanup() {
  if [[ "$KEEP_TMP" -eq 1 ]]; then
    echo "tmp kept at: $TMP_DIR"
    return
  fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo "Cloning upstream harness source..."
git clone --quiet "$REPO_URL" "$TMP_DIR/upstream"
(
  cd "$TMP_DIR/upstream"
  git checkout --quiet "$REF"
)

UPSTREAM_SHA="$(git -C "$TMP_DIR/upstream" rev-parse HEAD)"
UPSTREAM_HARNESS="$TMP_DIR/upstream/tests/harness.py"
UPSTREAM_EDMC_DIR="$TMP_DIR/upstream/tests/edmc"

if [[ ! -f "$UPSTREAM_HARNESS" ]]; then
  echo "error: upstream file missing: tests/harness.py" >&2
  exit 1
fi
if [[ ! -d "$UPSTREAM_EDMC_DIR" ]]; then
  echo "error: upstream directory missing: tests/edmc/" >&2
  exit 1
fi

RSYNC_FLAGS=(-a)
if [[ "$DELETE_MISSING" -eq 1 ]]; then
  RSYNC_FLAGS+=(--delete)
fi
if [[ "$DRY_RUN" -eq 1 ]]; then
  RSYNC_FLAGS+=(-n --itemize-changes)
fi

echo "Upstream commit: $UPSTREAM_SHA"
echo "Sync source: $REPO_URL @ $REF"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo
  echo "[dry-run] tests/edmc changes:"
  rsync "${RSYNC_FLAGS[@]}" "$UPSTREAM_EDMC_DIR/" "$TARGET_EDMC_DIR/"

  if cmp -s "$UPSTREAM_HARNESS" "$TARGET_HARNESS"; then
    echo "[dry-run] tests/harness.py: no change"
  else
    echo "[dry-run] tests/harness.py: would be updated"
  fi

  if [[ "$WRITE_RECORD" -eq 1 ]]; then
    echo "[dry-run] $RECORD_PATH: would be updated"
  fi
  exit 0
fi

mkdir -p "$TARGET_EDMC_DIR"
cp "$UPSTREAM_HARNESS" "$TARGET_HARNESS"
rsync "${RSYNC_FLAGS[@]}" "$UPSTREAM_EDMC_DIR/" "$TARGET_EDMC_DIR/"

if [[ "$WRITE_RECORD" -eq 1 ]]; then
  SYNCED_AT_UTC="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  cat >"$RECORD_PATH" <<EOF
# Vendored Harness Source

- Upstream repository: $REPO_URL
- Upstream ref requested: $REF
- Upstream commit: $UPSTREAM_SHA
- Synced at (UTC): $SYNCED_AT_UTC

This file tracks provenance for vendored harness artifacts:
- tests/harness.py
- tests/edmc/
EOF
fi

echo "Sync complete."
echo "Updated:"
echo "  - tests/harness.py"
echo "  - tests/edmc/"
if [[ "$WRITE_RECORD" -eq 1 ]]; then
  echo "  - tests/VENDORED_HARNESS_SOURCE.md"
fi
echo
echo "Next suggested checks:"
echo "  source .venv/bin/activate && python -m pytest tests/test_harness_smoke.py tests/test_harness_integration.py"

