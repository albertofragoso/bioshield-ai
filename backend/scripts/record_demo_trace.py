"""Genera fixtures SSE para el demo de la landing page.

Corre scans reales contra el backend local y serializa los eventos
con su timing real a frontend/public/demo/.

Uso:
    cd backend
    # Asegurar que el backend corre en :8000 con una cuenta demo con biomarkers
    python -m scripts.record_demo_trace

Productos preset (barcodes MX comunes):
    7501055300072 — Yogurt Danone Natural
    7501000510010 — Granola Quaker
    7501055316981 — Agua Ciel con gas
"""

import asyncio
import json
import time
from pathlib import Path

import httpx

BACKEND_URL = "http://localhost:8000"
TEST_EMAIL = "demo@bioshield.test"
TEST_PASSWORD = "DemoPass123!"

PRODUCTS = [
    {"barcode": "7501055300072", "label": "yogurt-danone"},
    {"barcode": "7501000510010", "label": "granola-quaker"},
    {"barcode": "7501055316981", "label": "agua-ciel"},
]

OUTPUT_DIR = Path(__file__).parent.parent.parent / "frontend" / "public" / "demo"


async def login(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        f"{BACKEND_URL}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    resp.raise_for_status()


async def record_product(client: httpx.AsyncClient, barcode: str, label: str) -> None:
    print(f"Grabando {label} ({barcode})...")

    events = []
    t_start = time.time()

    async with client.stream("GET", f"{BACKEND_URL}/scan/barcode/{barcode}") as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue

            t_ms = int((time.time() - t_start) * 1000)
            raw = line[5:].strip()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            events.append({"t_ms": t_ms, "type": data.get("type", "unknown"), "data": data})
            print(f"  [{t_ms}ms] {data.get('type', '?')}")

    output = {
        "barcode": barcode,
        "product_name": label,
        "events": events,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"scan-trace-{barcode}.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"  Guardado: {output_path} ({len(events)} eventos)")


async def main() -> None:
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        await login(client)
        for product in PRODUCTS:
            await record_product(client, product["barcode"], product["label"])


if __name__ == "__main__":
    asyncio.run(main())
