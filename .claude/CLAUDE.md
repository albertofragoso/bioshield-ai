# BioShield AI — Contexto del Proyecto

## Qué es
Asistente agéntico que analiza etiquetas nutricionales, detecta aditivos ocultos
mediante búsqueda semántica, y cruza hallazgos con biomarcadores de sangre del usuario.

## Stack
- Backend: FastAPI (Python 3.11+)
- Orquestación: LangGraph
- Vector Store: ChromaDB
- LLM: Gemini 1.5 Flash (visión + parsing)
- Embeddings: gemini-embedding-001 (API) con fallback a BGE-M3 (local)
- Frontend: Next.js
- Base de datos: (pendiente definir — ver docs/architecture.md)

## Convenciones
- Usar Pydantic v2 para todos los schemas de request/response.
- Usar Structured Outputs de Gemini para extracción (no parsear JSON manualmente).
- Los prompt templates viven en docs/prompts.md y se importan como constantes.
- Todo endpoint requiere JWT excepto /auth/login y /auth/register.
- Los datos médicos se encriptan con AES-256 antes de persistir.

## Documentación de referencia
- LangGraph: https://www.langchain.com/langgraph
- Open Food Facts API: https://wiki.openfoodfacts.org/API
- Gemini API: https://ai.google.dev/gemini-api/docs
- BGE-M3: https://huggingface.co/BAAI/bge-m3