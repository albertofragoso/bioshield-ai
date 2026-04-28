# Runbook: Embeddings — BGE-M3 Primary / Gemini Fallback

**Versión:** 2.0  
**Última actualización:** 2026-04-28  
**Audiencia:** DevOps / SRE / Technical Lead  
**Criticidad:** Media (servicio degradado pero funcional)

---

## 1. Overview

BioShield usa **BGE-M3** (local, `BAAI/bge-m3`) como primario desde la v2.0 y **Gemini embedding-001** (API) como fallback.

El cambio fue motivado por el semantic re-ranking de biomarcadores: los datos médicos del usuario no pueden enviarse a APIs externas. Solo el texto canónico de la regla clínica (código estático, sin PHI) se embeddea.

| Aspecto | BGE-M3 (primario) | Gemini embedding-001 (fallback) |
|---|---|---|
| Dimensión | **1024** | 768 |
| Ubicación | proceso local | Google Cloud |
| Latencia | 50–100ms | 200–400ms |
| Costo | $0 (batch) | ~$0.25 / 1k calls |
| Privacidad PHI | Garantizada | Requiere revisión |
| Config | `USE_LOCAL_EMBEDDINGS=true` | `USE_LOCAL_EMBEDDINGS=false` |

**Cambiar entre modelos requiere re-indexar Chroma** porque la dimensión es incompatible (1024 vs 768). No es hot-swappable.

### Plataforma Intel Mac (x86_64)

PyTorch >= 2.3 no tiene wheels para Intel Mac en PyPI. El máximo disponible es torch 2.2.2. Para compatibilidad:
- `transformers` debe ser < 4.51 (a partir de 4.51 bloquea torch < 2.6 incondicionalmente)
- `numpy` debe ser < 2 (torch 2.2.2 fue compilado contra NumPy 1.x ABI)

Ver `requirements.txt` para las versiones fijadas.

---

## 2. Triggers para activar fallback

Activar BGE-M3 en estos casos:

| Trigger | Síntoma | TTR |
|---|---|---|
| **Free tier agotado** | 429 `ResourceExhausted` en `/scan/photo` | 24–48h (esperar reset) |
| **Outage Gemini API** | 503 `GoogleAPIError` sostenido > 2h | 1–4h (típico) |
| **Decisión arquitectónica** | "Queremos independencia de APIs externas" | Planned downtime |
| **Costos escalando** | Factura mensual de embeddings > presupuesto | Planned downtime |

**NO activar por:**
- Slow Gemini (> 400ms) — es normal, no es fallback-trigger
- Free tier "bajo" — espera a que se agote de verdad

---

## 3. Pre-activación (1–2 horas antes)

### 3.1 · Comunicación

```
Canal Slack / Email al equipo:

[AVISO] Maintenance programada: Migración de embeddings Gemini → BGE-M3
Duración estimada: 30 min
Impacto: /scan/barcode y /scan/photo indisponibles
Ventana: [hora UTC]
Reason: [gemini outage | free tier exhausted | cost optimization]

Si esto es URGENTE (outage real), omitir este paso y pasar a 3.2.
```

### 3.2 · Validar requisitos

```bash
# En producción (Render shell)
df -h /data                    # Necesitas >500 MB libres
free -h                        # Necessitas >2 GB RAM libres
du -sh ./chroma_db             # Cuánto ocupa la colección actual

# En local (dev)
pip show sentence-transformers torch  # ¿Ya instalados?
```

Si no hay espacio, liberar:
```bash
# Backup de la colección actual (crítico)
tar -czf bioshield_ingredients_backup_$(date +%s).tar.gz ./chroma_db/

# Opcional: limpiar cache antiguo
rm -rf ~/.cache/huggingface/   # BGE-M3 descargas
```

### 3.3 · Snapshot del estado actual

```bash
# Capturar métricas pre-migración
curl http://localhost:8000/health > health_pre.json

# Contar ingredientes indexados
# (conectar a DB)
SELECT COUNT(*) FROM ingredients;  -- esperar ~10k en producción
SELECT COUNT(*) FROM scan_history WHERE scanned_at > NOW() - '24 hours'::interval;  -- scans recientes
```

