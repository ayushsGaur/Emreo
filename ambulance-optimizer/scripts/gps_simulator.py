"""
GPS Simulator

Simulates ambulance GPS devices pushing location updates via WebSocket.
Run this alongside the backend to see ambulances moving on the map.

Each simulated ambulance:
  - Starts at its registered station location
  - Moves toward any assigned incident
  - Wanders randomly when available
  - Respects road-like movement (smooth curves, realistic speed)

Usage:
    # Simulate all registered ambulances
    python scripts/gps_simulator.py

    # Simulate with faster updates (for demo)
    python scripts/gps_simulator.py --interval 2
"""

import asyncio
import json
import math
import random
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import websockets

API_BASE = "http://localhost:8000/api/v1"
WS_BASE  = "ws://localhost:8000/api/v1"

# Ludhiana bounding box — ambulances wander within this
BOUNDS = {
    "lat_min": 30.78, "lat_max": 30.96,
    "lng_min": 75.77, "lng_max": 75.95,
}

# Station home positions (fallback if no registered location)
DEFAULT_STATIONS = [
    {"unit_number": "AMB-01", "lat": 30.9010, "lng": 75.8573},  # Central
    {"unit_number": "AMB-02", "lat": 30.9200, "lng": 75.8400},  # North
    {"unit_number": "AMB-03", "lat": 30.8800, "lng": 75.8700},  # South
]


class AmbulanceSimulator:
    def __init__(self, ambulance: dict, interval: float):
        self.id          = ambulance["id"]
        self.unit        = ambulance["unit_number"]
        self.status      = ambulance["status"]
        self.lat         = ambulance.get("latitude") or self._default_lat()
        self.lng         = ambulance.get("longitude") or self._default_lng()
        self.heading     = random.uniform(0, 360)
        self.speed       = 0.0
        self.interval    = interval
        self.target_lat  = None
        self.target_lng  = None
        self.step        = 0

    def _default_lat(self):
        return random.uniform(BOUNDS["lat_min"], BOUNDS["lat_max"])

    def _default_lng(self):
        return random.uniform(BOUNDS["lng_min"], BOUNDS["lng_max"])

    def _move(self):
        """Compute next position — smooth realistic movement."""
        if self.target_lat and self.target_lng:
            # Move toward target
            dlat = self.target_lat - self.lat
            dlng = self.target_lng - self.lng
            dist = math.sqrt(dlat**2 + dlng**2)

            if dist < 0.0005:  # arrived
                self.target_lat = self.target_lng = None
                self.speed = random.uniform(0, 5)
            else:
                step = min(dist, 0.0008)  # ~90m per step
                self.lat     += (dlat / dist) * step * random.uniform(0.8, 1.2)
                self.lng     += (dlng / dist) * step * random.uniform(0.8, 1.2)
                self.heading  = math.degrees(math.atan2(dlng, dlat)) % 360
                self.speed    = random.uniform(40, 80)  # km/h en route
        else:
            # Random wander — pick new target occasionally
            if self.step % 20 == 0 or not self.target_lat:
                self.target_lat = random.uniform(BOUNDS["lat_min"], BOUNDS["lat_max"])
                self.target_lng = random.uniform(BOUNDS["lng_min"], BOUNDS["lng_max"])
            self.speed = random.uniform(0, 15)

        # Clamp to bounds
        self.lat = max(BOUNDS["lat_min"], min(BOUNDS["lat_max"], self.lat))
        self.lng = max(BOUNDS["lng_min"], min(BOUNDS["lng_max"], self.lng))
        self.step += 1

    def payload(self) -> dict:
        self._move()
        return {
            "event": "location",
            "data": {
                "ambulance_id":  self.id,
                "latitude":      round(self.lat, 6),
                "longitude":     round(self.lng, 6),
                "heading_degrees": round(self.heading, 1),
                "speed_kmh":     round(self.speed, 1),
                "status":        self.status,
                "timestamp":     datetime.now(timezone.utc).isoformat(),
            }
        }


async def simulate_ambulance(ambulance: dict, interval: float):
    """Connect one ambulance to its WebSocket and push GPS updates."""
    sim = AmbulanceSimulator(ambulance, interval)
    uri = f"{WS_BASE}/ws/ambulance/{ambulance['id']}"

    while True:
        try:
            async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as ws:
                print(f"[{sim.unit}] Connected → {uri}")
                while True:
                    payload = sim.payload()
                    await ws.send(json.dumps(payload))
                    await asyncio.sleep(interval)
        except (websockets.ConnectionClosed, ConnectionRefusedError, OSError) as e:
            print(f"[{sim.unit}] Disconnected ({e}), retrying in 3s…")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"[{sim.unit}] Error: {e}, retrying in 5s…")
            await asyncio.sleep(5)


async def fetch_ambulances() -> list[dict]:
    """Fetch registered ambulances from the backend."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/ambulances", timeout=5.0)
            resp.raise_for_status()
            ambulances = resp.json()
            if not ambulances:
                print("No ambulances registered. Register some first:")
                print(f"  curl -X POST {API_BASE}/ambulances -H 'Content-Type: application/json' \\")
                print("    -d '{\"unit_number\":\"AMB-01\",\"station_name\":\"Central\",\"ambulance_type\":\"ALS\"}'")
                sys.exit(1)
            return ambulances
    except httpx.ConnectError:
        print(f"Cannot connect to backend at {API_BASE}")
        print("Make sure the FastAPI server is running: uvicorn main:app --reload")
        sys.exit(1)


async def main(interval: float):
    print(f"GPS Simulator starting (update interval: {interval}s)")
    print(f"Backend: {API_BASE}")
    print()

    ambulances = await fetch_ambulances()
    print(f"Found {len(ambulances)} ambulance(s): {[a['unit_number'] for a in ambulances]}")
    print("Simulating GPS updates… (Ctrl+C to stop)\n")

    # Run all simulators concurrently
    await asyncio.gather(*[
        simulate_ambulance(amb, interval + random.uniform(-0.5, 0.5))
        for amb in ambulances
    ])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ambulance GPS simulator")
    parser.add_argument("--interval", type=float, default=4.0, help="Update interval in seconds (default: 4)")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.interval))
    except KeyboardInterrupt:
        print("\nSimulator stopped.")
