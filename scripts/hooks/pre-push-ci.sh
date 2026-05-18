#!/usr/bin/env bash
# PreToolUse — bloquea git push si el CI matrix no está verde.
# Exit 0: permitir. Exit 1: bloquear.

set -uo pipefail

INPUT="$(cat)"

TOOL_NAME="$(python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('tool_name',''))" <<< "$INPUT")"

if [[ "$TOOL_NAME" != "Bash" ]]; then
    exit 0
fi

CMD="$(python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('tool_input',{}).get('command',''))" <<< "$INPUT")"

# Only intercept git push — ignore all other Bash commands
if ! echo "$CMD" | grep -qE 'git\s+push'; then
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "[pre-push-ci] git push detected — running CI matrix before allowing push..."

cd "${REPO_ROOT}/backend"

echo "[pre-push-ci] ruff format --check..."
.venv/bin/python -m ruff format --check . 2>&1 || {
    echo "[pre-push-ci] BLOQUEADO: ruff format failed."
    echo "[pre-push-ci] Fix: cd backend && .venv/bin/python -m ruff format ."
    exit 1
}

echo "[pre-push-ci] ruff check..."
.venv/bin/python -m ruff check . 2>&1 || {
    echo "[pre-push-ci] BLOQUEADO: ruff lint errors."
    echo "[pre-push-ci] Fix: cd backend && .venv/bin/python -m ruff check --fix ."
    exit 1
}

echo "[pre-push-ci] mypy..."
.venv/bin/python -m mypy app/ 2>&1 || {
    echo "[pre-push-ci] BLOQUEADO: mypy type errors. Fix before pushing."
    exit 1
}

echo "[pre-push-ci] pytest..."
.venv/bin/python -m pytest 2>&1 || {
    echo "[pre-push-ci] BLOQUEADO: pytest failures. Fix failing tests before pushing."
    exit 1
}

echo "[pre-push-ci] All checks passed — proceeding with push."
exit 0
