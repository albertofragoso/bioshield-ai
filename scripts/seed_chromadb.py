#!/usr/bin/env python3
"""Seed ChromaDB with additive data from Open Food Facts API.

Fetches the most common food additives (E-numbers) from Open Food Facts,
generates embeddings, and indexes them in ChromaDB for semantic search.

Usage (from repo root, with the stack running):
    # Inside the container (via make seed):
    docker compose -f docker-compose.prod.yml exec backend python /app/scripts/seed_chromadb.py

    # Or locally (requires backend deps installed and .env.prod loaded):
    cd backend && python ../scripts/seed_chromadb.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _ROOT / "backend"
sys.path.insert(0, str(_BACKEND))
os.chdir(_BACKEND)

import httpx  # noqa: E402

from app.config import Settings  # noqa: E402
from app.services.embeddings import embed_text  # noqa: E402
from app.services.rag import (  # noqa: E402
    build_embedding_template,
    get_collection,
    upsert_record,
)

OFF_API = "https://world.openfoodfacts.org/api/v2/search"
BATCH_SIZE = 50
MAX_PRODUCTS = 500


async def fetch_additives(client: httpx.AsyncClient) -> list[dict]:
    """Fetch products with additives from Open Food Facts."""
    additives: dict[str, dict] = {}
    page = 1

    while len(additives) < MAX_PRODUCTS:
        resp = await client.get(
            OFF_API,
            params={
                "fields": "additives_tags,additives_original_tags,product_name",
                "page_size": 100,
                "page": page,
                "json": 1,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        products = data.get("products", [])
        if not products:
            break

        for product in products:
            for tag in product.get("additives_tags", []):
                # tag format: "en:e471" → normalize to "E471"
                code = tag.replace("en:", "").upper()
                if code not in additives and code.startswith("E"):
                    additives[code] = {
                        "entity_id": f"OFF:{code}",
                        "canonical_name": code,
                        "e_number": code,
                        "fda_status": "UNKNOWN",
                        "efsa_status": "UNKNOWN",
                        "codex_status": "UNKNOWN",
                        "hazard_note": f"Additive {code} found in processed foods. Regulatory status varies by region.",
                        "usage_limits": "Varies by application and region",
                        "severity": None,
                        "conflict_flag": False,
                    }

        print(f"  Page {page}: {len(additives)} unique additives collected")
        page += 1

        if len(products) < 100:
            break

    return list(additives.values())[:MAX_PRODUCTS]


async def main() -> None:
    settings = Settings()
    collection = get_collection(settings)

    existing = collection.count()
    print(f"ChromaDB collection '{settings.chroma_collection_name}': {existing} existing records\n")

    print("Fetching additives from Open Food Facts...")
    async with httpx.AsyncClient() as client:
        additives = await fetch_additives(client)

    print(f"\nIndexing {len(additives)} additives into ChromaDB...")
    print(f"Embedding model: {'BGE local' if settings.use_local_embeddings else settings.gemini_embedding_model}\n")

    for i, ing in enumerate(additives, 1):
        template = build_embedding_template(
            entity_id=ing["entity_id"],
            canonical_name=ing["canonical_name"],
            fda_status=ing["fda_status"],
            efsa_status=ing["efsa_status"],
            codex_status=ing["codex_status"],
            hazard_note=ing["hazard_note"],
            usage_limits=ing["usage_limits"],
        )
        embedding = await embed_text(template, settings)
        upsert_record(
            collection,
            entity_id=ing["entity_id"],
            template_text=template,
            embedding=embedding,
            metadata={
                "entity_id": ing["entity_id"],
                "canonical_name": ing["canonical_name"],
                "e_number": ing["e_number"],
                "region": "GLOBAL",
                "source": "OPEN_FOOD_FACTS",
                "conflict_flag": ing["conflict_flag"],
                "severity": ing["severity"] or "",
                "data_version": "2026.06",
            },
        )
        if i % 50 == 0 or i == len(additives):
            print(f"  [{i}/{len(additives)}] indexed")

    total = collection.count()
    print(f"\nDone — {total} total records in '{settings.chroma_collection_name}'")


if __name__ == "__main__":
    asyncio.run(main())
