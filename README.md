# BioShield AI

Agentic assistant that analyzes nutritional labels, detects hidden additives via semantic search, and cross-references findings with the user's blood biomarkers.

## Features

- **Barcode scanning** — looks up products in Open Food Facts and extracts ingredients automatically
- **Photo label extraction** — uses Gemini Vision to parse nutritional labels from images
- **Ingredient risk analysis** — semantic search against FDA (EAFUS/GRAS), EFSA, and Codex Alimentarius databases to flag regulated or controversial additives
- **Regulatory conflict detection** — surfaces discrepancies between FDA and EFSA rulings on the same substance
- **Biomarker integration** — cross-references ingredient risks against the user's personal health data (AES-256 encrypted at rest)
- **JWT authentication** — access + refresh token flow with per-user rate limiting

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI 0.115 + Python 3.11 |
| Agent orchestration | LangGraph 0.3 |
| LLM / Vision | Gemini 1.5 Flash |
| Embeddings | gemini-embedding-001 (API) · BGE-M3 (local fallback) |
| Vector store | ChromaDB |
| Database | SQLite (dev) · PostgreSQL (prod) |
| Migrations | Alembic |
| Frontend (planned) | Next.js on Vercel |

## Project Structure

```
bio_shield/
├── backend/
│   ├── app/
│   │   ├── agents/          # LangGraph graph and nodes
│   │   ├── middleware/       # JWT validation, rate limiting
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── routers/         # auth, scan, biosync endpoints
│   │   ├── schemas/         # Pydantic v2 request/response models
│   │   ├── services/        # Gemini, embeddings, Open Food Facts clients
│   │   ├── config.py        # Pydantic Settings
│   │   └── main.py          # App factory + router registration
│   ├── alembic/             # DB migrations
│   ├── tests/               # pytest test suite
│   └── requirements.txt
├── docs/
│   ├── architecture.md      # DB schema + system design
│   ├── data-sources.md      # RAG pipeline + data source specs
│   ├── embedding-strategy.md
│   └── prompts.md
├── .env.example
└── PRD.md
```

## Getting Started

### Prerequisites

- Python 3.11+
- A [Gemini API key](https://ai.google.dev/gemini-api)

### Installation

```bash
# Clone
git clone <repo-url>
cd bio_shield/backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
```

Edit `.env` and fill in at minimum:

| Variable | Description |
|---|---|
| `JWT_SECRET` | Random 32-char string — `openssl rand -hex 32` |
| `AES_KEY` | Exactly 32 ASCII bytes for AES-256 encryption |
| `GEMINI_API_KEY` | Your Google Gemini API key |
| `DATABASE_URL` | SQLite path for dev, PostgreSQL URL for prod |

### Database Setup

```bash
alembic upgrade head
```

### Run

```bash
uvicorn app.main:app --reload
```

API docs available at `http://localhost:8000/docs`.

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | — | Create account |
| POST | `/auth/login` | — | Obtain access + refresh tokens |
| POST | `/auth/refresh` | — | Rotate refresh token |
| POST | `/auth/logout` | JWT | Invalidate session |
| POST | `/scan/barcode` | JWT | Scan product by barcode |
| POST | `/scan/photo` | JWT | Analyze label from image |
| POST | `/biosync/upload` | JWT | Upload biomarker data |
| GET | `/biosync/` | JWT | Retrieve current biomarkers |
| GET | `/health` | — | Health check |

Rate limits: 10 req/min on auth endpoints · 20 req/min on scan endpoints.

## Testing

```bash
cd backend
pytest --cov=app tests/
```

## Environment Variable Reference

See [`.env.example`](.env.example) for the full list with descriptions.

Key variables:

- `USE_LOCAL_EMBEDDINGS=true` — switches to local BGE-M3 model when the Gemini API is unavailable
- `CHROMA_PERSIST_DIRECTORY` — path where ChromaDB stores vector data
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` / `JWT_REFRESH_TOKEN_EXPIRE_DAYS` — token lifetimes
- `ALLOWED_ORIGINS` — comma-separated CORS origins for the frontend

## Documentation

- [Architecture & DB schema](docs/architecture.md)
- [RAG data sources](docs/data-sources.md)
- [Product Requirements](PRD.md)

## License

Software: [MIT](LICENSE) · Regulatory data: [ODbL](https://opendatacommons.org/licenses/odbl/)