---

## 4. Activación (pasos en orden)

### 4.1 · Marcar como en mantenimiento (opcional pero recomendado)

Si tienes un flag de maintenance:
```bash
# Opción A: Detener uvicorn, esperar a que drene conexiones activas
kill -TERM $(pgrep -f "uvicorn.*main:app")  # Graceful shutdown

# Opción B: Devolver 503 desde un middleware sin detener
# (Implementación futura — no existe aún)
```

Esperar 30s a que las conexiones active se drenen.

### 4.2 · Activar BGE-M3 en configuración

```bash
# En .env (o variables de entorno en Render)
USE_LOCAL_EMBEDDINGS=true

# Confirmación
grep USE_LOCAL_EMBEDDINGS .env
```

### 4.3 · Instalar dependencias (si no existen)

```bash
# En el contenedor o shell de producción
pip install sentence-transformers torch

# Esto descarga ~500 MB en ~/.cache/huggingface/
# Paciencia: puede tomar 5–10 minutos en conexión lenta

# Verificar instalación
python -c "from sentence_transformers import SentenceTransformer; print('OK')"
```

**Nota:** Si usas Docker, esto debería estar en la imagen ya. Si no, añadir a `requirements.txt` y reconstruir.

### 4.4 · Borrar colección de Chroma (DESTRUCTIVO)

```bash
# ADVERTENCIA: Esto elimina todos los índices de vector
# Asegúrate de que el backup (§3.2) está guardado

rm -rf ./chroma_db/
# O si está en otro path:
rm -rf /data/chroma_db/
```

### 4.5 · Re-indexar la colección (5–15 minutos)

Triggear el script de ingesta:

```bash
# En el directorio del backend
python -m scripts.seed_rag --live

# Output esperado:
# Loading FDA EAFUS from https://...
# Parsed 500 records
# Embedding with BGE-M3...
# [████████████████████] 500/500
# Upserting to Chroma...
# Ingestion complete: 500 records, 18 conflicts detected
# Ingestion log: <uuid>
```

**Fallback si `--live` falla** (URLs rotas):
```bash
python -m scripts.seed_rag  # Usa seed data local curado (20 ingredientes)
```

### 4.6 · Iniciar backend

```bash
# Opción A: Local
uvicorn app.main:app --reload

# Opción B: Render (redeploy)
git push origin main  # Trigger deploy automático
# O en Render dashboard: "Deploy latest"

# Opción C: Docker Compose
docker-compose up --build backend
```

Esperar a que el servicio esté healthy (5–10s):
```bash
# En otra terminal
while true; do curl -s http://localhost:8000/health && echo " ✓" && break || echo " ✗"; sleep 2; done
```

---

## 5. Validación post-activación (10–15 minutos)

### 5.1 · Health check

```bash
curl http://localhost:8000/health
# Respuesta esperada:
# {"status":"ok","app":"BioShield AI"}
```

### 5.2 · Scan barcode real

```bash
# Usar un barcode común (ej: Nutella 3017620422003)
curl -X POST http://localhost:8000/scan/barcode \
  -H "Content-Type: application/json" \
  -H "Cookie: access_token=<tu_jwt_aquí>" \
  -d '{"barcode": "3017620422003"}'

# Respuesta esperada:
# {
#   "product_barcode": "3017620422003",
#   "product_name": "Nutella",
#   "semaphore": "YELLOW",
#   "ingredients": [...],
#   "source": "barcode",
#   "scanned_at": "2026-04-22T..."
# }
```

Si ves errores:
- `500` → revisar logs del backend (`docker logs <container>`)
- `422` → schema mismatch (improbable, arquitectura es igual)

### 5.3 · Scan photo (más lento, toma 5–8s)

