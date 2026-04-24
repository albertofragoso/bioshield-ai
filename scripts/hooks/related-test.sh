#!/usr/bin/env bash
# PostToolUse — corre el test de backend que corresponde al archivo modificado.
# Solo backend Python. Siempre exit 0.

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

# Solo archivos .py en backend/app/
if [[ "$FILE_PATH" != "${REPO_ROOT}/backend/"* ]] || [[ "$FILE_PATH" != *.py ]]; then
    exit 0
fi

REL_PATH="${FILE_PATH#${REPO_ROOT}/backend/}"

if [[ "$REL_PATH" != app/* ]]; then
    exit 0
fi

BASENAME="$(basename "${REL_PATH}" .py)"
SUBPATH="${REL_PATH#app/}"
SUBDIR="$(dirname "${SUBPATH}")"
[[ "$SUBDIR" == "." ]] && SUBDIR=""

TESTS_DIR="${REPO_ROOT}/backend/tests"

# Resolución: flat primero, luego nested
TEST_FILE=""
if [[ -f "${TESTS_DIR}/test_${BASENAME}.py" ]]; then
    TEST_FILE="${TESTS_DIR}/test_${BASENAME}.py"
elif [[ -n "$SUBDIR" && -f "${TESTS_DIR}/${SUBDIR}/test_${BASENAME}.py" ]]; then
    TEST_FILE="${TESTS_DIR}/${SUBDIR}/test_${BASENAME}.py"
fi

if [[ -z "$TEST_FILE" ]]; then
    echo "[related-test] Sin test para ${REL_PATH}, omitiendo."
    exit 0
fi

REL_TEST="${TEST_FILE#${REPO_ROOT}/backend/}"
echo "[related-test] pytest ${REL_TEST}"
cd "${REPO_ROOT}/backend" && .venv/bin/pytest "${REL_TEST}" -x -q 2>&1 || true

exit 0
