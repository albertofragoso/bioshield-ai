#!/usr/bin/env bash
# PreToolUse — bloquea comandos Bash destructivos conocidos.
# Exit 0: permitir. Exit 1: bloquear.

set -uo pipefail

INPUT="$(cat)"

TOOL_NAME="$(python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('tool_name',''))" <<< "$INPUT")"

if [[ "$TOOL_NAME" != "Bash" ]]; then
    exit 0
fi

CMD="$(python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('tool_input',{}).get('command',''))" <<< "$INPUT")"

block() {
    local label="$1"
    echo "[safety-gate] BLOQUEADO: el comando coincide con el patrón prohibido '${label}'." >&2
    echo "[safety-gate] Comando: ${CMD}" >&2
    exit 1
}

echo "$CMD" | grep -qiE 'rm\s+-[a-zA-Z]*r[a-zA-Z]*f|rm\s+-[a-zA-Z]*f[a-zA-Z]*r' && block "rm -rf"
echo "$CMD" | grep -qiE 'git\s+push\s+.*--force'                                   && block "git push --force"
echo "$CMD" | grep -qiE 'git\s+reset\s+.*--hard'                                   && block "git reset --hard"
echo "$CMD" | grep -qiE 'DROP\s+DATABASE'                                           && block "DROP DATABASE"
echo "$CMD" | grep -qiE 'TRUNCATE\s+.*--'                                          && block "TRUNCATE --"

exit 0
