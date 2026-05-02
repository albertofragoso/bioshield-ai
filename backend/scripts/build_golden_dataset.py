"""Build a golden dataset for RAG evaluation — fully automated, zero human annotators.

Architecture (3 layers, increasing coverage):

  Layer 1 — Domain Knowledge (confidence 0.95)
    Derives ground truth directly from BIOMARKER_RULES: if a rule's keyword
    appears in an ingredient's canonical_name or synonyms, that pair is a
    verified positive. This IS the expert knowledge already encoded in code.

  Layer 2 — Embedding Retrieval Validation (confidence 0.80–0.90)
    For each rule's canonical query, retrieves top-20 from ChromaDB (BGE-M3).
    Compares against Layer 1 positives. Ingredients returned by semantic search
    that are NOT in Layer 1 are candidate false positives — kept only if their
    similarity is high enough (> LAYER2_CONFIDENCE_THRESHOLD).

  Layer 3 — Gemini Query Variations (confidence 0.70–0.85)
    Asks Gemini to generate alternate phrasings for each rule.
    Runs each phrasing through ChromaDB and validates overlap against Layer 1.
    Only adds a variation query if it recovers ≥ MIN_VARIATION_OVERLAP of
    Layer 1 positives, ensuring consistency with the curated ground truth.

Usage:
    cd backend
    python -m scripts.build_golden_dataset
    python -m scripts.build_golden_dataset --layers 1 2
    python -m scripts.build_golden_dataset --output data/golden/my_dataset.json
    python -m scripts.build_golden_dataset --skip-gemini    # offline mode
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Ingredient
from app.models.base import get_engine
from app.services.analysis import BIOMARKER_RULES, BiomarkerRule, _has_negation
from app.services.embeddings import embed_text
from app.services.rag import collection_size, get_collection, query_by_embedding

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "data" / "golden" / "golden_dataset.json"

# Layer 2: semantic hits above this similarity are kept even without a keyword match.
LAYER2_CONFIDENCE_THRESHOLD = 0.72

# Layer 3: fraction of Layer 1 positives a variant query must recover to be accepted.
MIN_VARIATION_OVERLAP = 0.50

# Top-K used when querying ChromaDB during building.
RETRIEVAL_TOP_K = 20

# How many Gemini query variations to request per rule.
GEMINI_VARIATIONS_PER_RULE = 3


# ──────────────────────────────────────────────────────────────────────────────
# Layer 1 — Domain Knowledge
# ──────────────────────────────────────────────────────────────────────────────

def _keyword_relevance(rule: BiomarkerRule, ingredient: Ingredient) -> tuple[int, str | None]:
    """Return (relevance_score, matched_keyword) using rule keywords against the ingredient.

    Scores:
      5 — exact keyword in canonical_name
      4 — exact keyword in a synonym
      0 — no match

    Applies the same negation and excludes guards as the production matcher so
    Layer 1 ground truth is free of the false positives PR 1 fixed in analysis.py.
    """
    name_lower = (ingredient.canonical_name or "").lower()

    # Guard: excludes on canonical name (same as production)
    if any(ex in name_lower for ex in rule.excludes):
        return 0, None

    for kw in rule.keywords:
        if kw in name_lower and not _has_negation(name_lower, kw):
            return 5, kw

    synonyms: list[str] = ingredient.synonyms or []
    for synonym in synonyms:
        syn_lower = synonym.lower()
        if any(ex in syn_lower for ex in rule.excludes):
            continue
        for kw in rule.keywords:
            if kw in syn_lower and not _has_negation(syn_lower, kw):
                return 4, kw

    return 0, None


def build_layer1(db: Session) -> list[dict[str, Any]]:
    """Generate query entries with ground-truth judgments from BIOMARKER_RULES."""
    logger.info("Layer 1: Building domain knowledge queries from BIOMARKER_RULES …")
    ingredients = list(db.scalars(select(Ingredient)))
    logger.info("  Loaded %d ingredients from DB", len(ingredients))

    queries: list[dict[str, Any]] = []

    for i, rule in enumerate(BIOMARKER_RULES):
        query_text = (
            f"{rule.biomarker.value} {rule.direction}: "
            f"{', '.join(rule.keywords)}"
        )

        judgments: list[dict[str, Any]] = []
        for ing in ingredients:
            relevance, matched_kw = _keyword_relevance(rule, ing)
            if relevance > 0:
                judgments.append(
                    {
                        "ingredient_id": ing.id,
                        "ingredient_name": ing.canonical_name,
                        "entity_id": ing.entity_id,
                        "relevance": relevance,
                        "confidence": 0.95,
                        "match_type": "keyword_exact" if relevance == 5 else "keyword_synonym",
                        "matched_keyword": matched_kw,
                    }
                )

        queries.append(
            {
                "query_id": f"{rule.biomarker.value}_{rule.direction}_{i:03d}",
                "biomarker": rule.biomarker.value,
                "direction": rule.direction,
                "severity": rule.severity.value,
                "query_text": query_text,
                "layer": "layer1_domain_knowledge",
                "judgments": judgments,
            }
        )
        logger.info(
            "  Rule [%s %s]: %d positive judgments",
            rule.biomarker.value,
            rule.direction,
            len(judgments),
        )

    logger.info("Layer 1 complete: %d queries, %d total judgments",
                len(queries), sum(len(q["judgments"]) for q in queries))
    return queries


# ──────────────────────────────────────────────────────────────────────────────
# Layer 2 — Embedding Retrieval Validation
# ──────────────────────────────────────────────────────────────────────────────

async def build_layer2(layer1_queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate semantic retrieval against Layer 1 and surface near-miss positives."""
    settings = get_settings()
    collection = get_collection(settings)
    logger.info("Layer 2: Running embedding retrieval validation (top-%d) …", RETRIEVAL_TOP_K)

    enriched: list[dict[str, Any]] = []

    for entry in layer1_queries:
        query_text = entry["query_text"]
        query_vec = await embed_text(query_text, settings)

        hits = query_by_embedding(collection, query_vec, top_k=RETRIEVAL_TOP_K)

        # Build set of Layer 1 positives for quick lookup
        l1_positive_ids: set[str] = {j["ingredient_id"] for j in entry["judgments"]}
        l1_positive_entity_ids: set[str] = {
            j["entity_id"] for j in entry["judgments"] if j.get("entity_id")
        }

        extra_judgments: list[dict[str, Any]] = []
        retrieval_stats = {"true_positives": 0, "false_positives": 0, "near_misses": 0}

        for hit in hits:
            # Match by entity_id (ChromaDB key) or ingredient_id
            is_l1_positive = (
                hit.entity_id in l1_positive_entity_ids
                or hit.entity_id in l1_positive_ids
            )

            if is_l1_positive:
                retrieval_stats["true_positives"] += 1
                # Already in Layer 1, no need to duplicate; just record similarity
            elif hit.similarity >= LAYER2_CONFIDENCE_THRESHOLD:
                # Semantic near-miss: high similarity but not a keyword match.
                # Could be a synonym the rules don't know yet — worth including.
                retrieval_stats["near_misses"] += 1
                extra_judgments.append(
                    {
                        "ingredient_id": hit.entity_id,
                        "ingredient_name": hit.metadata.get("canonical_name", hit.entity_id),
                        "entity_id": hit.entity_id,
                        "relevance": 3,  # Partial: semantic hit, no explicit keyword
                        "confidence": round(hit.similarity * 0.90, 3),
                        "match_type": "semantic_near_miss",
                        "matched_keyword": None,
                        "cosine_similarity": round(hit.similarity, 4),
                    }
                )
            else:
                retrieval_stats["false_positives"] += 1

        enriched_entry = {
            **entry,
            "layer2_retrieval_stats": retrieval_stats,
            "layer2_judgments": extra_judgments,
        }
        enriched.append(enriched_entry)

        tp = retrieval_stats["true_positives"]
        l1_count = len(l1_positive_ids)
        recall = tp / l1_count if l1_count > 0 else 0.0
        logger.info(
            "  [%s %s] recall@%d=%.2f | near_misses=%d",
            entry["biomarker"],
            entry["direction"],
            RETRIEVAL_TOP_K,
            recall,
            retrieval_stats["near_misses"],
        )

    logger.info("Layer 2 complete.")
    return enriched


