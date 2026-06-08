# BioShield AI

Agente que analiza etiquetas nutricionales, detecta aditivos ocultos mediante búsqueda semántica, y cruza hallazgos con biomarcadores de sangre del usuario.

## Intent Layer

**Antes de modificar código en un subdirectorio, leer su CLAUDE.md primero.**

| Área | Archivo | Responsabilidad |
|------|---------|-----------------|
| Backend | `backend/CLAUDE.md` | FastAPI, LangGraph, ChromaDB, endpoints, auth |
| Frontend | `frontend/CLAUDE.md` | Next.js 16 App Router, shadcn/ui, TanStack Query |
| Tests | `backend/tests/CLAUDE.md` | Pytest, fixtures, CI gate rules |

### Global Invariants

- **JWT obligatorio** en todos los endpoints excepto `/auth/login`, `/auth/register`, `/auth/refresh`
- **Datos médicos van encriptados** (AES-256/Fernet) antes de persistir — nunca plaintext en DB
- **Biomarkers expiran en 180 días** — el campo `expires_at` se valida en DB y en queries
- **LLM endpoints necesitan budget guard** — `Depends(token_budget(...))` en cada endpoint que llame a Gemini, sin excepción; `tests/test_ci_gate.py` verifica esto
- **Nunca leer `os.environ` directamente** — toda config pasa por `backend/app/config.py` (Pydantic Settings)
- **Nunca llamar `fetch()` en componentes** — todo HTTP pasa por `frontend/lib/api/client.ts`
- **Tests E2E Playwright en `tests/specs/{feature}/`** (raíz del repo), nunca dentro de `frontend/`

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | FastAPI (Python 3.11+), LangGraph, SQLAlchemy 2.0 |
| LLM | Gemini 2.5 Flash (visión + parsing) |
| Embeddings | gemini-embedding-001 con fallback BGE-M3 |
| Vector store | ChromaDB |
| Frontend | Next.js 16, Tailwind CSS v4, shadcn/ui |
| Base de datos | SQLite (dev) / PostgreSQL (prod) |

## Correr el proyecto completo

```bash
# Stack completo (backend + frontend + postgres)
docker compose up --build

# Backend solo
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload

# Frontend solo
cd frontend && pnpm dev
```

## Convenciones globales

- Conventional commits: `type(scope): description` — max 72 chars primera línea
- Schemas Pydantic v2; `lib/api/types.ts` debe espejar `backend/app/schemas/models.py`
- Prompt templates en `docs/prompts.md`, importados como constantes — no inline
- Docs de arquitectura en `docs/architecture.md`; actualizar en el mismo PR que el código

## Documentación de referencia

- Arquitectura y schema DB: `docs/architecture.md`
- Estrategia de embeddings: `docs/embedding-strategy.md`
- Fuentes de datos RAG: `docs/data-sources.md`
- Prompt templates: `docs/prompts.md`
- Soluciones documentadas: `docs/solutions/` — bugs, patrones y decisiones organizados por categoría con frontmatter YAML (`module`, `tags`, `problem_type`)
- Vocabulario del dominio: `CONCEPTS.md` — entidades, procesos y conceptos con significado específico en este proyecto
