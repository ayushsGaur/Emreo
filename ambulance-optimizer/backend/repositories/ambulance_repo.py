"""
Ambulance Repository — all database operations for ambulances.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.models.ambulance import AmbulanceORM, AmbulanceStatus, AmbulanceCreate
from backend.models.incident import AmbulanceType, SeverityPriority
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Map severity to minimum required ambulance type
# P1/P2 need ALS (Advanced Life Support), P3/P4 can use BLS
SEVERITY_TO_MIN_TYPE: dict[SeverityPriority, AmbulanceType] = {
    SeverityPriority.P1_CRITICAL:   AmbulanceType.ALS,
    SeverityPriority.P2_EMERGENT:   AmbulanceType.ALS,
    SeverityPriority.P3_URGENT:     AmbulanceType.BLS,
    SeverityPriority.P4_NON_URGENT: AmbulanceType.BLS,
}


class AmbulanceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: AmbulanceCreate) -> AmbulanceORM:
        ambulance = AmbulanceORM(
            unit_number=data.unit_number,
            station_name=data.station_name,
            ambulance_type=data.ambulance_type,
        )
        self.db.add(ambulance)
        await self.db.flush()
        # logger.info("Ambulance registered", unit_number=data.unit_number)
        logger.info(f"Ambulance registered | unit_number={data.unit_number}")
        return ambulance

    async def get_by_id(self, ambulance_id: uuid.UUID) -> Optional[AmbulanceORM]:
        result = await self.db.execute(
            select(AmbulanceORM).where(AmbulanceORM.id == ambulance_id)
        )
        return result.scalar_one_or_none()

    async def get_by_unit_number(self, unit_number: str) -> Optional[AmbulanceORM]:
        result = await self.db.execute(
            select(AmbulanceORM).where(AmbulanceORM.unit_number == unit_number)
        )
        return result.scalar_one_or_none()

    async def list_all_active(self) -> list[AmbulanceORM]:
        result = await self.db.execute(
            select(AmbulanceORM).where(AmbulanceORM.is_active == True)
        )
        return list(result.scalars().all())

    async def list_available(self) -> list[AmbulanceORM]:
        """All active ambulances currently available for dispatch."""
        result = await self.db.execute(
            select(AmbulanceORM).where(
                AmbulanceORM.is_active == True,
                AmbulanceORM.status == AmbulanceStatus.AVAILABLE,
                AmbulanceORM.latitude.isnot(None),
                AmbulanceORM.longitude.isnot(None),
            )
        )
        return list(result.scalars().all())

    async def update_location(
        self,
        ambulance_id: uuid.UUID,
        latitude: float,
        longitude: float,
        heading: Optional[float] = None,
        speed_kmh: Optional[float] = None,
        status: Optional[AmbulanceStatus] = None,
    ) -> None:
        values: dict = {
            "latitude": latitude,
            "longitude": longitude,
            "last_location_update": datetime.now(timezone.utc),
        }
        if heading is not None:
            values["heading_degrees"] = heading
        if speed_kmh is not None:
            values["speed_kmh"] = speed_kmh
        if status is not None:
            values["status"] = status

        await self.db.execute(
            update(AmbulanceORM)
            .where(AmbulanceORM.id == ambulance_id)
            .values(**values)
        )

    async def update_status(
        self,
        ambulance_id: uuid.UUID,
        status: AmbulanceStatus,
        incident_id: Optional[uuid.UUID] = None,
    ) -> None:
        values: dict = {"status": status}
        if status == AmbulanceStatus.AVAILABLE:
            values["current_incident_id"] = None
        elif incident_id is not None:
            values["current_incident_id"] = incident_id

        await self.db.execute(
            update(AmbulanceORM)
            .where(AmbulanceORM.id == ambulance_id)
            .values(**values)
        )

    async def count_by_status(self) -> dict[str, int]:
        """Fleet status summary for the dashboard."""
        ambulances = await self.list_all_active()
        counts: dict[str, int] = {}
        for amb in ambulances:
            key = amb.status if isinstance(amb.status, str) else amb.status.value
            counts[key] = counts.get(key, 0) + 1
        return counts
