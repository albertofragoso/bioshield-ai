# Auditoría de Production Readiness — BioShield AI

**Fecha:** 2026-06-26  
**Auditor:** Senior Software Engineer (automated audit via codebase analysis)  
**Entornos auditados:** dev (SQLite + docker-compose.yml) y prod (Oracle Cloud + Cloudflare Tunnel + docker-compose.prod.yml)  
**Propósito:** Priorizar roadmap hacia madurez de producción

---

## Resumen ejecutivo

| Pilar | Riesgo | Estado |
|-------|--------|--------|
| 1. Spec-Driven Development | 🟡 Medio | Artefactos parciales, sin flujo formal |
| 2. Documentación | 🟢 Bajo | Sólida — múltiples capas, actualizada |
| 3. Version Control | 🟡 Medio | Commits directos a main, sin branch protection |
| 4. Testing | 🟡 Medio | Cobertura amplia pero sin threshold y 1 test failing |
| 5. AuthN vs AuthZ | 🟡 Medio | AuthN robusta; AuthZ solo a nivel app, sin RLS |
| 6. Error Handling | 🟡 Medio | Global handler OK; falta 422 custom + timeouts LLM |
| 7. Bases de Datos | 🟡 Medio | Índices básicos OK; faltan compuestos y backup pre-deploy |
| 8. Seguridad | 🟡 Medio | Base sólida post-audit; brechas puntuales subsisten |
| 9. Hosting | 🔴 Alto | SPOF — single VM sin staging ni redundancia |
| 10. Despliegue | 🔴 Alto | Deploy manual, sin rollback automatizado |
| 11. Observabilidad | 🔴 Alto | Logs estructurados OK; cero métricas, alertas ni trazas |

**Prioridad de roadmap recomendada:** Pilares 11 → 10 → 9 → 3 → 5

---

## Pilar 1 — Spec-Driven Development

**Riesgo: 🟡 Medio**

### Hallazgos