# ──────────────────────────────────────────────────────────────────────────────
# Layer 3 — Gemini Query Variations
# ──────────────────────────────────────────────────────────────────────────────

_VARIATION_PROMPT = """\
You are a clinical nutrition expert. Given a biomarker rule, generate {n} ALTERNATIVE
query phrasings that a user might use to search for food ingredients that affect
this biomarker.

Biomarker: {biomarker}
Direction: the ingredient {direction} this biomarker
Canonical keywords: {keywords}
Severity: {severity}

Rules:
- Use different vocabulary than the canonical keywords (synonyms, clinical terms, colloquial)
- Keep queries short (5–15 words)
- Do NOT include numerical biomarker values (privacy constraint)
- Respond ONLY with a JSON array of strings, no explanations

Example output:
["foods that spike blood sugar", "sugary additives and glycemic load"]
"""


async def _call_gemini_for_variations(rule: BiomarkerRule, n: int) -> list[str]:
    """Ask Gemini to generate n alternate query phrasings for a biomarker rule."""
    try:
        import google.generativeai as genai

        settings = get_settings()
        if not settings.gemini_api_key:
            return []

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.gemini_model)

        prompt = _VARIATION_PROMPT.format(
            n=n,
            biomarker=rule.biomarker.value.replace("_", " "),
            direction=rule.direction,
            keywords=", ".join(rule.keywords),
            severity=rule.severity.value,
        )

        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"},
        )
        variations = json.loads(response.text)
        if isinstance(variations, list):
            return [str(v) for v in variations[:n]]
    except Exception as exc:
        logger.warning("Gemini variation generation failed for [%s]: %s", rule.biomarker.value, exc)
    return []