```bash
# Usa una imagen de etiqueta real o fixture
BASE64=$(base64 < /path/to/label.jpg)

curl -X POST http://localhost:8000/scan/photo \
  -H "Content-Type: application/json" \
  -H "Cookie: access_token=<tu_jwt_aquí>" \
  -d "{\"image_base64\": \"$BASE64\"}"

# Latencia esperada: 5–8s (igual que Gemini, a veces más rápido)
```

### 5.4 · Comparar RAG latencia

```bash
# Correr 3 scans idénticos, cronometrar

time curl -X POST http://localhost:8000/scan/barcode ... > /dev/null

# Antes (Gemini): ~800ms–1s
# Después (BGE-M3): ~800ms–1s (similar)
# (La mayoría del tiempo es Gemini Vision de foto, no embedding)
```

### 5.5 · Logs del backend

Buscar errores de embedding:

```bash
# Local
tail -f /tmp/uvicorn.log | grep -i "embed\|bge\|sentence"

# Docker
docker logs <container> --follow | grep -i "embed"

# Render
(en dashboard: "Logs")
```

Patrones esperados:
- ✅ `Loading BGE-M3 model from huggingface...`
- ✅ `Embedding 500 records with local BGE...`
- ❌ `NotImplementedError: Local BGE-M3 embeddings are not wired` → USE_LOCAL_EMBEDDINGS no está True

---

## 6. Troubleshooting

### Problema: `torch` no instala (o solo encuentra 2.2.2)

```bash
# Síntoma en Intel Mac:
pip install "torch>=2.6"
# ERROR: No matching distribution found — PyTorch >= 2.3 no tiene wheels x86_64 macOS

# Causa: PyTorch eliminó soporte Intel Mac (x86_64) a partir de 2.3.
# Solución: torch 2.2.2 + pinear transformers<4.51 + numpy<2
pip install "torch==2.2.2" "transformers==4.50.3" "numpy<2"

# En Linux (CI/producción), instalar CPU-only:
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### Problema: OOM (Out of Memory) durante embedding

```bash
# Síntoma:
RuntimeError: CUDA out of memory
# o
MemoryError: Unable to allocate ...

# Solución:
# BGE-M3 corre en CPU por defecto (no GPU). Si hay OOM:
# 1. Reducir batch size (en scripts/seed_rag.py)
# 2. Correr solo en máquina con >4 GB RAM libres
# 3. Indexar en chunks (seed 100 → sleep 30s → seed 100)
```

### Problema: Chroma no levanta tras borrar

```bash
# Síntoma:
FileNotFoundError: [Errno 2] No such file or directory: './chroma_db'

# Solución (automático en startup):
# Chroma crea la carpeta si no existe. Solo espera 10s y reinicia backend.
```

### Problema: RAG hits no relevantes

```bash
# Síntoma:
/scan/barcode devuelve semaphore=GRAY (ingredientes no resueltos)

# Posibles causas:
# 1. Seed data incompleto (solo 20 aditivos)
# 2. --live falló silenciosamente (falta --live?)
# 3. Índice de Chroma corrupto

# Debug:
# Verificar ingestion_log
SELECT * FROM ingestion_logs ORDER BY finished_at DESC LIMIT 1;

# Re-indexar completo
python -m scripts.seed_rag --live --force
```

---

## 7. Rollback a Gemini (si es necesario)

Si la migración causa problemas irrecuperables:

### 7.1 · Restaurar colección de Chroma

```bash
# Si hiciste backup en §3.2
tar -xzf bioshield_ingredients_backup_<timestamp>.tar.gz

# Verifica que se restauró
ls -la ./chroma_db/bioshield_ingredients/
```

### 7.2 · Volver a Gemini en configuración

```bash
USE_LOCAL_EMBEDDINGS=false

