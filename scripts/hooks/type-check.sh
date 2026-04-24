#!/usr/bin/env bash
# Stop — type-check completo en ambos stacks. Siempre exit 0 (informacional).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "=========================================="
echo "[type-check] Iniciando verificación de tipos"
echo "=========================================="

# ── Frontend: tsc --noEmit ─────────────────────────────────────────────────────
echo ""
echo "[type-check] TypeScript (frontend)..."
if cd "${REPO_ROOT}/frontend" && pnpm exec tsc --noEmit 2>&1; then
    echo "[type-check] TypeScript: OK"
else
    echo "[type-check] TypeScript: ERRORES ENCONTRADOS (ver arriba)"
fi

# ── Backend: mypy app/ ────────────────────────────────────────────────────────
echo ""
echo "[type-check] mypy (backend)..."
if cd "${REPO_ROOT}/backend" && .venv/bin/python -c "import mypy" 2>/dev/null; then
    if .venv/bin/python -m mypy app/ 2>&1; then
        echo "[type-check] mypy: OK"
    else
        echo "[type-check] mypy: ERRORES ENCONTRADOS (ver arriba)"
    fi
else
    echo "[type-check] mypy no instalado en venv — omitiendo. Para instalar: cd backend && .venv/bin/pip install mypy"
fi

echo ""
echo "[type-check] Listo."
exit 0