async def build_layer3(
    layer2_entries: list[dict[str, Any]],
    rules: tuple[BiomarkerRule, ...],
) -> list[dict[str, Any]]:
    """Add Gemini-generated query variations validated against Layer 1 ground truth."""
    settings = get_settings()
    collection = get_collection(settings)
    logger.info("Layer 3: Generating Gemini query variations …")

    result: list[dict[str, Any]] = []

    for entry, rule in zip(layer2_entries, rules):
        l1_positive_entity_ids: set[str] = {
            j["entity_id"] for j in entry["judgments"] if j.get("entity_id")
        }
        l1_count = len(l1_positive_entity_ids)

        variations = await _call_gemini_for_variations(rule, GEMINI_VARIATIONS_PER_RULE)
        accepted_variations: list[dict[str, Any]] = []

        for var_text in variations:
            var_vec = await embed_text(var_text, settings)
            hits = query_by_embedding(collection, var_vec, top_k=RETRIEVAL_TOP_K)

            hit_entity_ids = {h.entity_id for h in hits}
            overlap = len(l1_positive_entity_ids & hit_entity_ids) / l1_count if l1_count > 0 else 0.0

            if overlap >= MIN_VARIATION_OVERLAP:
                accepted_variations.append(
                    {
                        "variation_text": var_text,
                        "l1_overlap": round(overlap, 3),
                        "top_hits": [
                            {
                                "entity_id": h.entity_id,
                                "name": h.metadata.get("canonical_name", h.entity_id),
                                "similarity": round(h.similarity, 4),
                            }
                            for h in hits[:5]
                        ],
                    }
                )
                logger.info(
                    "    Accepted variation (overlap=%.2f): %s", overlap, var_text[:60]
                )
            else:
                logger.info(
                    "    Rejected variation (overlap=%.2f < %.2f): %s",
                    overlap,
                    MIN_VARIATION_OVERLAP,
                    var_text[:60],
                )

        result.append({**entry, "layer3_variations": accepted_variations})

    logger.info("Layer 3 complete.")
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Merge + serialize
# ──────────────────────────────────────────────────────────────────────────────

