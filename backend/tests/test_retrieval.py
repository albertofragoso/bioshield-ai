"""Tests para app/services/retrieval — cache BM25 y RetrievalResult."""

from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

import app.services.retrieval as r
from app.services.retrieval import (
    RetrievalResult,
    RankedHit,
    _get_bm25_corpus,
    invalidate_bm25_cache,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_ingredient(name: str = "aspartame", entity_id: str = "eid-001"):
    ing = MagicMock()
    ing.canonical_name = name
    ing.entity_id = entity_id
    ing.synonyms = []
    ing.id = 1
    return ing


def _make_mock_db(ingredients=None):
    """DB mock que devuelve ingredientes cuando se llama a scalars()."""
    if ingredients is None:
        ingredients = [_make_ingredient()]
    db = MagicMock()
    db.scalars.return_value = iter(ingredients)
    return db


def _reset_cache():
    r._bm25_cache = None


# ──────────────────────────────────────────────────────────────────────────────
# 1. invalidate_bm25_cache limpia el cache
# ──────────────────────────────────────────────────────────────────────────────

class TestInvalidateCache(unittest.TestCase):
    def tearDown(self):
        _reset_cache()

    def test_invalidate_clears_cache(self):
        db = _make_mock_db()
        _get_bm25_corpus(db)
        assert r._bm25_cache is not None, "cache debería estar lleno tras primer llamado"

        invalidate_bm25_cache()
        assert r._bm25_cache is None, "cache debería ser None tras invalidar"


# ──────────────────────────────────────────────────────────────────────────────
# 2. _get_bm25_corpus cachea en el segundo llamado
# ──────────────────────────────────────────────────────────────────────────────

class TestGetBm25CorpusCaching(unittest.TestCase):
    def tearDown(self):
        _reset_cache()

    def test_get_bm25_corpus_caches_on_second_call(self):
        db = _make_mock_db()

        with patch.object(r, "_build_bm25_corpus", wraps=r._build_bm25_corpus) as mock_build:
            _reset_cache()
            _get_bm25_corpus(db)
            _get_bm25_corpus(db)

        assert mock_build.call_count == 1, (
            f"_build_bm25_corpus debe llamarse solo una vez; se llamó {mock_build.call_count} veces"
        )


# ──────────────────────────────────────────────────────────────────────────────
# 3. hybrid_search devuelve RetrievalResult en el camino feliz
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class _FakeVectorHit:
    entity_id: str
    document: str
    metadata: dict
    similarity: float


class TestHybridSearchReturnsRetrievalResult(unittest.IsolatedAsyncioTestCase):
    def tearDown(self):
        _reset_cache()

    async def test_hybrid_search_returns_retrieval_result(self):
        ingredient = _make_ingredient()
        db = _make_mock_db([ingredient])
        settings = MagicMock()

        fake_embedding = [0.1] * 768
        fake_vector_hits = [
            _FakeVectorHit(
                entity_id="eid-001",
                document="aspartame",
                metadata={"canonical_name": "aspartame"},
                similarity=0.9,
            )
        ]

        with (
            patch("app.services.retrieval.embed_text", return_value=fake_embedding),
            patch("app.services.retrieval.get_collection", return_value=MagicMock()),
            patch("app.services.retrieval.query_by_embedding", return_value=fake_vector_hits),
        ):
            result = await r.hybrid_search("aspartame", db, settings, top_k=3)

        assert isinstance(result, RetrievalResult), "debe devolver RetrievalResult"
        assert result.fallback_used is False
        assert result.corpus_size > 0
        assert isinstance(result.hits, list)


# ──────────────────────────────────────────────────────────────────────────────
# 4. fallback activa fallback_used=True cuando embed_text lanza excepción
# ──────────────────────────────────────────────────────────────────────────────

class TestHybridSearchFallback(unittest.IsolatedAsyncioTestCase):
    def tearDown(self):
        _reset_cache()

    async def test_hybrid_search_fallback_sets_fallback_used(self):
        ingredient = _make_ingredient()
        db = _make_mock_db([ingredient])
        settings = MagicMock()

        async def _fail(*args, **kwargs):
            raise RuntimeError("chroma down")

        with patch("app.services.retrieval.embed_text", side_effect=_fail):
            result = await r.hybrid_search("aspartame", db, settings, top_k=3)

        assert result.fallback_used is True, "fallback_used debe ser True cuando embed_text falla"
        assert result.embed_ms == 0.0, "embed_ms debe ser 0.0 en fallback"
        assert isinstance(result.hits, list)


# ──────────────────────────────────────────────────────────────────────────────
# 5. embed_ms es positivo cuando embed_text tiene latencia real
# ──────────────────────────────────────────────────────────────────────────────

class TestEmbedMsPositiveOnSuccess(unittest.IsolatedAsyncioTestCase):
    def tearDown(self):
        _reset_cache()

    async def test_embed_ms_is_positive_on_success(self):
        ingredient = _make_ingredient()
        db = _make_mock_db([ingredient])
        settings = MagicMock()

        fake_embedding = [0.1] * 768
        fake_vector_hits = [
            _FakeVectorHit(
                entity_id="eid-001",
                document="aspartame",
                metadata={"canonical_name": "aspartame"},
                similarity=0.9,
            )
        ]

        async def _slow_embed(*args, **kwargs):
            await asyncio.sleep(0.01)  # 10 ms de latencia simulada
            return fake_embedding

        with (
            patch("app.services.retrieval.embed_text", side_effect=_slow_embed),
            patch("app.services.retrieval.get_collection", return_value=MagicMock()),
            patch("app.services.retrieval.query_by_embedding", return_value=fake_vector_hits),
        ):
            result = await r.hybrid_search("aspartame", db, settings, top_k=3)

        assert result.embed_ms > 0, f"embed_ms debe ser > 0, fue {result.embed_ms}"
        assert result.fallback_used is False
