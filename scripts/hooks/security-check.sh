#!/usr/bin/env bash
# PreToolUse — escanea credenciales hardcodeadas en comandos y contenido de archivos.
# Exit 0: permitir (o advertir). Exit 1: bloquear (credencial confirmada encontrada).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

INPUT="$(cat)"

TOOL_NAME="$(python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('tool_name',''))" <<< "$INPUT")"

# ── Bash tool ─────────────────────────────────────────────────────────────────
if [[ "$TOOL_NAME" == "Bash" ]]; then
    CMD="$(python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('tool_input',{}).get('command',''))" <<< "$INPUT")"

    if echo "$CMD" | grep -qiE '(PASSWORD|API_KEY|SECRET_KEY|AUTH_TOKEN|password|api_key|secret_key|auth_token)\s*=\s*["\x27][^"]{6,}["\x27]'; then
        echo "[security-check] ERROR: credencial hardcodeada detectada en comando Bash. Bloqueando." >&2
        exit 1
    fi

    if echo "$CMD" | grep -qiE 'sk-[A-Za-z0-9]{32,}|AKIA[0-9A-Z]{16}'; then
        echo "[security-check] ERROR: clave API detectada en comando Bash. Bloqueando." >&2
        exit 1
    fi

    exit 0
fi

# ── Write / Edit tools ────────────────────────────────────────────────────────
if [[ "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "Edit" ]]; then
    CONTENT="$(python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
ti = d.get('tool_input', {})
print(ti.get('content', '') or ti.get('new_string', '') or ti.get('new_content', ''))
" <<< "$INPUT")"

    # Patrones que bloquean (credenciales literales claras)
    if echo "$CONTENT" | grep -qE 'sk-[A-Za-z0-9]{32,}'; then
        echo "[security-check] ERROR: clave OpenAI/Anthropic detectada en contenido. Bloqueando." >&2
        exit 1
    fi

    if echo "$CONTENT" | grep -qE 'AKIA[0-9A-Z]{16}'; then
        echo "[security-check] ERROR: clave AWS detectada en contenido. Bloqueando." >&2
        exit 1
    fi

    if echo "$CONTENT" | grep -qiE '(PASSWORD|API_KEY|SECRET_KEY|AUTH_TOKEN|password|api_key|secret_key|auth_token)\s*=\s*["\x27][^"]{8,}["\x27]'; then
        echo "[security-check] ERROR: credencial hardcodeada detectada en contenido. Bloqueando." >&2
        exit 1
    fi

    # Patrones de advertencia (no bloquean)
    if echo "$CONTENT" | grep -qiE 'Bearer\s+[A-Za-z0-9._-]{20,}|ghp_[A-Za-z0-9]{36}'; then
        echo "[security-check] WARNING: posible token literal encontrado. Revisar antes de commitear." >&2
    fi

    exit 0
fi

exit 0