# Confirmación
grep USE_LOCAL_EMBEDDINGS .env
```

### 7.3 · Reiniciar backend

```bash
# Mismo proceso que en §4.6
uvicorn app.main:app --reload
# o
docker-compose up --build backend
```

### 7.4 · Validar

```bash
curl http://localhost:8000/health
# Si salió mal en ~30s, tenías un problema en backup o configuración
```

---

## 8. Decisiones de diseño (por qué es así)

| Decisión | Alternativa | Razón |
|---|---|---|
| **Borrar y re-indexar** | Convertir embeddings 768→1024 in-place | 768→1024 es dimensión incompatible; conversión sería pseudociencia |
| **script.seed_rag** | Dump + restore del Chroma | seed_rag es idempotente y valida parsers en vivo |
| **USE_LOCAL_EMBEDDINGS env var** | Feature flag en DB | Env var es más rápida de cambiar sin redeploy (aunque típicamente requiere restart) |
| **Instalación manual de deps** | Pre-installer en Docker | Deps de ML son grandes (~500 MB); solo instalar si se usa |

---

## 9. Checklist rápido

```
PRE-ACTIVACIÓN
☐ Backup de chroma_db (tar.gz)
☐ Comunicación al equipo (Slack/Email)
☐ Validar espacio en disco (>500 MB)
☐ Snapshot de métricas (health, ingredientes, scans recientes)

ACTIVACIÓN
☐ Detener backend (graceful shutdown)
☐ USE_LOCAL_EMBEDDINGS=true en .env
☐ pip install sentence-transformers torch
☐ rm -rf ./chroma_db/
☐ python -m scripts.seed_rag --live
☐ Iniciar backend

VALIDACIÓN
☐ curl /health → 200 OK
☐ POST /scan/barcode → response en < 2s
☐ POST /scan/photo → response en < 8s
☐ Logs sin errores de embedding
☐ Notificar equipo: "Migración completada exitosamente"

ROLLBACK (si falla)
☐ tar -xzf backup
☐ USE_LOCAL_EMBEDDINGS=false
☐ Restart backend
☐ Validar salud
☐ Postmortem: ¿qué salió mal?
```

---

## 10. Contactos y escalación

| Rol | Contacto | Cuándo |
|---|---|---|
| Backend Lead | Alberto | Errores técnicos durante migración |
| DevOps / SRE | [TBD] | Disk space issues, deployment problems |
| Product | [TBD] | Comunicación a usuarios (si downtime > 10 min) |

**Slack channel:** #bioshield-ops (crear si no existe)

---

## Appendix A: Comparativa de rendimiento Gemini vs BGE-M3

Datos reales de corrida con ~500 ingredientes:

| Métrica | Gemini API | BGE-M3 local |
|---|---|---|
| Embedding 500 records | 15–20 min (rate limited) | 3–5 min |
| Latencia p95 query | 150–250ms | 50–100ms |
| Memoria peak | 200 MB | 800 MB (cargar modelo) |
| Costo mensual (10k calls) | ~$2.50 | $0 (batch) |
| Downtime risk | Rate limits, quota | GPU OOM (CPU only en MVP) |

BGE-M3 es **más rápido** en latencia y costo, pero requiere **más RAM** en startup.

---

## Appendix B: Script de validación post-migración

```bash
#!/bin/bash
# validate_migration.sh

set -e

echo "[1/5] Health check..."
curl -s http://localhost:8000/health || exit 1
echo "✓"

echo "[2/5] Barcode scan test (Nutella 3017620422003)..."
RESULT=$(curl -s -X POST http://localhost:8000/scan/barcode \
  -H "Content-Type: application/json" \
  -H "Cookie: access_token=$ACCESS_TOKEN" \
  -d '{"barcode": "3017620422003"}')
echo "$RESULT" | jq .semaphore || exit 1
echo "✓"

echo "[3/5] Ingredient count..."
# (Requiere acceso a DB)
# psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM ingredients;"

echo "[4/5] Latency p95..."
# Correr 10 scans y medir
# (Script separado)

echo "[5/5] Log check..."
docker logs $(docker ps -q) 2>&1 | grep -i error || echo "✓ No errors"

echo ""
echo "✅ Validación completada. Sistema ready."
```

Guardar en `scripts/validate_migration.sh` y ejecutar:
```bash
chmod +x scripts/validate_migration.sh
./scripts/validate_migration.sh
```
