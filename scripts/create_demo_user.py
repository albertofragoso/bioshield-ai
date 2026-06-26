#!/usr/bin/env python3
"""Create a demo user with fictional biomarkers for portfolio demonstrations.

Creates user demo@bioshield.app with password Demo2026! and pre-loads
fictional biomarker data so the app shows real content on first visit.

Usage (from repo root, with the stack running):
    # Inside the container (via make seed):
    docker compose -f docker-compose.prod.yml exec backend python /app/scripts/create_demo_user.py

    # Or via HTTP if the API is accessible:
    BASE_URL=http://localhost:8000 python scripts/create_demo_user.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

DEMO_EMAIL = "demo@bioshield.app"
DEMO_PASSWORD = "Demo2026!"

# Fictional biomarker values — all within normal ranges, clearly marked as demo data
DEMO_BIOMARKERS = {
    "glucose_mg_dl": 95.0,
    "hba1c_percent": 5.2,
    "total_cholesterol_mg_dl": 182.0,
    "ldl_mg_dl": 108.0,
    "hdl_mg_dl": 58.0,
    "triglycerides_mg_dl": 118.0,
    "creatinine_mg_dl": 0.9,
    "uric_acid_mg_dl": 5.1,
    "note": "DEMO DATA — fictional values for portfolio demonstration only",
}


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # 1. Register demo user
        print(f"Creating demo user: {DEMO_EMAIL}")
        reg = await client.post(
            "/auth/register",
            json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        )

        if reg.status_code == 409:
            print("  → User already exists, skipping registration")
        elif reg.status_code in (200, 201):
            print("  → Registered successfully")
        else:
            print(f"  ✗ Registration failed: {reg.status_code} {reg.text}")
            sys.exit(1)

        # 2. Login to get token
        print("Logging in...")
        login = await client.post(
            "/auth/login",
            json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        )
        if login.status_code != 200:
            print(f"  ✗ Login failed: {login.status_code} {login.text}")
            sys.exit(1)

        token = login.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        print("  → Login successful")

        # 3. Upload fictional biomarkers
        print("Uploading demo biomarkers...")
        biosync = await client.post(
            "/biosync/upload",
            json=DEMO_BIOMARKERS,
            headers=headers,
        )
        if biosync.status_code in (200, 201):
            print("  → Biomarkers uploaded successfully")
        else:
            print(f"  ✗ Biosync failed: {biosync.status_code} {biosync.text}")
            sys.exit(1)

    print(f"\nDemo user ready:")
    print(f"  Email:    {DEMO_EMAIL}")
    print(f"  Password: {DEMO_PASSWORD}")
    print(f"  Note:     All biomarker values are fictional demo data")


if __name__ == "__main__":
    asyncio.run(main())