def _merge_judgments(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Merge Layer 1 and Layer 2 judgments, de-duplicating by ingredient_id."""
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []

    for j in entry.get("judgments", []):
        key = j["ingredient_id"]
        if key not in seen:
            seen.add(key)
            merged.append(j)

    for j in entry.get("layer2_judgments", []):
        key = j["ingredient_id"]
        if key not in seen:
            seen.add(key)
            merged.append(j)

    return sorted(merged, key=lambda x: (-x["relevance"], -x["confidence"]))


def serialize_dataset(
    entries: list[dict[str, Any]],
    chromadb_size: int,
    layers_used: list[str],
) -> dict[str, Any]:
    """Produce the final dataset dict, cleaned of internal build fields."""
    queries = []
    total_judgments = 0

    for entry in entries:
        all_judgments = _merge_judgments(entry)
        total_judgments += len(all_judgments)

        queries.append(
            {
                "query_id": entry["query_id"],
                "biomarker": entry["biomarker"],
                "direction": entry["direction"],
                "severity": entry["severity"],
                "query_text": entry["query_text"],
                "layer": entry["layer"],
                "layer2_retrieval_stats": entry.get("layer2_retrieval_stats"),
                "layer3_variations": entry.get("layer3_variations", []),
                "judgments": all_judgments,
            }
        )

    avg_confidence = (
        sum(j["confidence"] for q in queries for j in q["judgments"]) / total_judgments
        if total_judgments > 0
        else 0.0
    )

    return {
        "metadata": {
            "version": "1.0",
            "created_at": datetime.now(UTC).isoformat(),
            "bge_model": "BAAI/bge-m3",
            "chromadb_size": chromadb_size,
            "total_queries": len(queries),
            "total_judgments": total_judgments,
            "avg_confidence": round(avg_confidence, 3),
            "layers_built": layers_used,
        },
        "queries": queries,
        "thresholds": {
            "semantic_similarity": 0.65,
            "layer2_near_miss_min": LAYER2_CONFIDENCE_THRESHOLD,
            "layer3_variation_min_overlap": MIN_VARIATION_OVERLAP,
            # Baselines calibrated empirically: set by --calibrate after first build.
            # Before calibration these are 0 (no regression checks fire).
            "ndcg_at_5_baseline": 0.0,
            "mrr_at_10_baseline": 0.0,
            "precision_at_3_baseline": 0.0,
            "recall_at_10_baseline": 0.0,
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

async def _run(args: argparse.Namespace) -> None:
    settings = get_settings()
    engine = get_engine()
    layers_used: list[str] = []

    with Session(engine) as db:
        # ── Layer 1 ────────────────────────────────────────────────────────
        if 1 in args.layers:
            entries = build_layer1(db)
            layers_used.append("layer1_domain_knowledge")
        else:
            logger.warning("Layer 1 skipped — golden dataset will have no ground truth judgments")
            entries = [
                {
                    "query_id": f"{r.biomarker.value}_{r.direction}_{i:03d}",
                    "biomarker": r.biomarker.value,
                    "direction": r.direction,
                    "severity": r.severity.value,
                    "query_text": f"{r.biomarker.value} {r.direction}: {', '.join(r.keywords)}",
                    "layer": "layer1_domain_knowledge",
                    "judgments": [],
                }
                for i, r in enumerate(BIOMARKER_RULES)
            ]

    # ── Layer 2 ────────────────────────────────────────────────────────────
    if 2 in args.layers:
        entries = await build_layer2(entries)
        layers_used.append("layer2_embedding_retrieval")

    # ── Layer 3 ────────────────────────────────────────────────────────────
    if 3 in args.layers and not args.skip_gemini:
        entries = await build_layer3(entries, BIOMARKER_RULES)
        layers_used.append("layer3_gemini_variations")
    elif 3 in args.layers and args.skip_gemini:
        logger.info("Layer 3 skipped (--skip-gemini).")

    # ── ChromaDB size ───────────────────────────────────────────────────────
    chroma_size = 0
    try:
        collection = get_collection(settings)
        chroma_size = collection_size(collection)
    except Exception:
        logger.warning("Could not reach ChromaDB; chromadb_size will be 0")

    # ── Serialize ───────────────────────────────────────────────────────────
    dataset = serialize_dataset(entries, chroma_size, layers_used)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(dataset, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"✓ Golden dataset written to {output_path}")
    print(f"  Queries  : {dataset['metadata']['total_queries']}")
    print(f"  Judgments: {dataset['metadata']['total_judgments']}")
    print(f"  Avg conf : {dataset['metadata']['avg_confidence']:.3f}")
    print(f"  Layers   : {', '.join(layers_used)}")

    # ── Calibrate baselines (optional) ─────────────────────────────────────
    if getattr(args, "calibrate", False):
        await _calibrate(output_path)


async def _calibrate(dataset_path: Path) -> None:
    """Run the evaluator against the just-built dataset and write calibrated baselines.

    Baselines are set to 90% of the observed metrics so any future 10%+ regression
    is flagged. Writes the baselines back into the dataset JSON in-place.
    """
    # Import here to avoid circular-ish dependency at module level
    import importlib

    eval_mod = importlib.import_module("scripts.evaluate_rag")
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    report = await eval_mod.evaluate(dataset)
    gm = report["global_metrics"]

    calibrated = {
        "ndcg_at_5_baseline": round(gm["ndcg_at_5"] * 0.90, 4),
        "mrr_at_10_baseline": round(gm["mrr_at_10"] * 0.90, 4),
        "precision_at_3_baseline": round(gm["precision_at_3"] * 0.90, 4),
        "recall_at_10_baseline": round(gm["recall_at_10"] * 0.90, 4),
    }

    dataset["thresholds"].update(calibrated)
    dataset_path.write_text(json.dumps(dataset, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n✓ Baselines calibrated (90% of observed metrics):")
    for k, v in calibrated.items():
        raw_key = k.replace("_baseline", "")
        print(f"  {k:<30} {v:.4f}  (observed: {gm[raw_key]:.4f})")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    parser = argparse.ArgumentParser(description="Build BioShield RAG golden evaluation dataset")
    parser.add_argument(
        "--layers",
        nargs="+",
        type=int,
        default=[1, 2, 3],
        choices=[1, 2, 3],
        help="Which layers to run (default: 1 2 3)",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output JSON path (default: data/golden/golden_dataset.json)",
    )
    parser.add_argument(
        "--skip-gemini",
        action="store_true",
        help="Skip Layer 3 Gemini variations (offline mode)",
    )
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="After building, run evaluator and set baselines to 90%% of observed metrics",
    )
    args = parser.parse_args()

    asyncio.run(_run(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
