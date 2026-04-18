"""Hybrid retrieval: vector (Chroma) + BM25 (in-process) with fallback chain.

Per docs/embedding-strategy.md §5:
    score = 0.7 * vector_similarity + 0.3 * bm25_score

Fallback order when the primary path fails:
  1. Chroma healthy → vector + BM25 hybrid (top path)
  2. Chroma fails → BM25-only over SQL corpus
  3. Both fail → empty list (degraded response, semaphore = GRAY)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from rank_bm25 import BM25L
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Ingredient
from app.services.embeddings import embed_text
from app.services.rag import RAGHit, get_collection, query_by_embedding

logger = logging.getLogger(__name__)

_VECTOR_WEIGHT = 0.7
_BM25_WEIGHT = 0.3
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class RankedHit:
    entity_id: str
    document: str
    metadata: dict
    score: float  # hybrid score (or BM25-only in fallback)


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _build_bm25_corpus(db: Session) -> tuple[BM25L, list[Ingredient]]:
    """Build an in-memory BM25 index over all ingredients in SQL.

    Corpus = canonical_name + synonyms. Small enough (< 20k records) to
    rebuild on demand; a long-lived service should cache this.
    """
    ingredients = list(db.scalars(select(Ingredient)))
    corpus: list[list[str]] = []
    for ing in ingredients:
        parts = [ing.canonical_name] + list(ing.synonyms or [])
        corpus.append(_tokenize(" ".join(parts)))
    if not corpus:
        corpus = [[""]]  # rank_bm25 rejects empty corpora
    return BM25L(corpus), ingredients


def _bm25_scores(bm25: BM25L, query: str) -> list[float]:
    scores = bm25.get_scores(_tokenize(query))
    peak = max(scores) if len(scores) else 0.0
    if peak <= 0:
        return [0.0] * len(scores)
    return [s / peak for s in scores]  # normalize 0..1


async def hybrid_search(
    query: str,
    db: Session,
    settings: Settings,
    top_k: int = 5,
    where: dict | None = None,
) -> list[RankedHit]:
    """Run hybrid vector + BM25 retrieval with graceful degradation."""
    bm25, bm25_corpus = _build_bm25_corpus(db)
    bm25_norm = _bm25_scores(bm25, query)
    bm25_by_entity = {
        ing.entity_id: bm25_norm[i]
        for i, ing in enumerate(bm25_corpus)
        if ing.entity_id
    }

    try:
        embedding = await embed_text(query, settings)
        collection = get_collection(settings)
        vector_hits = query_by_embedding(collection, embedding, top_k=top_k * 3, where=where)
    except Exception as exc:
        logger.warning("Vector search failed, degrading to BM25-only: %s", exc)
        return _bm25_only(bm25_corpus, bm25_norm, top_k)

    fused: list[RankedHit] = []
    seen: set[str] = set()
    for hit in vector_hits:
        bm25_score = bm25_by_entity.get(hit.entity_id, 0.0)
        score = _VECTOR_WEIGHT * hit.similarity + _BM25_WEIGHT * bm25_score
        fused.append(RankedHit(entity_id=hit.entity_id, document=hit.document, metadata=hit.metadata, score=score))
        seen.add(hit.entity_id)

    # Include BM25-only matches not in vector hits (for recall)
    for ing, score in zip(bm25_corpus, bm25_norm):
        if ing.entity_id and ing.entity_id not in seen and score > 0.5:
            fused.append(
                RankedHit(
                    entity_id=ing.entity_id,
                    document=ing.canonical_name,
                    metadata={"canonical_name": ing.canonical_name},
                    score=_BM25_WEIGHT * score,
                )
            )

    fused.sort(key=lambda h: h.score, reverse=True)
    return fused[:top_k]


def _bm25_only(
    ingredients: list[Ingredient],
    scores: list[float],
    top_k: int,
) -> list[RankedHit]:
    ranked = [
        RankedHit(
            entity_id=ing.entity_id or f"sql:{ing.id}",
            document=ing.canonical_name,
            metadata={"canonical_name": ing.canonical_name, "degraded": True},
            score=score,
        )
        for ing, score in zip(ingredients, scores)
        if score > 0
    ]
    ranked.sort(key=lambda h: h.score, reverse=True)
    return ranked[:top_k]
