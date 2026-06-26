# BioShield AI — Deployment Runbook

**Stack:** FastAPI · PostgreSQL · ChromaDB · Next.js · Docker  
**Última actualización:** 2026-06-26

---

## Índice

- [Producción: Oracle Cloud Always Free + Cloudflare Tunnel](#1-producción-oracle-cloud-always-free--cloudflare-tunnel)
- [Deploy local (docker-compose dev)](#2-deploy-local-docker-compose-dev)
- [Variables de entorno](#3-variables-de-entorno)
- [Cómo hacer updates en producción](#4-cómo-hacer-updates-en-producción)
- [Troubleshooting](#5-troubleshooting)
- [Demo credentials](#6-demo-credentials)
- [Backup y restore](#7-backup-y-restore)
- [Rotación de AES_KEY](#8-rotación-de-aes_key)
- [Rollback de migraciones](#9-rollback-de-migraciones)

---

## 1. Producción: Oracle Cloud Always Free + Cloudflare Tunnel

### Arquitectura

```
Browser (recruiter / usuario)
    │
    │ HTTPS — certificado válido de Cloudflare
    ▼
Cloudflare Edge
    │
    │ Túnel encriptado (outbound TCP 443 desde el VM)
    │ No requiere puertos 80/443 abiertos en Oracle
    ▼
cloudflared (container)
    │
    ▼
Nginx (container) :8080
    ├── /api/*  ──▶  FastAPI backend :8000
    └── /*      ──▶  Next.js frontend :3000
                          │
                     PostgreSQL :5432
                     ChromaDB (volumen persistente)
```

**Costo:** $0/mes (Oracle Always Free ARM A1: 4 OCPU, 24GB RAM, 200GB disco)  
**URL resultado:** `https://UUID.cfargotunnel.com`

---

### Prerequisitos

| Herramienta | Dónde obtenerla | Costo |
|-------------|-----------------|-------|
| Cuenta Oracle Cloud | cloud.oracle.com → "Start for free" | $0 (requiere tarjeta débito para verificación $1 reversible) |
| Cuenta Cloudflare | cloudflare.com | $0, sin tarjeta |
| `GEMINI_API_KEY` | aistudio.google.com | $0 en tier gratuito |
| SSH key pair | `ssh-keygen -t ed25519 -C "bioshield-prod"` | — |

---

### Slice 1 — Crear VM en Oracle Cloud

1. Ir a `cloud.oracle.com` → **"Start for free"**
2. Signup: nombre, email, país, tarjeta débito ($1 autorización reversible en 3-5 días)
3. **Home Region:** elegir `eu-frankfurt-1` o `us-ashburn-1`
   > ⚠️ La Home Region **no se puede cambiar** después del signup. Afecta la latencia y disponibilidad de ARM.

4. Una vez activa la cuenta: **Compute → Instances → Create Instance**

   | Campo | Valor |
   |-------|-------|
   | Name | `bioshield-prod` |
   | Image | Ubuntu 22.04 (Canonical) |
   | Shape | `VM.Standard.A1.Flex` |
   | OCPUs | 4 |
   | RAM | 24 GB |
   | Boot Volume | 200 GB |
   | SSH Key | Pegar contenido de `~/.ssh/id_ed25519.pub` |

5. Crear la instancia. Si aparece **"Out of host capacity"**:
   ```bash
   # Script de polling automático — reintenta cada 60s hasta éxito
   git clone https://github.com/hitrov/oci-arm-host-capacity
   cd oci-arm-host-capacity
   cp .env.example .env
   # Editar .env con tus credenciales OCI (ver README del script)
   python3 oci-arm-host-capacity.py
   # Típico: éxito en 24-72h
   ```

6. Una vez creado: anotar la **IP pública** del VM
7. En Oracle: **VCN → Security Lists → Default Security List → Ingress Rules**:
   - Agregar: TCP 22 (SSH)
   - TCP 80/443 **no son necesarios** con Cloudflare Tunnel

---

### Slice 2 — Configurar Cloudflare Tunnel

1. Crear cuenta gratuita en `cloudflare.com` (sin tarjeta)
2. Ir a **Zero Trust → Networks → Tunnels → Create a tunnel**
3. Tipo: **Cloudflared** → nombre: `bioshield-prod`
4. Copiar el **Tunnel Token** que genera Cloudflare
5. En la configuración del tunnel, agregar una ruta pública:
   - **Subdomain:** dejar vacío (usa el UUID generado)
   - **Service:** `http://nginx:8080`
   - Cloudflare genera la URL: `https://UUID.cfargotunnel.com`
6. Guardar la URL para usarla en el siguiente slice:
   ```bash
   echo "https://UUID.cfargotunnel.com" > .tunnel_url
   ```

---

### Slice 3 — Configurar el servidor

```bash
# Conectarse al VM
ssh ubuntu@IP_PUBLICA_ORACLE

# Instalar Docker y make
sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu
sudo apt install docker-compose-plugin make -y
newgrp docker

# Docker arranca automáticamente en reboots
sudo systemctl enable docker

# Clonar el repo
git clone https://github.com/TU_USUARIO/bio_shield.git /opt/bioshield
cd /opt/bioshield

# Configurar variables de entorno
cp .env.prod.example .env.prod
nano .env.prod
```

**Valores a completar en `.env.prod`:**

```bash
# Generar JWT_SECRET:
openssl rand -hex 32

# Generar AES_KEY:
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# POSTGRES_PASSWORD: elegir contraseña fuerte
# GEMINI_API_KEY: tu key de Google AI Studio
# CLOUDFLARE_TUNNEL_TOKEN: del Slice 2
# ALLOWED_ORIGINS, NEXT_PUBLIC_API_URL, FRONTEND_URL: URL del tunnel (https://UUID.cfargotunnel.com)
```

```bash
# Crear directorios de datos persistentes
mkdir -p data/chroma_db data/backups
```

---

### Slice 4 — Deploy

```bash
cd /opt/bioshield

# Build + levantar todos los servicios
make up

# Esperar ~3-5 min para que PostgreSQL inicialice y el backend pase el healthcheck
# Verificar estado:
make status

# Ver logs si algo falla:
make logs

# Poblar ChromaDB con aditivos de Open Food Facts + crear usuario demo
# (ejecutar UNA sola vez después del primer deploy)
make seed
```

**Verificaciones:**
```bash
# Backend healthy (desde el VM):
curl http://localhost:8080/api/health

# Tunnel funcionando (desde tu laptop, reemplazar con la URL real):
curl https://UUID.cfargotunnel.com/api/health
# Respuesta esperada: {"status":"ok"}

# Frontend cargando:
curl -I https://UUID.cfargotunnel.com
# Respuesta esperada: HTTP/2 200
```

---

### Slice 5 — Observabilidad

**UptimeRobot (gratis, 50 monitores):**
1. Crear cuenta en `uptimerobot.com`
2. **Add Monitor** → tipo HTTP(S)
3. URL: `https://UUID.cfargotunnel.com/api/health`
4. Intervalo: 5 minutos
5. Alert contact: email

**Backup automático de PostgreSQL (cron en el VM):**
```bash
# Agregar al crontab del VM:
crontab -e

# Línea a agregar (backup diario a las 3am, retención 7 días):
0 3 * * * docker exec bioshield-postgres-1 pg_dump -U bioshield bioshield | gzip > /opt/bioshield/data/backups/db_$(date +\%Y\%m\%d).sql.gz && find /opt/bioshield/data/backups -name "*.gz" -mtime +7 -delete
```

---

## 2. Deploy local (docker-compose dev)

```bash
# Clonar y configurar
git clone <repo>
cd bio_shield
cp backend/.env.example backend/.env
# Editar backend/.env con valores reales (al menos GEMINI_API_KEY)

# Levantar stack completo
docker compose up --build
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
# OpenAPI: http://localhost:8000/docs

# Sembrar ChromaDB con datos de prueba (8 ingredientes de Nutella)
docker compose exec backend python -m scripts.seed_rag

# Detener preservando datos
docker compose down

# Reset completo (borra volúmenes postgres + chroma)
docker compose down -v
```

---

## 3. Variables de entorno

| Variable | Propósito | Cómo generarla |
|----------|-----------|----------------|
| `POSTGRES_USER` | Usuario de PostgreSQL | `bioshield` (fijo) |
| `POSTGRES_PASSWORD` | Password de PostgreSQL | Contraseña fuerte aleatoria |
| `DATABASE_URL` | DSN de conexión a PostgreSQL | `postgresql+asyncpg://USER:PASS@postgres:5432/bioshield` |
| `JWT_SECRET` | Firma de tokens JWT (≥32 chars) | `openssl rand -hex 32` |
| `AES_KEY` | Clave Fernet para encriptar biomarcadores | `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `TURNSTILE_SECRET_KEY` | Cloudflare Turnstile (anti-bot) | `1x0000000000000000000000000000000AA` (test key para demo) |
| `GEMINI_API_KEY` | Google Gemini API | aistudio.google.com |
| `GEMINI_MODEL` | Modelo LLM | `gemini-2.5-flash` |
| `GEMINI_EMBEDDING_MODEL` | Modelo de embeddings | `models/gemini-embedding-001` |
| `CHROMA_PERSIST_DIRECTORY` | Ruta de ChromaDB | `/data/chroma_db` |
| `ALLOWED_ORIGINS` | CORS — dominios permitidos | `["https://UUID.cfargotunnel.com"]` |
| `NEXT_PUBLIC_API_URL` | URL del backend para el frontend | `https://UUID.cfargotunnel.com/api` |
| `FRONTEND_URL` | URL base del frontend | `https://UUID.cfargotunnel.com` |
| `CLOUDFLARE_TUNNEL_TOKEN` | Token del tunnel de Cloudflare | Dashboard Cloudflare Zero Trust |

---

## 4. Cómo hacer updates en producción

```bash
# En el VM:
cd /opt/bioshield
git pull origin main
make up  # rebuild + restart de containers con cambios
```

> ⚠️ **Nunca usar `docker compose down -v`** en producción — borra los volúmenes de PostgreSQL y ChromaDB.

Si hay nuevas migraciones de Alembic, el backend las aplica automáticamente en el startup (`alembic upgrade head` en el entrypoint).

---

## 5. Troubleshooting

```bash
# Ver logs de todos los servicios
make logs

# Ver logs de un servicio específico
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f postgres
docker compose -f docker-compose.prod.yml logs -f cloudflared

# Reiniciar un servicio sin bajar todo el stack
docker compose -f docker-compose.prod.yml restart backend

# Entrar al container del backend
docker compose -f docker-compose.prod.yml exec backend bash

# Estado completo (servicios + disco + RAM)
make status

# Health check manual
curl http://localhost:8080/api/health
```

**Errores comunes:**

| Síntoma | Causa probable | Fix |
|---------|----------------|-----|
| Backend en `starting` por más de 5 min | PostgreSQL aún inicializando | Esperar, ver `make logs` |
| `502 Bad Gateway` en Cloudflare | Backend/nginx caído | `docker compose ... restart nginx backend` |
| `CORS error` en el browser | `ALLOWED_ORIGINS` no incluye la URL del tunnel | Actualizar `.env.prod` y `make up` |
| ChromaDB retorna 0 resultados | `make seed` no se ejecutó | Ejecutar `make seed` |
| `ValueError: jwt_secret must be overridden` | `.env.prod` tiene valores de ejemplo sin cambiar | Completar todas las variables `CHANGE_ME` |

---

## 6. Demo credentials

| Campo | Valor |
|-------|-------|
| Email | `demo@bioshield.app` |
| Password | `Demo2026!` |
| Datos | Biomarcadores ficticios (glucosa 95 mg/dL, colesterol 182 mg/dL, triglicéridos 118 mg/dL) |
| Nota | Todos los valores son ficticios para demostración — no representan datos médicos reales |

El usuario demo se crea ejecutando `make seed` después del primer deploy.

---

## 7. Backup y restore

### Backup manual de PostgreSQL

```bash
# Desde el VM:
docker exec bioshield-postgres-1 pg_dump -U bioshield bioshield | \
  gzip > /opt/bioshield/data/backups/db_manual_$(date +%Y%m%d_%H%M).sql.gz
```

### Restore de PostgreSQL

```bash
# Detener el backend para evitar escrituras durante restore
docker compose -f docker-compose.prod.yml stop backend

# Restaurar
gunzip -c /opt/bioshield/data/backups/db_YYYYMMDD.sql.gz | \
  docker exec -i bioshield-postgres-1 psql -U bioshield bioshield

# Reiniciar
docker compose -f docker-compose.prod.yml start backend
```

### Backup de ChromaDB

ChromaDB persiste en `./data/chroma_db/` en el host. Basta con copiar ese directorio:

```bash
tar -czf /opt/bioshield/data/backups/chroma_$(date +%Y%m%d).tar.gz \
  -C /opt/bioshield/data chroma_db
```

---

## 8. Rotación de AES_KEY

> ⚠️ AES_KEY encripta todos los biomarcadores. Una rotación incorrecta deja datos irrecuperables.

El procedimiento requiere el script `scripts/rotate_aes_key.py` (pendiente de implementar).  
Hasta entonces, la única opción es:
1. Hacer backup de la DB
2. Eliminar todos los biomarcadores (`DELETE FROM biomarkers`)
3. Actualizar `AES_KEY` en `.env.prod` y reiniciar
4. Pedir a los usuarios que re-suban sus datos

---

## 9. Rollback de migraciones

```bash
# Ver historial de migraciones
docker compose -f docker-compose.prod.yml exec backend alembic history --verbose

# Revertir una migración
docker compose -f docker-compose.prod.yml exec backend alembic downgrade <revision_id>

# Revertir todas las migraciones
docker compose -f docker-compose.prod.yml exec backend alembic downgrade base
```
