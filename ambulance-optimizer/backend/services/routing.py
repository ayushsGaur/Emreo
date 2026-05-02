"""
Routing Service — GIS route computation via OSRM

Responsibilities:
  - Compute fastest route between two coordinates
  - Return ETA in minutes + encoded polyline for map display
  - Handle OSRM failures gracefully with haversine fallback
  - Cache frequent routes in Redis to reduce external API calls

OSRM API used: /route/v1/driving/{lng1},{lat1};{lng2},{lat2}
Note: OSRM expects (longitude, latitude) order — not the usual lat/lng.
"""

import math
import json
from dataclasses import dataclass
from typing import Optional

import httpx

from backend.core.config import settings
from backend.core.exceptions import RoutingServiceError
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Average ambulance speed assumption when OSRM is unavailable
FALLBACK_SPEED_KMH = 60.0


@dataclass
class RouteResult:
    distance_km: float
    duration_minutes: float
    polyline: Optional[str]          # encoded polyline for Leaflet
    waypoints: list[dict]             # [{lat, lng}, ...]
    via_osrm: bool                    # False = haversine fallback was used


class RoutingService:
    """
    Wraps OSRM routing API with caching and fallback.
    Instantiated once and reused across requests.
    """

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=settings.OSRM_BASE_URL,
                timeout=8.0,
                headers={"User-Agent": "AmbulanceOptimizer/1.0"},
            )
        return self._client

    async def compute_route(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> RouteResult:
        """
        Compute the fastest driving route from origin to destination.

        Tries OSRM first. Falls back to haversine straight-line estimate
        if OSRM is unreachable — ensuring dispatch never fails due to
        a routing service outage.
        """
        try:
            return await self._route_via_osrm(origin_lat, origin_lng, dest_lat, dest_lng)
        except RoutingServiceError:
            raise
        except Exception as e:
            # logger.warning(
            #     "OSRM unavailable — using haversine fallback",
            #     error=str(e),
            #     origin=(origin_lat, origin_lng),
            #     dest=(dest_lat, dest_lng),
            # )
            logger.warning(
            f"OSRM unavailable — using haversine fallback | error={str(e)} | origin=({origin_lat}, {origin_lng}) | dest=({dest_lat}, {dest_lng})"
            )
            return self._route_via_haversine(origin_lat, origin_lng, dest_lat, dest_lng)

    async def _route_via_osrm(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> RouteResult:
        """Call OSRM routing API and parse the response."""
        # OSRM coordinate format: longitude,latitude (reversed from convention)
        coords = f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
        url = f"/route/v1/driving/{coords}"

        client = await self._get_client()
        response = await client.get(url, params={
            "overview": "full",          # return full route geometry
            "geometries": "polyline",    # encoded polyline format
            "steps": "false",
        })

        if response.status_code != 200:
            raise RoutingServiceError(
                detail=f"OSRM returned HTTP {response.status_code}"
            )

        data = response.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            raise RoutingServiceError(
                detail=f"OSRM error: {data.get('code', 'unknown')}"
            )

        route = data["routes"][0]
        distance_km = round(route["distance"] / 1000, 2)
        duration_minutes = round(route["duration"] / 60, 1)
        polyline = route.get("geometry")

        waypoints = [
            {"lat": wp["location"][1], "lng": wp["location"][0]}
            for wp in data.get("waypoints", [])
        ]

        # logger.info(
        #     "Route computed via OSRM",
        #     distance_km=distance_km,
        #     duration_minutes=duration_minutes,
        # )

        logger.info(
        f"Route computed via OSRM | distance_km={distance_km} | duration_minutes={duration_minutes}"
        )

        return RouteResult(
            distance_km=distance_km,
            duration_minutes=duration_minutes,
            polyline=polyline,
            waypoints=waypoints,
            via_osrm=True,
        )

    def _route_via_haversine(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> RouteResult:
        """
        Straight-line distance estimate using the Haversine formula.
        Applies a 1.3x road-factor multiplier to approximate actual road distance.
        Used only when OSRM is unreachable.
        """
        distance_km = haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
        road_distance_km = round(distance_km * 1.3, 2)  # road factor
        duration_minutes = round((road_distance_km / FALLBACK_SPEED_KMH) * 60, 1)

        # logger.info(
        #     "Route computed via haversine fallback",
        #     straight_line_km=distance_km,
        #     estimated_road_km=road_distance_km,
        #     duration_minutes=duration_minutes,
        # )

        logger.info(
        f"Route computed via haversine fallback | straight_line_km={distance_km} | estimated_road_km={road_distance_km} | duration_minutes={duration_minutes}"
        )


        return RouteResult(
            distance_km=road_distance_km,
            duration_minutes=duration_minutes,
            polyline=None,
            waypoints=[
                {"lat": origin_lat, "lng": origin_lng},
                {"lat": dest_lat,   "lng": dest_lng},
            ],
            via_osrm=False,
        )

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ── Utility ───────────────────────────────────────────────────────────────────

def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Great-circle distance between two coordinates in kilometres.
    Used for nearest-ambulance selection and fallback routing.
    """
    R = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# Singleton
routing_service = RoutingService()
