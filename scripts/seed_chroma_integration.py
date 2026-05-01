#!/usr/bin/env python3
"""Generate ChromaDB seed snapshot for E2E integration tests.

Usage (from repo root):
    python scripts/seed_chroma_integration.py --output tests/fixtures/chroma-seed

Reads embedding settings from backend/.env. Requires GEMINI_API_KEY if
USE_LOCAL_EMBEDDINGS=false (the default). Set USE_LOCAL_EMBEDDINGS=true
to use BGE-M3 local model instead (needs sentence-transformers installed).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _ROOT / "backend"
sys.path.insert(0, str(_BACKEND))
os.chdir(_BACKEND)  # pydantic-settings reads env_file=".env" relative to cwd

from app.config import Settings  # noqa: E402
from app.services.embeddings import embed_text  # noqa: E402
from app.services.rag import (  # noqa: E402
    build_embedding_template,
    get_collection,
    upsert_record,
)

NUTELLA_INGREDIENTS: list[dict] = [
    {
        "entity_id": "CAS:57-50-1",
        "canonical_name": "Sugar",
        "fda_status": "GRAS",
        "efsa_status": "APPROVED",
        "codex_status": "APPROVED",
        "hazard_note": "High glycemic index; excessive consumption linked to metabolic disorders",
        "usage_limits": "No regulatory limit",
        "e_number": "",
        "severity": "LOW",
        "conflict_flag": False,
    },
    {
        "entity_id": "CAS:57-10-3",
        "canonical_name": "Palm Oil",
        "fda_status": "APPROVED",
        "efsa_status": "APPROVED",
        "codex_status": "APPROVED",
        "hazard_note": "High saturated fat (50%); GE and 3-MCPD contaminants flagged by EFSA at industrial refining temperatures",
        "usage_limits": "No regulatory limit; EFSA recommends minimizing GE exposure",
        "e_number": "",
        "severity": "MEDIUM",
        "conflict_flag": True,
    },
    {
        "entity_id": "CAS:84012-22-6",
        "canonical_name": "Hazelnuts",
        "fda_status": "GRAS",
        "efsa_status": "APPROVED",
        "codex_status": "APPROVED",
        "hazard_note": "Tree nut allergen (FDA Top 9 allergens); no chemical safety concerns",
        "usage_limits": "N/A",
        "e_number": "",
        "severity": "LOW",
        "conflict_flag": False,
    },
    {
        "entity_id": "CAS:8002-31-1",
        "canonical_name": "Cocoa",
        "fda_status": "GRAS",
        "efsa_status": "APPROVED",
        "codex_status": "APPROVED",
        "hazard_note": "May contain cadmium at elevated levels depending on geographic origin",
        "usage_limits": "Cadmium limit: 0.3 mg/kg (EU Reg 2019/1870) for cocoa powder",
        "e_number": "",
        "severity": "LOW",
        "conflict_flag": False,
    },
    {
        "entity_id": "CAS:8056-51-7",
        "canonical_name": "Skimmed Milk Powder",
        "fda_status": "GRAS",
        "efsa_status": "APPROVED",
        "codex_status": "APPROVED",
        "hazard_note": "Milk allergen (FDA Top 9); no chemical safety concerns",
        "usage_limits": "N/A",
        "e_number": "",
        "severity": None,
        "conflict_flag": False,
    },
    {
        "entity_id": "CAS:8013-17-0",
        "canonical_name": "Whey Powder",
        "fda_status": "GRAS",
        "efsa_status": "APPROVED",
        "codex_status": "APPROVED",
        "hazard_note": "Milk allergen; no chemical safety concerns",
        "usage_limits": "N/A",
        "e_number": "",
        "severity": None,
        "conflict_flag": False,
    },
    {
        "entity_id": "CAS:8002-43-5",
        "canonical_name": "Soy Lecithin",
        "fda_status": "GRAS",
        "efsa_status": "APPROVED",
        "codex_status": "APPROVED",
        "hazard_note": "Soy allergen; generally well-tolerated in highly refined form",
        "usage_limits": "quantum satis (EU Regulation)",
        "e_number": "E322",
        "severity": None,
        "conflict_flag": False,
    },
    {
        "entity_id": "CAS:121-33-5",
        "canonical_name": "Vanillin",
        "fda_status": "GRAS",
        "efsa_status": "APPROVED",
        "codex_status": "APPROVED",
        "hazard_note": "No significant hazard at food-use concentrations",
        "usage_limits": "N/A",
        "e_number": "",
        "severity": None,
        "conflict_flag": False,
    },
]


async def main(output_dir: str) -> None:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    settings = Settings(chroma_persist_directory=str(out))
    collection = get_collection(settings)

    print(f"Seeding {len(NUTELLA_INGREDIENTS)} Nutella ingredients → {out}")
    print(f"Embedding model: {'BGE-M3 local' if settings.use_local_embeddings else settings.gemini_embedding_model}\n")

    for ing in NUTELLA_INGREDIENTS:
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
                "source": "INTEGRATION_SEED",
                "conflict_flag": ing["conflict_flag"],
                "severity": ing["severity"] or "",
                "data_version": "2026.04.30",
            },
        )
        print(f"  ✓ {ing['canonical_name']} ({ing['entity_id']})")

    print(f"\nDone — {collection.count()} records in collection '{settings.chroma_collection_name}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", required=True, help="ChromaDB persist directory (will be created)")
    args = parser.parse_args()
    # Resolve relative to the original cwd (repo root) BEFORE os.chdir has moved us to backend/.
    # os.chdir(_BACKEND) runs at import time above, so we use _ROOT to anchor relative paths.
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = (_ROOT / args.output).resolve()
    asyncio.run(main(str(output_path)))
