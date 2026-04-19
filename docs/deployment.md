# BioShield AI — Deployment Runbook

**Stack:** FastAPI · PostgreSQL · ChromaDB (persistent volume) · Docker  
**Última actualización:** 2026-04-19

---

## 1. Prerequisitos

| Herramienta | Versión mínima |
|---|---|
| Docker + Docker Compose | 24.x |
| Python | 3.11+ (solo para scripts locales) |
| Git | cualquiera |

Variables de entorno requeridas (ver `.env.example`):

| Variable | Descripción |
|---|---|
| `GEMINI_API_KEY` | API key de Google AI Studio |
| `JWT_SECRET` | String aleatorio ≥ 32 chars (`openssl rand -hex 32`) |
| `AES_KEY` | Exactamente 32 bytes ASCII para cifrado de biomarcadores |
| `DATABASE_URL` | `postgresql://user:pass@host:5432/bioshield` en producción |

---

## 2. Deploy local (docker-compose)

```bash
# 1. Clonar y configurar env
git clone <repo>
cd bio_shield
cp backend/.env.example backend/.env
# Editar backend/.env con valores reales

# 2. Levantar stack (build + migraciones + servidor)
docker compose up --build

# El backend corre alembic upgrade head automáticamente antes de arrancar.
# Accesible en http://localhost:8000
# Docs OpenAPI en http://localhost:8000/docs

# 3. (Opcional) Sembrar RAG con datos curados
docker compose exec backend python -m scripts.seed_rag

# 4. Detener preservando datos
docker compose down

# 5. Reset completo (borra volúmenes postgres + chroma)
docker compose down -v
```

---

## 3. Deploy en producción (Render)

### 3.1 Web Service (backend)

1. Crear **Web Service** apuntando al repo, **Root Directory:** `backend`.
2. **Build Command:** `pip install -r requirements.txt`
3. **Start Command:** `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Configurar las variables de entorno del §1 en el panel de Render.
5. `DATABASE_URL` debe apuntar a la Postgres instance de Render (interna).

### 3.2 Postgres (Render)

1. Crear **PostgreSQL** instance en Render.
2. Copiar la **Internal Database URL** y pegarla como `DATABASE_URL` en el Web Service.

### 3.3 Persistent Disk (ChromaDB)

1. Adjuntar un **Persistent Disk** al Web Service (mínimo 1 GB).
2. **Mount Path:** `/data`
3. Confirmar que `CHROMA_PERSIST_DIRECTORY=/data/chroma_db` está configurado.

### 3.4 Cron Job (expiración de biomarcadores)

El workflow `.github/workflows/expire-biomarkers.yml` corre diariamente a las 02:00 UTC.  
Requiere que los siguientes **GitHub Secrets** estén configurados en el repositorio:

| Secret | Valor |
|---|---|
| `DATABASE_URL` | URL de producción |
| `AES_KEY` | Igual que el del Web Service |
| `JWT_SECRET` | Igual que el del Web Service |
| `GEMINI_API_KEY` | API key de Gemini |

Configurar en: **GitHub → Settings → Secrets and variables → Actions → New repository secret**

---

## 4. Rotación de AES_KEY

> **Crítico:** AES_KEY cifra todos los biomarcadores. Una rotación incorrecta deja datos irrecuperables.

### Cuándo rotar

- Sospecha de compromiso del host o del archivo `.env`.
- Política interna de rotación periódica.
- Migración a KMS (ver §5).

### Procedimiento de rotación (re-encrypt in place)

```bash
# 1. Poner el backend en modo mantenimiento (detener tráfico)
#    En Render: suspender el Web Service.

# 2. Hacer backup de la base de datos ANTES de cualquier cambio
pg_dump $DATABASE_URL > backup_pre_rotation_$(date +%Y%m%d).sql

# 3. Ejecutar script de re-encriptación
#    (requiere OLD_AES_KEY y NEW_AES_KEY en el entorno)
OLD_AES_KEY="<clave_actual>" \
NEW_AES_KEY="$(openssl rand -hex 16 | cut -c1-32)" \
python -m scripts.rotate_aes_key   # ver §4.1

# 4. Actualizar AES_KEY en .env / Render / GitHub Secrets con NEW_AES_KEY

# 5. Reanudar el Web Service y verificar que /biosync/status responde 200

# 6. Guardar el backup en almacenamiento seguro (S3 / GCS)
```

### 4.1 Script `scripts/rotate_aes_key.py` (pendiente de implementar)

Este script no existe aún. Cuando se implemente debe:
1. Leer todos los rows `biomarkers` donde `data IS NOT NULL`.
2. Desencriptar cada row con `OLD_AES_KEY`.
3. Re-encriptar con `NEW_AES_KEY` usando `encrypt_biomarker()`.
4. Hacer upsert de cada row en una transacción única.
5. Emitir count de rows procesados y hash SHA-256 del nuevo key para trazabilidad.

> Hasta que este script exista, la única opción de rotación es eliminar todos los biomarcadores (`DELETE FROM biomarkers`) y pedir a los usuarios que re-suban sus datos.

---

## 5. Upgrade path: AES_KEY en KMS (producción con PII real)

La implementación actual carga `AES_KEY` desde `.env` (`app/config.py`). Para producción con datos médicos reales, migrar a:

- **AWS:** `boto3` + `secretsmanager.get_secret_value` — reemplazar `settings.aes_key` por una llamada al SDK.
- **GCP:** `google-cloud-secret-manager` + `SecretManagerServiceClient.access_secret_version`.

La API pública (`encrypt_biomarker` / `decrypt_biomarker` en `services/crypto.py`) no cambia — solo el origen del key.

---

## 6. Rollback de migraciones

```bash
# Ver historial de migraciones aplicadas
alembic history --verbose

# Revertir una migración (target = revision anterior)
alembic downgrade <revision_id>

# Revertir todas las migraciones
alembic downgrade base
```

---

## 7. Health check

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

El Dockerfile tiene `HEALTHCHECK` configurado contra este endpoint. En Render, usarlo como Health Check Path.
