# BioShield AI — Backend

## Cómo correr el backend

```bash
# Desde backend/
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Desarrollo
uvicorn app.main:app --reload

# Tests
pytest
pytest --cov=app --cov-report=term-missing
```

## Estructura

```
backend/
├── app/
│   ├── main.py          # FastAPI app, CORS, routers
│   ├── config.py        # Settings (Pydantic) — todas las env vars aquí
│   ├── routers/         # Endpoints HTTP: auth, scan, biosync
│   ├── schemas/         # Pydantic v2 request/response models
│   ├── agents/          # LangGraph: graph.py (StateGraph), nodes.py, state.py
│   └── services/        # Clientes externos: gemini.py, off_client.py, embeddings.py
├── tests/
│   ├── conftest.py      # Fixtures globales: client, db_session, override_settings
│   └── test_*.py        # Un archivo por router/servicio
├── requirements.txt
└── pytest.ini
```

## Convenciones

- **Config:** toda variable de entorno vive en `app/config.py` como campo de `Settings`. Nunca leer `os.environ` directamente.
- **Dependencias FastAPI:** inyectar `settings: Settings = Depends(get_settings)` y `db: Session = Depends(get_db)` en los endpoints.
- **Schemas:** usar únicamente Pydantic v2. Sin `parse_raw`, sin `dict()` — usar `model_validate` y `model_dump`.
- **Gemini Structured Outputs:** pasar el schema Pydantic directamente a la API, no parsear JSON manualmente.
- **Routers:** todos los endpoints excepto `/auth/login` y `/auth/register` requieren JWT válido.
- **Datos médicos:** desencriptar biomarcadores solo en variables locales del grafo — nunca loguear ni persistir el dato en claro.

## Variables de entorno requeridas

Ver `.env.example` en la raíz del proyecto.

## Endpoints principales

| Método | Ruta              | Auth | Descripción                          |
|--------|-------------------|------|--------------------------------------|
| POST   | /auth/register    | No   | Registro de usuario                  |
| POST   | /auth/login       | No   | Login, devuelve JWT                  |
| POST   | /auth/refresh     | No   | Refresca access token                |
| GET    | /health           | No   | Health check                         |
| POST   | /scan/barcode     | JWT  | Escaneo por código de barras         |
| POST   | /scan/photo       | JWT  | Escaneo por foto de etiqueta (Gemini)|
| POST   | /biosync/upload   | JWT  | Subir biomarcadores (AES-256)        |
| GET    | /biosync/status   | JWT  | Estado y expiración de biomarcadores |
| DELETE | /biosync/data     | JWT  | Eliminar datos médicos               |
