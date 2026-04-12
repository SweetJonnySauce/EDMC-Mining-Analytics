#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"
PYTEST_TARGET="tests/test_harness_integration.py"
PYTEST_FILTER="session_data_file"

use_real_output=""
system_name=""

usage() {
  cat <<'EOF'
Usage:
  ./scripts/generate_test_session.sh [--real-output] [--system-name "Name"]

Options:
  --real-output         Write harness-generated outputs to the real repo session_data/ directory.
  --system-name NAME    Override the synthetic test system name.
  --help                Show this help text.

Examples:
  ./scripts/generate_test_session.sh
  ./scripts/generate_test_session.sh --system-name "My Test System"
  ./scripts/generate_test_session.sh --real-output
  ./scripts/generate_test_session.sh --real-output --system-name "My Test System"
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --real-output)
      use_real_output="1"
      shift
      ;;
    --system-name)
      if [[ $# -lt 2 ]]; then
        echo "error: --system-name requires a value" >&2
        exit 2
      fi
      system_name="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! -x "${VENV_PYTHON}" ]]; then
  echo "error: expected virtualenv python at ${VENV_PYTHON}" >&2
  echo "create it with: python3 -m venv .venv && source .venv/bin/activate && python -m pip install -r requirements-dev.txt" >&2
  exit 1
fi

cd "${ROOT_DIR}"

if [[ -n "${use_real_output}" ]]; then
  export EDMCMA_HARNESS_USE_REAL_OUTPUT="${use_real_output}"
fi

if [[ -n "${system_name}" ]]; then
  export EDMCMA_HARNESS_SYSTEM_NAME="${system_name}"
fi

"${VENV_PYTHON}" -m pytest "${PYTEST_TARGET}" -k "${PYTEST_FILTER}"

output_root="${ROOT_DIR}/tests/session_data"
if [[ -n "${use_real_output}" ]]; then
  output_root="${ROOT_DIR}/session_data"
fi

echo
echo "Latest generated files in ${output_root}:"
find "${output_root}" -maxdepth 1 -type f | sort
