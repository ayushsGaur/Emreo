"""
Seed Script

Populates the database with realistic ambulances and sample incidents
so the dashboard is immediately usable for demo / development.

Usage:
    python scripts/seed.py               # seed everything
    python scripts/seed.py --ambulances  # only ambulances
    python scripts/seed.py --incidents   # only incidents
    python scripts/seed.py --wipe        # wipe + reseed
"""

import asyncio
import argparse
import random
import httpx

API = "http://localhost:8000/api/v1"

AMBULANCES = [
    {"unit_number": "AMB-06", "station_name": "Central Station",    "ambulance_type": "ALS"},
    {"unit_number": "AMB-07", "station_name": "North Station",      "ambulance_type": "BLS"},
    {"unit_number": "AMB-08", "station_name": "South Station",      "ambulance_type": "ALS"},
    {"unit_number": "AMB-09", "station_name": "East Station",       "ambulance_type": "BLS"},
    {"unit_number": "AMB-10", "station_name": "Civil Hospital Base", "ambulance_type": "ALS"},
]

SAMPLE_INCIDENTS = [
    {
        "caller_name": "Rajinder Singh",
        "caller_phone": "9876543210",
        "complaint": "Patient unresponsive, not breathing. Possible cardiac arrest.",
        "address": "Ferozepur Road, near Sarabha Nagar, Ludhiana",
        "latitude": 30.8953, "longitude": 75.8575,
        "patient_age": 62, "patient_conscious": False, "patient_breathing": False,
    },
    {
        "caller_name": "Priya Sharma",
        "caller_phone": "9876501234",
        "complaint": "Severe chest pain radiating to left arm. Patient sweating heavily.",
        "address": "Model Town, Ludhiana",
        "latitude": 30.9200, "longitude": 75.8400,
        "patient_age": 55, "patient_conscious": True, "patient_breathing": True,
    },
    {
        "caller_name": "Gurpreet Kaur",
        "caller_phone": "9812345678",
        "complaint": "Road accident near bus stand. Patient has fractured leg, conscious.",
        "address": "Ghumar Mandi, near Bus Stand, Ludhiana",
        "latitude": 30.9010, "longitude": 75.8650,
        "patient_age": 28, "patient_conscious": True, "patient_breathing": True,
    },
    {
        "caller_name": "Harman Dhaliwal",
        "caller_phone": "9988776655",
        "complaint": "Elderly woman fell at home. Possible hip fracture, in pain.",
        "address": "Dugri, Phase 2, Ludhiana",
        "latitude": 30.8800, "longitude": 75.8450,
        "patient_age": 74, "patient_conscious": True, "patient_breathing": True,
    },
    {
        "caller_name": "Amandeep Brar",
        "caller_phone": "7814567890",
        "complaint": "Child having seizure, lasted more than 5 minutes.",
        "address": "BRS Nagar, Ludhiana",
        "latitude": 30.9100, "longitude": 75.8200,
        "patient_age": 8, "patient_conscious": False, "patient_breathing": True,
    },
]


async def seed_ambulances(client: httpx.AsyncClient) -> list[dict]:
    print("\n── Ambulances ──────────────────────────────────────")
    results = []
    for amb in AMBULANCES:
        try:
            r = await client.post(f"{API}/ambulances", json=amb)
            if r.status_code == 201:
                data = r.json()
                print(f"  ✓ {data['unit_number']} ({data['ambulance_type']}) — {data['station_name']}")
                results.append(data)
            elif r.status_code == 409:
                print(f"  · {amb['unit_number']} already exists — skipped")
            else:
                print(f"  ✗ {amb['unit_number']}: {r.status_code} {r.text[:80]}")
        except Exception as e:
            print(f"  ✗ {amb['unit_number']}: {e}")
    return results


async def seed_incidents(client: httpx.AsyncClient) -> list[dict]:
    print("\n── Incidents ───────────────────────────────────────")
    results = []
    for inc in SAMPLE_INCIDENTS:
        try:
            r = await client.post(f"{API}/incidents", json=inc)
            if r.status_code == 201:
                data = r.json()
                sev = data.get("severity", "?")
                print(f"  ✓ {sev} — {inc['complaint'][:60]}…")
                results.append(data)
            else:
                print(f"  ✗ Incident failed: {r.status_code} {r.text[:80]}")
        except Exception as e:
            print(f"  ✗ Incident error: {e}")
    return results


async def main(ambulances_only: bool, incidents_only: bool):
    print("Ambulance Optimizer — Seed Script")
    print(f"API: {API}")

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Health check first
        try:
            r = await client.get(API.replace("/api/v1", "/health"))
            health = r.json()
            db_ok = health.get("dependencies", {}).get("database") == "ok"
            print(f"\nBackend: {'✓ healthy' if db_ok else '✗ DB not ready — run migrations first'}")
            if not db_ok:
                return
        except Exception:
            print("\nCannot reach backend. Is the server running?")
            print("  cd backend && uvicorn main:app --reload")
            return

        if not incidents_only:
            await seed_ambulances(client)

        if not ambulances_only:
            await seed_incidents(client)

    print("\nSeed complete. Open http://localhost:3000 to see the dashboard.")
    print("Run the GPS simulator to see ambulances move:")
    print("  python scripts/gps_simulator.py")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--ambulances", action="store_true")
    p.add_argument("--incidents",  action="store_true")
    args = p.parse_args()
    asyncio.run(main(args.ambulances, args.incidents))
