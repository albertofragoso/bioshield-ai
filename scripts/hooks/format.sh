#!/usr/bin/env bash
# PostToolUse — formatea el archivo modificado. Siempre exit 0.

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

# ── Frontend: Prettier ────────────────────────────────────────────────────────
if [[ "$FILE_PATH" == "${REPO_ROOT}/frontend/"* ]]; then
    REL_PATH="${FILE_PATH#${REPO_ROOT}/frontend/}"
    echo "[format] prettier --write: frontend/${REL_PATH}"
    cd "${REPO_ROOT}/frontend" && pnpm exec prettier --write "${REL_PATH}" 2>&1 || true
    exit 0
fi

# ── Backend: ruff format ──────────────────────────────────────────────────────
if [[ "$FILE_PATH" == "${REPO_ROOT}/backend/"* ]]; then
    REL_PATH="${FILE_PATH#${REPO_ROOT}/backend/}"
    echo "[format] ruff format: backend/${REL_PATH}"
    cd "${REPO_ROOT}/backend" && .venv/bin/python -m ruff format "${REL_PATH}" 2>&1 || true
    exit 0
fi

exit 0
