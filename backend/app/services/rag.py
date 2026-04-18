"""ChromaDB persistence layer.

Owns the 'bioshield_ingredients' collection. Ingest/query by entity_id with
metadata for downstream filtering (region, severity, source).

Embedding dimension is fixed by the model; switching Gemini ↔ BGE-M3
requires deleting and re-ingesting.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class RAGHit:
    entity_id: str
    document: str
    metadata: dict[str, Any]
    similarity: float  # 0..1 (1 - normalized distance)


@lru_cache(maxsize=4)
def _client_for(persist_directory: str) -> chromadb.ClientAPI:
    """Cached Chroma client. Uses ephemeral mode if persist_directory is empty."""
    if not persist_directory:
        return chromadb.EphemeralClient()
    return chromadb.PersistentClient(path=persist_directory)


def get_collection(settings: Settings) -> Collection:
    """Return the bioshield_ingredients collection, creating it if needed."""
    client = _client_for(settings.chroma_persist_directory)
    return client.get_or_create_collection(
        name=settings.chroma_collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def build_embedding_template(
    entity_id: str,
    canonical_name: str,
    fda_status: str | None = None,
    efsa_status: str | None = None,
    codex_status: str | None = None,
    hazard_note: str | None = None,
    usage_limits: str | None = None,
) -> str:
    """Deterministic embedding template per docs/embedding-strategy.md §3."""
    return (
        f"[ID: {entity_id}] "
        f"[Name: {canonical_name}] "
        f"[Status: FDA:{fda_status or 'N/A'}/EFSA:{efsa_status or 'N/A'}/Codex:{codex_status or 'N/A'}] "
        f"[Risk: {hazard_note or 'N/A'}] "
        f"[Context: {usage_limits or 'N/A'}]"
    )


def upsert_record(
    collection: Collection,
    entity_id: str,
    template_text: str,
    embedding: list[float],
    metadata: dict[str, Any],
) -> None:
    """Insert or update a single record in the collection."""
    collection.upsert(
        ids=[entity_id],
        documents=[template_text],
        embeddings=[embedding],
        metadatas=[metadata],
    )


def query_by_embedding(
    collection: Collection,
    embedding: list[float],
    top_k: int = 5,
    where: dict | None = None,
) -> list[RAGHit]:
    """Return top_k hits for a query embedding, ranked by cosine similarity."""
    result = collection.query(
        query_embeddings=[embedding],
        n_results=top_k,
        where=where,
    )

    ids = (result.get("ids") or [[]])[0]
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    hits: list[RAGHit] = []
    for eid, doc, meta, dist in zip(ids, docs, metas, distances):
        # cosine distance ∈ [0, 2]; convert to similarity ∈ [0, 1]
        similarity = max(0.0, 1.0 - (dist / 2.0))
        hits.append(RAGHit(entity_id=eid, document=doc, metadata=meta or {}, similarity=similarity))
    return hits


def collection_size(collection: Collection) -> int:
    return collection.count()
