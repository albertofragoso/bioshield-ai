"""Text embedding service.

Primary: BGE-M3 local (1024-dim) — activated when USE_LOCAL_EMBEDDINGS=true (default).
Fallback: Gemini `gemini-embedding-001` (768-dim) — USE_LOCAL_EMBEDDINGS=false.
Changing models requires re-indexing Chroma (dimension mismatch — see docs/runbooks).

Gemini is still required for Vision OCR and personalized insight copy generation,
but is no longer in the embedding path when local embeddings are enabled.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from functools import lru_cache

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from app.config import Settings

logger = logging.getLogger(__name__)

# BGE-M3 singleton — loaded lazily on first call to _embed_local_bge.
# threading.Lock (not asyncio) because _embed_local_bge is a sync function
# called from asyncio.to_thread's thread pool.
_bge_model = None
_bge_load_lock = threading.Lock()


@lru_cache(maxsize=256)
def _cached_embed(text: str, model: str) -> tuple[float, ...]:
    """Process-local LRU cache keyed by (text, model). Returns immutable tuple."""
    result = genai.embed_content(model=model, content=text)
    vec = result["embedding"] if isinstance(result, dict) else result.embedding
    return tuple(vec)


# Tracks whether the last _cached_embed call hit the lru cache (no API call made).
_embed_cache: set[tuple[str, str]] = set()

# Serializes live API calls and enforces inter-call delay to respect free-tier
# RPM limits (≈15 RPM → 4s headroom). Cache hits bypass lock and delay entirely.
_EMBED_API_LOCK = asyncio.Lock()
_EMBED_INTER_CALL_DELAY = 4.0  # seconds between live API calls


async def embed_text(text: str, settings: Settings) -> list[float]:
    """Embed a single text string; returns a dense vector.

    Cache hits (same text + model seen before) are returned immediately without
    acquiring the API lock or waiting. Live API calls are serialized and paced
    to avoid 60-120s retry storms on free-tier rate limits.
    """
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text")

    if settings.use_local_embeddings:
        return await asyncio.to_thread(_embed_local_bge, text, settings)

    genai.configure(api_key=settings.gemini_api_key)
    key = (text.strip(), settings.gemini_embedding_model)

    # Fast path: LRU cache already has this vector — no API call needed.
    if key in _embed_cache:
        return list(_cached_embed(*key))

    # Slow path: serialize and pace live API calls.
    async with _EMBED_API_LOCK:
        # Re-check after acquiring the lock — another coroutine may have cached it.
        if key in _embed_cache:
            return list(_cached_embed(*key))

        try:
            vec = await asyncio.to_thread(_cached_embed, *key)
            _embed_cache.add(key)
            await asyncio.sleep(_EMBED_INTER_CALL_DELAY)
            return list(vec)
        except google_exceptions.ResourceExhausted:
            # Single back-off retry — avoids the old 60+120+180s storm per ingredient.
            wait = 65.0
            logger.warning("Gemini embedding rate limited; backing off %.0fs", wait)
            await asyncio.sleep(wait)
            try:
                vec = await asyncio.to_thread(_cached_embed, *key)
                _embed_cache.add(key)
                return list(vec)
            except google_exceptions.ResourceExhausted as exc2:
                raise RuntimeError("Embedding service unavailable") from exc2
        except google_exceptions.GoogleAPIError as exc:
            logger.error("Gemini embedding failed: %s", exc)
            raise RuntimeError("Embedding service unavailable") from exc


def _embed_local_bge(text: str, settings: Settings) -> list[float]:
    """BGE-M3 local embedding — runs in asyncio.to_thread, never blocks the event loop.

    Lazy-loads the SentenceTransformer singleton on first call. Double-check
    locking prevents duplicate model loads if multiple threads race at startup.
    """
    global _bge_model
    if _bge_model is None:
        with _bge_load_lock:
            if _bge_model is None:
                from sentence_transformers import SentenceTransformer  # noqa: PLC0415

                _bge_model = SentenceTransformer(settings.bge_model_name)
    return _bge_model.encode(text).tolist()
