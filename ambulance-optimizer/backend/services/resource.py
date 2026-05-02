"""
Resource Allocation Service

Given an incident location and severity, finds the optimal available
ambulance using a weighted scoring algorithm — not just nearest distance.

Scoring factors (weighted):
  1. Distance from incident          (50%) — primary factor
  2. Ambulance type match            (30%) — ALS required for P1/P2
  3. Time since last deployment      (20%) — avoid fatiguing one crew

The result is the ambulance with the HIGHEST score (lowest penalty).
"""

import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.ambulance import AmbulanceORM, AmbulanceStatus
from backend.models.incident import SeverityPriority, AmbulanceType
from backend.repositories.ambulance_repo import AmbulanceRepository, SEVERITY_TO_MIN_TYPE
from backend.services.routing import haversine_km
from backend.core.config import settings
from backend.core.exceptions import NoAmbulanceAvailableError
from backend.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AllocationResult:
    ambulance_id: uuid.UUID
    unit_number: str
    ambulance_type: AmbulanceType
    distance_km: float
    score: float                  # higher = better candidate
    type_matched: bool            # True if type exactly matches severity requirement


class ResourceAllocationService:
    """
    Stateless service — all state lives in the DB and is fetched fresh per dispatch.
    This ensures allocation decisions are always based on current fleet state.
    """

    async def find_best_unit(
        self,
        db: AsyncSession,
        incident_lat: float,
        incident_lng: float,
        severity: SeverityPriority,
    ) -> AllocationResult:
        """
        Find the best available ambulance for this incident.

        Raises NoAmbulanceAvailableError if the fleet has no units ready.
        """
        repo = AmbulanceRepository(db)
        available = await repo.list_available()

        if not available:
            # logger.warning("No ambulances available", severity=severity.value)
            # raise NoAmbulanceAvailableError(
            #     detail=f"No units available for severity {severity.value}"
            # )
            logger.warning(f"No ambulances available | severity={severity.value}")
            raise NoAmbulanceAvailableError(
            detail=f"No units available for severity {severity.value}"
            )

        required_type = SEVERITY_TO_MIN_TYPE[severity]

        # Score every available ambulance
        scored: list[tuple[float, AmbulanceORM]] = []
        for amb in available:
            score = self._score_ambulance(
                amb, incident_lat, incident_lng, required_type
            )
            if score is not None:
                scored.append((score, amb))

        if not scored:
            # All available units are out of range
            raise NoAmbulanceAvailableError(
                detail=f"No units within {settings.MAX_AMBULANCE_SEARCH_RADIUS_KM}km"
            )

        # Pick highest score
        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_amb = scored[0]

        distance = haversine_km(
            incident_lat, incident_lng,
            best_amb.latitude, best_amb.longitude,
        )

        type_matched = (
            AmbulanceType(best_amb.ambulance_type) == required_type
            or AmbulanceType(best_amb.ambulance_type) == AmbulanceType.ALS
        )

        # logger.info(
        #     "Best ambulance selected",
        #     unit=best_amb.unit_number,
        #     distance_km=round(distance, 2),
        #     score=round(best_score, 4),
        #     severity=severity.value,
        #     type_matched=type_matched,
        #     candidates_evaluated=len(available),
        # )

        logger.info(
        f"Best ambulance selected | unit={best_amb.unit_number} | distance_km={round(distance, 2)} | score={round(best_score, 4)} | severity={severity.value} | type_matched={type_matched} | candidates_evaluated={len(available)}"
        )

        return AllocationResult(
            ambulance_id=best_amb.id,
            unit_number=best_amb.unit_number,
            ambulance_type=AmbulanceType(best_amb.ambulance_type),
            distance_km=round(distance, 2),
            score=round(best_score, 4),
            type_matched=type_matched,
        )

    def _score_ambulance(
        self,
        ambulance: AmbulanceORM,
        incident_lat: float,
        incident_lng: float,
        required_type: AmbulanceType,
    ) -> Optional[float]:
        """
        Compute a composite score for one ambulance.
        Returns None if the ambulance is outside the maximum search radius.

        Score is normalized 0–1 (higher = better).
        """
        distance_km = haversine_km(
            incident_lat, incident_lng,
            ambulance.latitude, ambulance.longitude,
        )

        # Hard cutoff — don't dispatch ambulances that are too far
        if distance_km > settings.MAX_AMBULANCE_SEARCH_RADIUS_KM:
            return None

        # ── Distance score (50%) ─────────────────────────────────
        # Normalize: 0km → 1.0, max_radius → 0.0
        distance_score = 1.0 - (distance_km / settings.MAX_AMBULANCE_SEARCH_RADIUS_KM)

        # ── Type match score (30%) ───────────────────────────────


        amb_type = AmbulanceType(ambulance.ambulance_type)
        if amb_type == required_type:
            type_score = 1.0       # exact match
        elif amb_type == AmbulanceType.ALS and required_type == AmbulanceType.BLS:
            type_score = 0.7       # ALS can always handle BLS calls, slight penalty
        else:
            # BLS unit for an ALS-required call — only use as last resort
            type_score = 0.2

        # ── Idle time score (20%) ────────────────────────────────
        # Prefer units that have been idle longer (crew freshness)
        # last_location_update used as proxy for activity recency
       

        # if ambulance.last_location_update:
        #     from datetime import datetime, timezone
        #     idle_seconds = (
        #         datetime.now(timezone.utc) - ambulance.last_location_update
        #     ).total_seconds()
        #     # Cap at 1 hour — beyond that, treat as fully rested
        #     idle_score = min(idle_seconds / 3600, 1.0)
        # else:
        #     idle_score = 1.0  # no update = assume idle
        


        # # Weighted composite
        # score = (
        #     0.50 * distance_score
        #     + 0.30 * type_score
        #     + 0.20 * idle_score
        # )

        # return score
        
        if ambulance.last_location_update:
            from datetime import datetime, timezone

            last_update = ambulance.last_location_update

            # 🔥 FIX: make it timezone-aware if it's naive
            if last_update.tzinfo is None:
                last_update = last_update.replace(tzinfo=timezone.utc)

            idle_seconds = (
                datetime.now(timezone.utc) - last_update
            ).total_seconds()

            # Cap at 1 hour — beyond that, treat as fully rested
            idle_score = min(idle_seconds / 3600, 1.0)
        else:
            idle_score = 1.0  # no update = assume idle


        # ✅ Weighted composite
        score = (
            0.50 * distance_score
            + 0.30 * type_score
            + 0.20 * idle_score
        )

        return score        


# Singleton
resource_service = ResourceAllocationService()
