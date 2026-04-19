"""
Manual E2E test: run all test_images through /scan/photo pipeline.
Usage: cd backend && python -m scripts.test_photo_scan
"""

import asyncio
import base64
import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.graph import build_scan_graph
from app.config import Settings

IMAGES_DIR = Path(__file__).parent.parent / "test_images"
RESULTS = []


async def scan_image(image_path: Path, db_session, settings: Settings) -> dict:
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    graph = build_scan_graph(db_session, settings)
    for attempt in range(3):
        try:
            state = await graph.ainvoke({
                "image_b64": b64,
                "user_id": "test-script",
            })
            return state
        except Exception as e:
            msg = str(e)
            if "429" in msg and attempt < 2:
                wait = 65
                print(f"  Rate limited, waiting {wait}s (attempt {attempt+1}/3)...", flush=True)
                await asyncio.sleep(wait)
            else:
                raise
    return {}


def fmt_ingredients(resolved: list) -> str:
    if not resolved:
        return "  (none resolved)"
    lines = []
    for ing in resolved[:10]:
        name = getattr(ing, "canonical_name", None) or getattr(ing, "raw_name", "?")
        status = getattr(ing, "regulatory_status", "?")
        conf = getattr(ing, "confidence_score", 0)
        lines.append(f"  • {name} [{status}] conf={conf:.2f}")
    if len(resolved) > 10:
        lines.append(f"  ... +{len(resolved) - 10} more")
    return "\n".join(lines)


def fmt_conflicts(conflicts: list) -> str:
    if not conflicts:
        return "  (none)"
    lines = []
    for c in conflicts[:5]:
        lines.append(f"  ⚠ {c}")
    return "\n".join(lines)


async def main():
    settings = Settings(_env_file=str(Path(__file__).parent.parent / ".env"))

    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)

    images = sorted(IMAGES_DIR.glob("*.jpeg")) + sorted(IMAGES_DIR.glob("*.jpg")) + sorted(IMAGES_DIR.glob("*.png"))
    print(f"\n{'='*60}")
    print(f"BioShield /scan/photo — {len(images)} images")
    print(f"{'='*60}\n")

    summary = []

    for img in images:
        print(f"[{img.name}] Scanning...", flush=True)
        db = Session()
        try:
            state = await scan_image(img, db, settings)

            semaphore = state.get("semaphore", "GRAY")
            if hasattr(semaphore, "value"):
                semaphore = semaphore.value

            resolved = state.get("resolved") or []
            extracted = state.get("extracted_ingredients") or []
            conflicts = state.get("conflicts") or []
            severity = state.get("conflict_severity", "-")
            error = state.get("error")
            product_name = state.get("product_name", "-")
            source = state.get("source", "photo")

            SEMAPHORE_ICONS = {
                "GRAY": "⬜", "BLUE": "🔵", "YELLOW": "🟡",
                "ORANGE": "🟠", "RED": "🔴",
            }
            icon = SEMAPHORE_ICONS.get(str(semaphore), "?")

            print(f"  {icon} SEMAPHORE: {semaphore}  severity={severity}  source={source}")
            print(f"  Product: {product_name}")
            print(f"  Extracted: {len(extracted)} ingredients  |  Resolved: {len(resolved)}")
            if resolved:
                print(fmt_ingredients(resolved))
            if conflicts:
                print(f"  Conflicts:")
                print(fmt_conflicts(conflicts))
            if error:
                print(f"  ERROR: {error}")
            print()

            summary.append({
                "image": img.name,
                "semaphore": str(semaphore),
                "product_name": product_name,
                "extracted": len(extracted),
                "resolved": len(resolved),
                "severity": str(severity),
                "error": error,
            })

        except Exception as e:
            print(f"  EXCEPTION: {e}\n")
            summary.append({
                "image": img.name,
                "semaphore": "ERROR",
                "product_name": "-",
                "extracted": 0,
                "resolved": 0,
                "severity": "-",
                "error": str(e),
            })
        finally:
            db.close()

        # Respect free-tier RPM limit (10 RPM → 6s between requests minimum)
        if img != images[-1]:
            await asyncio.sleep(8)

    # Final summary table
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"{'Image':<15} {'Semaphore':<10} {'Extracted':>10} {'Resolved':>9} {'Severity':<10} Product")
    print("-" * 80)
    for r in summary:
        err = " [ERR]" if r["error"] else ""
        print(f"{r['image']:<15} {r['semaphore']:<10} {r['extracted']:>10} {r['resolved']:>9} {r['severity']:<10} {r['product_name'][:30]}{err}")

    # Count semaphores
    from collections import Counter
    counts = Counter(r["semaphore"] for r in summary)
    print(f"\nSemaphore distribution: {dict(counts)}")
    errors = [r for r in summary if r["error"]]
    print(f"Errors: {len(errors)}/{len(summary)}")

    # Save JSON report
    report_path = Path(__file__).parent.parent / "test_images_report.json"
    with open(report_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nFull report saved to: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
