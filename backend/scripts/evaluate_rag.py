"""Evaluate current RAG quality against a golden dataset.

Computes NDCG@5, MRR@10, Precision@3, Recall@10 for each biomarker rule
and writes a timestamped report to data/golden/eval_<timestamp>.json.

Usage:
    cd backend
    python -m scripts.evaluate_rag
    python -m scripts.evaluate_rag --dataset data/golden/golden_dataset.json
    python -m scripts.evaluate_rag --fail-on-regression  # exit 1 if metrics drop
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.services.embeddings import embed_text
from app.services.rag import collection_size, get_collection, query_by_embedding

logger = logging.getLogger(__name__)

DEFAULT_DATASET = (
    Path(__file__).resolve().parent.parent / "data" / "golden" / "golden_dataset.json"
)
DEFAULT_REPORT_DIR = Path(__file__).resolve().parent.parent / "data" / "golden"

RETRIEVAL_TOP_K = 10  # must be >= max K used in metrics below


# ──────────────────────────────────────────────────────────────────────────────
# Metric helpers
# ──────────────────────────────────────────────────────────────────────────────


def _dcg(relevances: list[float]) -> float:
    return sum(rel / math.log2(rank + 2) for rank, rel in enumerate(relevances))


def ndcg_at_k(retrieved_ids: list[str], judgments: list[dict], k: int) -> float:
    """Normalized Discounted Cumulative Gain at K."""
    rel_map = {j["ingredient_id"]: j["relevance"] for j in judgments}
    if not rel_map:
        return 0.0

    pred = [rel_map.get(eid, 0) for eid in retrieved_ids[:k]]
    ideal = sorted(rel_map.values(), reverse=True)[:k]

    dcg = _dcg(pred)
    idcg = _dcg(ideal)
    return dcg / idcg if idcg > 0 else 0.0


def mrr_at_k(retrieved_ids: list[str], judgments: list[dict], k: int) -> float:
    """Mean Reciprocal Rank at K (single query — returns the reciprocal rank)."""
    positive_ids = {j["ingredient_id"] for j in judgments if j["relevance"] >= 4}
    for rank, eid in enumerate(retrieved_ids[:k], start=1):
        if eid in positive_ids:
            return 1.0 / rank
    return 0.0


def precision_at_k(retrieved_ids: list[str], judgments: list[dict], k: int) -> float:
    """Fraction of top-K retrieved that are relevant (relevance >= 3)."""
    positive_ids = {j["ingredient_id"] for j in judgments if j["relevance"] >= 3}
    hits = sum(1 for eid in retrieved_ids[:k] if eid in positive_ids)
    return hits / k if k > 0 else 0.0


def recall_at_k(retrieved_ids: list[str], judgments: list[dict], k: int) -> float:
    """Fraction of positives recovered in top-K (relevance >= 4)."""
    positive_ids = {j["ingredient_id"] for j in judgments if j["relevance"] >= 4}
    if not positive_ids:
        return 1.0  # vacuously true if no positives exist
    hits = sum(1 for eid in retrieved_ids[:k] if eid in positive_ids)
    return hits / len(positive_ids)


# ──────────────────────────────────────────────────────────────────────────────
# Evaluation loop
# ──────────────────────────────────────────────────────────────────────────────


async def evaluate(dataset: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    collection = get_collection(settings)
    thresholds = dataset.get("thresholds", {})

    per_query: list[dict[str, Any]] = []
    per_biomarker: dict[str, list[dict]] = {}

    for query_entry in dataset["queries"]:
        qid = query_entry["query_id"]
        biomarker = query_entry["biomarker"]
        query_text = query_entry["query_text"]
        judgments = query_entry.get("judgments", [])

        if not judgments:
            logger.debug("Skipping %s — no judgments", qid)
            continue

        query_vec = await embed_text(query_text, settings)
        hits = query_by_embedding(collection, query_vec, top_k=RETRIEVAL_TOP_K)
        retrieved_ids = [h.entity_id for h in hits]

        # Map entity_id → ingredient_id in judgments (they may differ)
        # Build a unified lookup so both ID types match
        entity_to_ingr: dict[str, str] = {
            j.get("entity_id", j["ingredient_id"]): j["ingredient_id"]
            for j in judgments
            if j.get("entity_id")
        }
        resolved_ids = [entity_to_ingr.get(eid, eid) for eid in retrieved_ids]

        scores = {
            "ndcg_at_5": ndcg_at_k(resolved_ids, judgments, 5),
            "mrr_at_10": mrr_at_k(resolved_ids, judgments, 10),
            "precision_at_3": precision_at_k(resolved_ids, judgments, 3),
            "recall_at_10": recall_at_k(resolved_ids, judgments, 10),
        }

        per_query.append(
            {
                "query_id": qid,
                "biomarker": biomarker,
                "direction": query_entry["direction"],
                "scores": scores,
                "retrieved_top5": [
                    {
                        "entity_id": h.entity_id,
                        "name": h.metadata.get("canonical_name", h.entity_id),
                        "similarity": round(h.similarity, 4),
                    }
                    for h in hits[:5]
                ],
            }
        )
        per_biomarker.setdefault(biomarker, []).append(scores)

    # ── Aggregate ────────────────────────────────────────────────────────────

    def _mean(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    all_scores = [q["scores"] for q in per_query]
    global_metrics = {
        "ndcg_at_5": round(_mean([s["ndcg_at_5"] for s in all_scores]), 4),
        "mrr_at_10": round(_mean([s["mrr_at_10"] for s in all_scores]), 4),
        "precision_at_3": round(_mean([s["precision_at_3"] for s in all_scores]), 4),
        "recall_at_10": round(_mean([s["recall_at_10"] for s in all_scores]), 4),
    }

    bm_summary: dict[str, dict] = {}
    for bm, score_list in per_biomarker.items():
        bm_summary[bm] = {
            k: round(_mean([s[k] for s in score_list]), 4) for k in score_list[0]
        }

    # ── Regression check ────────────────────────────────────────────────────

    baseline = {
        "ndcg_at_5": thresholds.get("ndcg_at_5_baseline", 0.70),
        "mrr_at_10": thresholds.get("mrr_at_10_baseline", 0.60),
        "precision_at_3": thresholds.get("precision_at_3_baseline", 0.75),
        "recall_at_10": thresholds.get("recall_at_10_baseline", 0.80),
    }
    failures = [
        {"metric": k, "baseline": baseline[k], "actual": global_metrics[k]}
        for k in baseline
        if global_metrics[k] < baseline[k]
    ]

    chroma_size = 0
    try:
        chroma_size = collection_size(collection)
    except Exception:
        pass

    return {
        "run_id": f"eval_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now(UTC).isoformat(),
        "golden_dataset_version": dataset.get("metadata", {}).get("version", "unknown"),
        "golden_dataset_created_at": dataset.get("metadata", {}).get("created_at"),
        "bge_model": "BAAI/bge-m3",
        "chromadb_size": chroma_size,
        "queries_evaluated": len(per_query),
        "global_metrics": global_metrics,
        "per_biomarker": bm_summary,
        "baseline_thresholds": baseline,
        "regressions": failures,
        "status": "FAIL" if failures else "PASS",
        "per_query_detail": per_query,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────


async def _run(args: argparse.Namespace) -> int:
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"ERROR: Golden dataset not found at {dataset_path}")
        print("Run: python -m scripts.build_golden_dataset")
        return 1

    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    report = await evaluate(dataset)

    # ── Print summary ────────────────────────────────────────────────────────
    gm = report["global_metrics"]
    print(f"\n{'─' * 50}")
    print(f"BioShield RAG Evaluation — {report['timestamp'][:10]}")
    print(f"{'─' * 50}")
    print(f"  NDCG@5       : {gm['ndcg_at_5']:.4f}  (baseline ≥ {report['baseline_thresholds']['ndcg_at_5']})")
    print(f"  MRR@10       : {gm['mrr_at_10']:.4f}  (baseline ≥ {report['baseline_thresholds']['mrr_at_10']})")
    print(f"  Precision@3  : {gm['precision_at_3']:.4f}  (baseline ≥ {report['baseline_thresholds']['precision_at_3']})")
    print(f"  Recall@10    : {gm['recall_at_10']:.4f}  (baseline ≥ {report['baseline_thresholds']['recall_at_10']})")
    print(f"{'─' * 50}")

    if report["regressions"]:
        print("⚠️  REGRESSIONS DETECTED:")
        for r in report["regressions"]:
            delta = r["actual"] - r["baseline"]
            print(f"    {r['metric']}: {r['actual']:.4f} (Δ {delta:+.4f} vs baseline {r['baseline']})")
    else:
        print("✅ All metrics above baseline.")

    print("\nPer-biomarker NDCG@5:")
    for bm, scores in sorted(report["per_biomarker"].items()):
        print(f"  {bm:<20} {scores['ndcg_at_5']:.4f}")

    # ── Write report ─────────────────────────────────────────────────────────
    if not args.no_report:
        report_path = DEFAULT_REPORT_DIR / f"{report['run_id']}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nFull report: {report_path}")

    if args.fail_on_regression and report["regressions"]:
        return 1
    return 0


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")

    parser = argparse.ArgumentParser(description="Evaluate BioShield RAG against golden dataset")
    parser.add_argument(
        "--dataset",
        default=str(DEFAULT_DATASET),
        help="Path to golden_dataset.json (default: data/golden/golden_dataset.json)",
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit with code 1 if any metric is below baseline (for CI)",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip writing the timestamped JSON report",
    )
    args = parser.parse_args()

    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
