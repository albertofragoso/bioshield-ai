"""Text embedding service.

Primary: Gemini `gemini-embedding-001` (768-dim).
Fallback: local BGE-M3 (1024-dim) — flagged via settings.use_local_embeddings.
Changing models requires re-indexing Chroma (dimension mismatch).
"""

from __future__ import annotations

import asyncio
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
        return _embed_local_bge(text, settings)

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
