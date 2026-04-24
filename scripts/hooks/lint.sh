#!/usr/bin/env bash
# PostToolUse — lint del archivo modificado. Siempre exit 0 (solo reporta).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

INPUT="$(cat)"

TOOL_NAME="$(python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('tool_name',''))" <<< "$INPUT")"

if [[ "$TOOL_NAME" != "Write" && "$TOOL_NAME" != "Edit" ]]; then
    exit 0
fi

FILE_PATH="$(python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
ti = d.get('tool_input', {})
print(ti.get('path', '') or ti.get('file_path', ''))
" <<< "$INPUT")"

if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

[[ "$FILE_PATH" != /* ]] && FILE_PATH="${REPO_ROOT}/${FILE_PATH}"

# ── Frontend: ESLint ──────────────────────────────────────────────────────────
if [[ "$FILE_PATH" == "${REPO_ROOT}/frontend/"* ]]; then
    REL_PATH="${FILE_PATH#${REPO_ROOT}/frontend/}"
    echo "[lint] eslint: frontend/${REL_PATH}"
    cd "${REPO_ROOT}/frontend" && pnpm exec eslint "${REL_PATH}" 2>&1 || true
    exit 0
fi

# ── Backend: ruff check --fix ─────────────────────────────────────────────────
if [[ "$FILE_PATH" == "${REPO_ROOT}/backend/"* ]]; then
    REL_PATH="${FILE_PATH#${REPO_ROOT}/backend/}"
    echo "[lint] ruff check --fix: backend/${REL_PATH}"
    cd "${REPO_ROOT}/backend" && .venv/bin/python -m ruff check --fix "${REL_PATH}" 2>&1 || true
    exit 0
fi

exit 0
