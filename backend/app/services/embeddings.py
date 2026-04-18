"""Text embedding service.

Primary: Gemini `gemini-embedding-001` (768-dim).
Fallback: local BGE-M3 (1024-dim) — flagged via settings.use_local_embeddings.
Changing models requires re-indexing Chroma (dimension mismatch).
"""

from __future__ import annotations

import logging
from functools import lru_cache

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from app.config import Settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=256)
def _cached_embed(text: str, model: str) -> tuple[float, ...]:
    """Process-local LRU cache keyed by (text, model). Returns immutable tuple."""
    result = genai.embed_content(model=model, content=text)
    vec = result["embedding"] if isinstance(result, dict) else result.embedding
    return tuple(vec)


async def embed_text(text: str, settings: Settings) -> list[float]:
    """Embed a single text string; returns a dense vector."""
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text")

    if settings.use_local_embeddings:
        return _embed_local_bge(text, settings)

    genai.configure(api_key=settings.gemini_api_key)
    try:
        vec = _cached_embed(text.strip(), settings.gemini_embedding_model)
        return list(vec)
    except google_exceptions.GoogleAPIError as exc:
        logger.error("Gemini embedding failed: %s", exc)
        raise RuntimeError("Embedding service unavailable") from exc


def _embed_local_bge(text: str, settings: Settings) -> list[float]:
    """BGE-M3 local fallback path.

    Not installed by default — sentence-transformers adds ~500MB. Enable by
    installing sentence-transformers + torch and implementing here. Tracked
    in backend/reviews/18-04.md.
    """
    raise NotImplementedError(
        "Local BGE-M3 embeddings are not wired in MVP. "
        "Install sentence-transformers and implement _embed_local_bge. "
        "See backend/reviews/18-04.md."
    )
