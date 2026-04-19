"""
Phase 1: Test only Gemini Vision OCR on all 13 test images.
Avoids reconciler/embedding calls — just validates OCR accuracy.
Usage: cd backend && python -m scripts.test_photo_ocr_only
"""

import asyncio
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import Settings
from app.services.gemini import extract_from_image

IMAGES_DIR = Path(__file__).parent.parent / "test_images"
DELAY_BETWEEN = 12  # seconds — conservative for free-tier RPM


async def main():
    settings = Settings(_env_file=str(Path(__file__).parent.parent / ".env"))
    images = sorted(IMAGES_DIR.glob("*.jpeg")) + sorted(IMAGES_DIR.glob("*.jpg")) + sorted(IMAGES_DIR.glob("*.png"))

    print(f"\n{'='*60}")
    print(f"BioShield Gemini Vision OCR — {len(images)} images")
    print(f"Model: {settings.gemini_model}  |  delay: {DELAY_BETWEEN}s")
    print(f"{'='*60}\n")

    results = []

    for i, img in enumerate(images):
        print(f"[{i+1}/{len(images)}] {img.name} ...", flush=True)
        with open(img, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        for attempt in range(3):
            try:
                extraction = await extract_from_image(b64, settings)
                n = len(extraction.ingredients)
                lang = extraction.language
                additives = extraction.has_additives
                preview = extraction.ingredients[:5]
                print(f"  ✓ {n} ingredientes  lang={lang}  additives={additives}")
                for ing in preview:
                    print(f"    - {ing}")
                if n > 5:
                    print(f"    ... +{n-5} más")
                print()
                results.append({
                    "image": img.name,
                    "ok": True,
                    "count": n,
                    "language": lang,
                    "has_additives": additives,
                    "ingredients": extraction.ingredients,
                    "error": None,
                })
                break
            except Exception as e:
                msg = str(e)
                if "429" in msg and attempt < 2:
                    wait = 65
                    print(f"  ⏳ Rate limited, waiting {wait}s (attempt {attempt+1}/3)...", flush=True)
                    await asyncio.sleep(wait)
                else:
                    print(f"  ✗ ERROR: {msg[:120]}\n")
                    results.append({
                        "image": img.name,
                        "ok": False,
                        "count": 0,
                        "language": None,
                        "has_additives": None,
                        "ingredients": [],
                        "error": msg[:200],
                    })
                    break

        if i < len(images) - 1:
            print(f"  [waiting {DELAY_BETWEEN}s...]\n", flush=True)
            await asyncio.sleep(DELAY_BETWEEN)

    # Summary
    ok = [r for r in results if r["ok"]]
    fail = [r for r in results if not r["ok"]]
    total_ing = sum(r["count"] for r in ok)

    print(f"\n{'='*60}")
    print("RESUMEN OCR")
    print(f"{'='*60}")
    print(f"{'Imagen':<15} {'OK':>4} {'#Ing':>6} {'Lang':<6} {'Additives'}")
    print("-" * 50)
    for r in results:
        status = "✓" if r["ok"] else "✗"
        print(f"{r['image']:<15} {status:>4} {r['count']:>6}   {str(r['language']):<6} {r['has_additives']}")

    print(f"\nTotal: {len(ok)}/{len(results)} OK | {total_ing} ingredientes extraídos | {len(fail)} errores")
    if fail:
        print("Errores:")
        for r in fail:
            print(f"  {r['image']}: {r['error']}")

    out = Path(__file__).parent.parent / "test_ocr_report.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nReporte guardado: {out}")


if __name__ == "__main__":
    asyncio.run(main())