**Positivos:**
- `PRD.md` en raíz del repo define el producto.
- `docs/plans/` contiene planes con fecha (ej. `2026-06-06-001-feat-langgraph-node-timing-plan.md`).
- `docs/brainstorms/`, `docs/reviews/`, `docs/design/` demuestran proceso iterativo.
- `.claude/plans/backend.md` y `.claude/plans/frontend.md` sirven como planes vivos.
- Los PRs (#31–#35) muestran que la mayoría de features pasaron por branch → PR → merge.

**Gaps:**
- Solo 1 plan formal en `docs/plans/` para ~15 PRs mergeados. La mayoría de features no tienen artefacto de especificación previo.
- No existe un directorio de `changes/` (changelog estructurado por decisión), ni una plantilla de RFC/ADR.
- Commits directos a `main` sin PR: `a4c1ed4b` (prod config), `0106087e` (fix marketing), `2a276b5a` (docs fix) — bypasan el proceso de review.
- No hay plantilla de issue/PR en `.github/ISSUE_TEMPLATE/` ni `PULL_REQUEST_TEMPLATE.md`.

### Recomendaciones

1. **Crear `.github/PULL_REQUEST_TEMPLATE.md`** con secciones: Problema, Solución, Tests, Screenshot.
2. **ADR mínimo:** para cada decisión arquitectónica, agregar un entry en `docs/decisions/YYYY-MM-DD-titulo.md` (formato ligero, no burocrático).
3. **Política de cero commits directos a main** — documentar en CLAUDE.md y enforcer con branch protection (ver Pilar 3).

---

## Pilar 2 — Documentación

**Riesgo: 🟢 Bajo**

### Hallazgos

**Positivos:**
- Stack de CLAUDE.md en 4 niveles: global → repo → `.claude/` → subdirectorios. Cubre invariantes globales, patrones anti-pattern, convenciones de commit.
- `CONCEPTS.md` documenta vocabulario del dominio (raro y valioso).
- `docs/architecture.md`, `docs/embedding-strategy.md`, `docs/data-sources.md`, `docs/prompts.md` actualizados.
- `docs/deployment.md` incluye runbook con tabla de variables de entorno y comandos.
- Docs se sincronizan en el mismo PR que el código (evidencia: commit `897a9ee3 docs(sync)`).
- Fix de referencia Fernet→AES-256-GCM realizado en `2a276b5a` — indicador de que la doc se mantiene.

**Gaps:**
- `docs/deployment.md` menciona Cloudflare Tunnel token de prueba `1x0000000000000000000000000000000AA` en la tabla de vars — podría confundir en un setup real de staging.
- No hay un `CHANGELOG.md` o release notes automatizados.
- `docs/testing.md` existe pero no se auditó su contenido para verificar si documenta la estrategia de mocking actual (MSW pendiente según KNOWN_ISSUES.md).

### Recomendaciones

1. Agregar sección "Known Limitations" en `docs/deployment.md` para el Turnstile test key.
2. Considerar `git-cliff` o `conventional-changelog` para auto-generar CHANGELOG desde conventional commits.

---

## Pilar 3 — Version Control

**Riesgo: 🟡 Medio**

### Hallazgos

**Positivos:**
- Conventional commits aplicados consistentemente: `feat`, `fix`, `chore`, `docs`, `perf`, `refactor`, `test` con scope.
- Modelo de ramas `feature/* → main` via PR evidenciado en PRs #27–#35.
- PRs usados para features no triviales con review (PR #33 tiene 4 commits de fix post-review).

**Gaps:**
- **3 commits directos a `main` recientes**: `a4c1ed4b`, `0106087e`, `2a276b5a`. Sin review, sin CI gate.
- **Sin rama `develop`**: modelo es `feature → main` directamente. Para un solo dev está bien, pero escala mal.
- **Ramas locales stale sin mergear ni eliminar**: `feat/alternatives-desktop-final`, `framework-merge-to-main`, `pr1-biomarker-rules-hardening`, `worktree-fix+scan-pipeline-cache-optimistic`. Evidencian trabajo incompleto o abandonado.
- **Sin branch protection en GitHub**: no hay evidencia de `Require PR reviews`, `Require status checks to pass`, ni `Require linear history` configurados en GitHub.

### Recomendaciones

1. **Activar branch protection en `main`** en GitHub Settings → Branches:
   - ✅ Require pull request before merging
   - ✅ Require status checks: `ci / test-backend`, `ci / lint`
   - ✅ Do not allow bypassing
2. **Limpiar ramas stale**: `git branch -d` las ramas locales sin actividad > 30 días.
3. **Agregar a CLAUDE.md**: "Nunca push directo a main — siempre PR, aunque sea un fix de una línea."

---

## Pilar 4 — Testing

**Riesgo: 🟡 Medio**

### Hallazgos

**Positivos:**
- **40+ archivos de tests backend** (pytest): crypto, embeddings, enrichment, phi_isolation, ci_gate, token_budget, security_headers, jwt_migration, schemas_hardening, logging_redaction.
- **E2E Playwright**: auth (login, register, session), scan (barcode, photo, result, reopen, SSE contract), biosync, dashboard, history, alternatives, landing, legal.
- Tests de integración separados en `tests/specs-integration/smoke/`.
- `test_ci_gate.py` verifica que los endpoints LLM tengan `token_budget` — pattern de CI gate para invariantes arquitectónicos.
- `test_phi_isolation.py` verifica que datos médicos no aparezcan en logs.
- Visual regression tests para landing.

**Gaps:**
- **1 test E2E fallando**: `dashboard.spec.ts` "happy path" — timing issue con mock overrides de TanStack Query. Documentado en KNOWN_ISSUES.md pero sin fecha de resolución.
- **Sin coverage threshold configurado**: `pytest.ini` solo tiene `testpaths = tests` y `asyncio_mode = auto`. No hay `--cov-fail-under`.
- **Sin cobertura reportada en CI**: el archivo `backend/.coverage` es binario; no hay paso de CI que publique el reporte HTML ni falle por coverage bajo.
- **Sin tests de carga/performance**: endpoints de streaming SSE y LangGraph no tienen pruebas de concurrencia o latencia bajo carga.
- **E2E de dashboard**: KNOWN_ISSUES.md documenta que la solución correcta es MSW pero no tiene ticket/fecha.

### Recomendaciones

1. **Agregar coverage threshold**: en `pytest.ini`:
   ```ini
   addopts = --cov=app --cov-report=term-missing --cov-fail-under=70
   ```
2. **Publicar HTML coverage en CI**: agregar step en `ci.yml` que suba artefacto de cobertura.
3. **Resolver dashboard test**: crear issue en GitHub y agregar fecha en KNOWN_ISSUES.md. La solución MSW es la correcta (eliminación de timing race con Playwright routes).
4. **Smoke test de carga mínimo**: agregar en `playwright-integration.yml` un test de `/health` bajo 10 requests concurrentes con `autocannon` o `k6`.

---

## Pilar 5 — AuthN vs AuthZ

**Riesgo: 🟡 Medio**

### Hallazgos

**Positivos (AuthN):**
- JWT middleware en `backend/app/middleware/auth.py` con `get_current_user` dependency.
- Refresh tokens implementados (migración `1906e8b727d2_add_refresh_tokens_table.py`).
- Access token expira en 30 min, refresh en 7 días.
- Endpoints públicos explícitamente separados: `public_router` en `scan.py`, `waitlist.router` sin JWT.
- `reject_dev_secrets_in_production` en `config.py` — startup falla si `JWT_SECRET` es el valor dev.
- `test_jwt_migration.py` verifica el proceso de rotación.

**Positivos (AuthZ):**
- Todos los endpoints protegidos filtran por `user_id = current_user.id` en queries SQL.
- Share token: `create_share_link` verifica `ScanHistory.user_id == current_user.id` antes de emitir token.
- Biomarkers: `upload_biomarkers` y `biomarker_status` filtran por `current_user.id`.
- Share revocation también verifica ownership.

**Gaps críticos:**
- **`/scan/alternatives/{barcode}` sin check de ownership**: el endpoint acepta cualquier `barcode` y busca en la DB sin verificar que el usuario haya escaneado ese producto. No es un IDOR clásico (no expone datos del usuario), pero permite enumerar si un producto existe en el sistema y obtener su análisis sin haberlo escaneado.
- **Sin Row Level Security (RLS)**: la ownership se enforce solo en la capa de aplicación. Si hay un bug de SQL injection o un segundo microservicio, los datos cruzados son posibles. Para datos médicos esto es riesgo real.
- **JWT HS256**: algoritmo simétrico — si `JWT_SECRET` se filtra, el atacante puede forjar tokens. Considerar RS256 (asimétrico) para futuro.
- **Sin MFA**: la app maneja datos de salud. MFA debería ser obligatorio o al menos disponible.

### Recomendaciones

1. **Urgente — Fix alternatives authZ**: agregar check en `GET /scan/alternatives/{barcode}`:
   ```python
   scan = db.scalar(select(ScanHistory).where(
       ScanHistory.product_barcode == barcode,
       ScanHistory.user_id == current_user.id
   ))
   if not scan:
       raise HTTPException(status_code=404)
   ```
2. **Medium term — RLS en PostgreSQL prod**: agregar políticas de RLS en `scan_history`, `biomarkers` filtradas por `user_id` correspondiente al claim del JWT.
3. **Backlog — RS256**: migrar JWT a RS256 para separar signing key de verification key.

---

## Pilar 6 — Error Handling

**Riesgo: 🟡 Medio**

### Hallazgos

**Positivos:**
- `@app.exception_handler(Exception)` global retorna JSON consistente `{"error": "internal_error", "message": "..."}` con `X-Request-ID`.
- Rate limit (429) manejado con `rate_limit_exceeded_handler`.
- Background tasks tienen `try/except` con `logger.error` — no crashean el proceso principal.
- Schema de errores tipado en `backend/app/schemas/errors.py`.
- `test_error_schema.py` verifica la consistencia del schema.

**Gaps:**
- **Sin `RequestValidationError` handler custom**: FastAPI por defecto retorna 422 con el path del campo inválido en el body (`loc`, `msg`, `type`). Esto puede exponer la estructura interna de los schemas Pydantic a atacantes que sondan la API.
- **Sin timeout en llamadas a Gemini API**: si la API de Google no responde, el request de `/scan/barcode` o `/scan/photo` cuelga indefinidamente. No se encontró `httpx.AsyncClient(timeout=...)` ni `asyncio.wait_for(...)` en los servicios.
- **Sin retry con backoff en LLM calls**: una falla transitoria de Gemini mata el scan completo sin reintentar.
- **ChromaDB sin circuit breaker**: si ChromaDB falla, la búsqueda semántica falla silenciosamente o propaga excepción. No hay fallback a búsqueda textual (BM25) documentado como failsafe en código.
- **Background tasks sin dead letter queue**: errores en `_run_enrichment_task` o `_run_off_lookup_task` se loggean pero se pierden. No hay forma de reintentar.

### Recomendaciones

1. **Handler 422 custom en `main.py`**:
   ```python
   from fastapi.exceptions import RequestValidationError
   @app.exception_handler(RequestValidationError)
   async def validation_handler(request, exc):
       return JSONResponse(status_code=422,
           content={"error": "validation_error", "message": "Invalid request"})
   ```
2. **Timeout en Gemini**: agregar `timeout=30` en el `httpx.AsyncClient` o `genai.Client` de `services/analysis.py`.
3. **Retry con tenacity**: `@retry(stop=stop_after_attempt(3), wait=wait_exponential())` en llamadas a Gemini.
4. **Fallback ChromaDB → BM25**: documentar y testear el fallback path explícitamente.

---

## Pilar 7 — Bases de Datos

**Riesgo: 🟡 Medio**

### Hallazgos

**Positivos:**
- Alembic con 13 migraciones versionadas — historia completa de schema desde initial.
- `alembic upgrade head` corre ANTES de `uvicorn` en el entrypoint del container (correcto).
- Índices en `scan_history`: `idx_scan_history_user` (user_id), `idx_scan_history_barcode` (product_barcode).
- Índices en `regulatory_status`: ingredient, source.
- Índices en `biomarkers`: user_id, expires_at (inferido de la migración de índices).
- `ON DELETE CASCADE` en FK `scan_history.user_id → users.id`.
- Check constraint: `confidence_score >= 0.0 AND confidence_score <= 1.0`.
- PostgreSQL en prod con health checks; SQLite solo en dev.

**Gaps:**
- **Falta índice compuesto `(user_id, scanned_at DESC)` en `scan_history`**: la query de historia paginada haría full scan de `idx_scan_history_user` y luego sort. Con miles de scans por usuario, esto degrada.
- **`result_json` es un blob JSON sin índice**: queries de analytics en `aabbc492fe8d` que filtren por campos internos del JSON (semaphore_result, clean_score) no pueden usar índices — full table scan garantizado.
- **dev docker-compose.yml tiene credenciales hardcodeadas**: `POSTGRES_USER: bioshield`, `POSTGRES_PASSWORD: bioshield`, `DATABASE_URL: postgresql://bioshield:bioshield@...`. Aunque es dev, entrena malos hábitos y puede filtrarse.
- **Sin backup pre-deploy**: el runbook de `docs/deployment.md` no incluye `pg_dump` antes de `make up`. Una migración fallida en prod no tiene rollback de datos.
- **Sin migration squash**: 13 migraciones incrementales en prod pueden tardar en aplicarse desde cero. Para un nuevo deploy, todas corren secuencialmente.

### Recomendaciones

1. **Índice compuesto urgente** — nueva migración Alembic:
   ```python
   op.create_index('idx_scan_history_user_date',
       'scan_history', ['user_id', 'scanned_at'], postgresql_ops={'scanned_at': 'DESC'})
   ```
2. **Backup pre-deploy en runbook**:
   ```bash
   docker compose -f docker-compose.prod.yml exec postgres \
     pg_dump -U $POSTGRES_USER bioshield > backup-$(date +%Y%m%d-%H%M).sql
   ```
3. **Mover credenciales dev a `.env.dev`** y referenciarlas en `docker-compose.yml` con `${VAR}`.

---

## Pilar 8 — Seguridad

**Riesgo: 🟡 Medio**

### Hallazgos

**Positivos:**
- Headers de seguridad en `main.py`: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, HSTS (solo en prod).
- AES-256-GCM para datos de biomarcadores — never plaintext en DB.
- `reject_dev_secrets_in_production` bloquea startup con secrets de dev.
- Docs UI (`/docs`, `/redoc`) deshabilitados en producción.
- Rate limiting con slowapi en endpoints críticos.
- `test_security_headers.py` verifica headers.
- `test_logging_redaction.py` verifica que tokens/passwords no aparezcan en logs.
- `test_phi_isolation.py` verifica aislamiento de datos médicos.
- Audit de seguridad previo (15/16 findings resueltos — commit `ee5cae18`).

**Gaps:**
- **Sin Content-Security-Policy en el backend**: el middleware solo agrega los 4 headers básicos. Falta CSP, `Permissions-Policy`, `Cross-Origin-Opener-Policy`.
- **Foto upload sin límite de tamaño**: `POST /scan/photo` lee `await file.read()` sin verificar `content_length`. Un archivo de 1GB puede saturar la memoria del contenedor.
- **`assert` en código de producción** (`scan.py`: `assert scan.share_expires_at is not None`): Python con `-O` deshabilita asserts. Si el assert es una guarda de seguridad real, usar `if not ...: raise`.
- **1 finding de security audit de 2026-05-30 sin resolver** (commit menciona "15/16 findings"). El finding #16 no está documentado como cerrado.
- **JWT HS256 simétrico**: secret único compartido — riesgo si hay leak.
- **Cloudflare Turnstile default `"dev"`** en `config.py`: si `TURNSTILE_SECRET_KEY` no se configura en prod, el anti-bot está desactivado.
- **`off_contributor_password` en `Settings`**: aunque vacío por defecto, si se configura una cuenta real de Open Food Facts, la password viaja en el env var.

### Recomendaciones

1. **Urgente — límite de tamaño en foto upload**:
   ```python
   MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
   if file.size and file.size > MAX_UPLOAD_SIZE:
       raise HTTPException(413, "File too large")
   image_bytes = await file.read()
   if len(image_bytes) > MAX_UPLOAD_SIZE:
       raise HTTPException(413, "File too large")
   ```
2. **Reemplazar `assert` con `if/raise`** en código de producción.
3. **Agregar CSP header** en el middleware de seguridad.
4. **Documentar el finding #16** del audit anterior — ya sea como aceptado, mitigado, o crear issue para tracking.
5. **Validar en startup** que `TURNSTILE_SECRET_KEY != "dev"` en producción (igual que se hace con `JWT_SECRET`).

---

## Pilar 9 — Hosting

**Riesgo: 🔴 Alto**

### Hallazgos

**Positivos:**
- Oracle Cloud Always Free (ARM64 VM) — cero costo para el stage actual, válido para MVP.
- Cloudflare Tunnel elimina exposición de IP pública — excelente decisión de seguridad.
- nginx como reverse proxy en prod (docker-compose.prod.yml).
- PostgreSQL con volumen persistente y health checks.
- Containers con `restart: unless-stopped` — auto-recovery de crashes.
- Separación correcta entre `docker-compose.yml` (dev) y `docker-compose.prod.yml` (prod).

**Gaps críticos:**
- **SPOF total**: un solo VM en Oracle Cloud. Si el VM muere (hardware failure, OCI maintenance), la app muere. Sin failover, sin replica.
- **Sin staging/preview environment**: no hay entorno intermedio entre dev local y producción. Los cambios van directo a prod sin validación en un entorno equivalente.
- **No hay CDN para assets**: el frontend se sirve a través del Cloudflare Tunnel → nginx → Next.js. Los assets estáticos no están en un CDN (Cloudflare Pages o similar) que ofrezca edge caching.
- **ChromaDB en volumen local del VM**: si el VM se pierde, el vector store también. No hay backup automatizado de `data/chroma_db`.
- **Sin auto-scaling**: si la carga sube (marketing viral), el single VM es el techo.
- **dev docker-compose.yml expone puertos 8000 y 3000 directamente** sin nginx — si se corre accidentalmente en un servidor con IP pública, quedan expuestos.

### Recomendaciones

1. **Backup de ChromaDB**: agregar cron en `expire-biomarkers.yml` o nuevo workflow que haga tar + upload a un bucket (Oracle Object Storage free tier) daily.
2. **Preview environments**: usar **Railway** o **Render** para PRs — ambos tienen free tier con deploy-on-PR que conecta con GitHub.
3. **Separar frontend**: migrar Next.js a **Cloudflare Pages** (free, CDN global, deploy-on-push). Solo el backend quedaría en el VM de Oracle.
4. **Documentar el RTO/RPO**: aunque es MVP, definir "si el VM muere, ¿cuánto tardamos en recovery?" — ayuda a saber si el nivel de riesgo es aceptable o no.

---

## Pilar 10 — Despliegue (CI/CD)

**Riesgo: 🔴 Alto**

### Hallazgos

**Positivos:**
- `ci.yml` con GitHub Actions — lint (Ruff), type check, tests backend.
- `docker-build.yml` — verifica que las imágenes construyen correctamente.
- `playwright-integration.yml` — E2E tests en CI.
- `lhci.yml` — Lighthouse CI para performance.
- `expire-biomarkers.yml` — cron job para expiración de datos.
- `alembic upgrade head` corre ANTES de `uvicorn` en el entrypoint — orden correcto.
- `depends_on: postgres: condition: service_healthy` — el backend espera a que la DB esté lista.

**Gaps críticos:**
- **Deploy es 100% manual**: `git pull origin main && make up` en el VM. No hay paso de CD en GitHub Actions que triggeree el deploy automáticamente.
- **Sin staging antes de prod**: los cambios se validan en CI (tests) pero no en un entorno real antes de llegar a producción.
- **Sin rollback automatizado**: si `alembic upgrade head` falla mid-deploy, el container no levanta pero los datos del paso anterior de Alembic pueden estar en estado inconsistente. No hay `alembic downgrade -1` en el runbook de emergencia.
- **Sin smoke test post-deploy**: después de `make up`, nadie verifica automáticamente que `/health` responde 200 antes de marcar el deploy como exitoso.
- **playwright-integration.yml no está confirmado como blocking gate**: no hay evidencia de que este workflow bloquee el merge de PRs (requeriría branch protection, que no está configurada — ver Pilar 3).
- **Sin notificación de deploy**: sin Slack/email cuando un deploy termina o falla.

### Recomendaciones

1. **Smoke test post-deploy** — agregar al final del `command` en docker-compose.prod.yml:
   ```yaml
   command: >
     sh -c "alembic upgrade head &&
            uvicorn app.main:app --host 0.0.0.0 --port 8000 &
            sleep 10 && curl -f http://localhost:8000/health || exit 1 &&
            wait"
   ```
   (o un health check script separado en el runbook)
2. **Rollback de emergencia** — agregar sección en `docs/deployment.md`:
   ```bash
   # Si el deploy falla:
   git revert HEAD && git push  # o git checkout <prev-commit>
   cd /opt/bioshield && git pull && make up
   # Si la migración se corrompió:
   docker compose exec backend alembic downgrade -1
   ```
3. **CD via SSH Action** — para automatizar deploy sin servidor de CD:
   ```yaml
   # En ci.yml, job deploy (solo en push a main):
   - uses: appleboy/ssh-action@v1
     with:
       host: ${{ secrets.ORACLE_VM_IP }}
       key: ${{ secrets.SSH_PRIVATE_KEY }}
       script: cd /opt/bioshield && git pull && make up
   ```
4. **Branch protection + required checks** (ver Pilar 3) para que `playwright-integration` bloquee merges.

---

## Pilar 11 — Observabilidad

**Riesgo: 🔴 Alto**

### Hallazgos

**Positivos:**
- **Structured JSON logging**: `JsonFormatter` emite un JSON por línea con `ts`, `level`, `logger`, `msg`, `request_id`. Excelente base.
- **Request ID propagation**: `RequestIDMiddleware` genera UUID por request, propagado via `REQUEST_ID_VAR` (contextvars) — correlación de logs correcta.
- **Sensitive field redaction**: `_should_redact()` redacta sufijos `_key`, `_password`, `_secret`, `_token`.
- **LangGraph node timing**: `timed_node` wrapper registra latencia por nodo del grafo — visibilidad del pipeline de IA.
- **Health endpoint** `/health` verifica conectividad con la DB.
- **Token budget tracking**: `tokens_used_today` por usuario — proxy de costo de LLM.

**Gaps críticos:**
- **Sin aggregación de logs**: los logs van a stdout del container. En Oracle Cloud VM con Docker, stdout → journal del daemon. Sin `docker logs` manual o acceso SSH, no hay forma de ver logs en tiempo real. No hay Loki, Papertrail, Datadog Logs, ni siquiera un `docker logs` forwarding a S3.
- **Sin métricas de error rate**: no hay Prometheus, no hay contadores de HTTP 4xx/5xx, no hay dashboard. La única forma de saber si hay errores es leer los logs manualmente.
- **Sin alertas**: ningún mecanismo notifica si la tasa de errores sube, si el backend está caído, o si el token budget de un usuario se agota de forma anómala.
- **Sin distributed tracing**: OpenTelemetry no está presente. No hay trace_id correlacionado entre el frontend, el backend, y los nodos de LangGraph.
- **Sin APM**: no hay tracking de latencia de endpoints por percentil (P50, P95, P99). El `timed_node` existe pero sus datos solo están en logs, no en una métrica consultable.
- **Logs sin rotación documentada**: stdout en Docker → el journal del VM puede crecer sin límite si no hay `logrotate` o `docker --log-opt max-size`.

### Recomendaciones (por prioridad)

1. **Inmediato — Agregación de logs (gratis)**:
   Usar **Grafana Cloud free tier** (50GB/mes) con Promtail para shipmear logs:
   ```yaml
   # En docker-compose.prod.yml, agregar servicio:
   promtail:
     image: grafana/promtail:latest
     volumes:
       - /var/run/docker.sock:/var/run/docker.sock
       - ./promtail-config.yml:/etc/promtail/config.yml
   ```

2. **Inmediato — Log rotation**:
   En `docker-compose.prod.yml`, para cada servicio:
   ```yaml
   logging:
     driver: "json-file"
     options:
       max-size: "50m"
       max-file: "5"
   ```

3. **Corto plazo — Error rate básica**:
   Agregar middleware que incremente contador de errores por status code. Exportar a Prometheus (o usar `prometheus-fastapi-instrumentator`):
   ```python
   from prometheus_fastapi_instrumentator import Instrumentator
   Instrumentator().instrument(app).expose(app, endpoint="/metrics")
   ```

4. **Corto plazo — Alerta de health**:
   UptimeRobot free tier: monitorea `https://[tunnel]/health` cada 5 min y envía email si está caído.

5. **Medio plazo — OpenTelemetry**:
   Agregar `opentelemetry-sdk` + `opentelemetry-instrumentation-fastapi` para trazas correlacionadas entre requests y nodos de LangGraph.

---

## Roadmap priorizado

### Sprint 1 — Urgente (esta semana)
| # | Tarea | Pilar | Impacto |
|---|-------|-------|---------|
| 1 | Activar log rotation en docker-compose.prod.yml | 11 | Evita VM lleno |
| 2 | Agregar log forwarding a Grafana Cloud | 11 | Visibilidad inmediata |
| 3 | Agregar UptimeRobot en `/health` | 11 | Alerta de downtime |
| 4 | Fix authZ en `/scan/alternatives/{barcode}` | 5 | Seguridad de datos |
| 5 | Límite de tamaño en upload de fotos | 8 | DoS mitigation |
| 6 | Backup de ChromaDB al Object Storage | 9 | Durabilidad de datos |

### Sprint 2 — Corto plazo (este mes)
| # | Tarea | Pilar |
|---|-------|-------|
| 7 | Branch protection en main + required CI checks | 3 |
| 8 | Handler 422 custom + timeout en Gemini calls | 6 |
| 9 | Índice compuesto `(user_id, scanned_at)` en scan_history | 7 |
| 10 | Backup pre-deploy en runbook | 7 |
| 11 | Prometheus metrics + dashboard básico | 11 |
| 12 | Smoke test post-deploy automatizado | 10 |

### Sprint 3 — Medio plazo (próximo trimestre)
| # | Tarea | Pilar |
|---|-------|-------|
| 13 | Preview environments (Railway o Render) | 9 |
| 14 | Separar frontend a Cloudflare Pages | 9 |
| 15 | CD automatizado via SSH Action | 10 |
| 16 | OpenTelemetry distributed tracing | 11 |
| 17 | RLS en PostgreSQL para datos médicos | 5 |
| 18 | Coverage threshold en CI (≥70%) | 4 |
| 19 | Resolver dashboard E2E test (MSW) | 4 |

---

## Fortalezas del proyecto (no obvias)

Antes de cerrar, merece reconocimiento lo que este proyecto hace **mejor que el promedio**:

1. **Token budget guard con CI gate** (`test_ci_gate.py`) — patrón inusualmente maduro que previene que un endpoint LLM sin guard pase a producción.
2. **PHI isolation testing** — pocos proyectos testean explícitamente que datos médicos no se filtran en logs.
3. **Structured logging con redacción automática** — la mayoría de proyectos usan `print()` o `logger.info(f"token={token}")`.
4. **`reject_dev_secrets_in_production`** — el servidor falla rápido y explícitamente si se despliega con secrets de dev.
5. **Atomic SQL UPDATE para token budget** — evita el race condition de read-modify-write que afecta a casi todo rate limiter naive.
6. **CONCEPTS.md** — raro y valioso en proyectos de dominio médico/nutricional.

---

*Generado en: 2026-06-26 | Revisado contra: commit `a4c1ed4b` (HEAD de main)*
