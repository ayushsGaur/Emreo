"""
Incident Repository — all database operations for incidents.

The repository pattern means:
  - Routers never write SQL
  - Services never write SQL
  - All DB logic lives here, swappable without touching business logic
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, func

from backend.models.incident import (
    IncidentORM,
    IncidentCreate,
    IncidentStatus,
    SeverityPriority,
)
from backend.core.logging import get_logger

logger = get_logger(__name__)


class IncidentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: IncidentCreate, latitude: float, longitude: float) -> IncidentORM:
        """Persist a new incident. Coordinates must be resolved before calling."""
        incident = IncidentORM(
            caller_name=data.caller_name,
            caller_phone=data.caller_phone,
            address=data.address or f"{latitude:.6f}, {longitude:.6f}",
            latitude=latitude,
            longitude=longitude,
            complaint=data.complaint,
            patient_age=data.patient_age,
            patient_conscious=data.patient_conscious,
            patient_breathing=data.patient_breathing,
            status=IncidentStatus.RECEIVED,
        )
        self.db.add(incident)
        await self.db.flush()  # get the ID without committing yet
        logger.info(f"Incident created | incident_id={str(incident.id)}")
        return incident

    async def get_by_id(self, incident_id: uuid.UUID) -> Optional[IncidentORM]:
        result = await self.db.execute(
            select(IncidentORM).where(IncidentORM.id == incident_id)
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> list[IncidentORM]:
        """All non-closed incidents, newest first."""
        result = await self.db.execute(
            select(IncidentORM)
            .where(IncidentORM.status != IncidentStatus.CLOSED)
            .order_by(desc(IncidentORM.created_at))
        )
        return list(result.scalars().all())

    async def list_by_status(self, status: IncidentStatus) -> list[IncidentORM]:
        result = await self.db.execute(
            select(IncidentORM)
            .where(IncidentORM.status == status)
            .order_by(desc(IncidentORM.created_at))
        )
        return list(result.scalars().all())

    async def update_severity(
        self,
        incident_id: uuid.UUID,
        severity: SeverityPriority,
        confidence: float,
        flagged: bool,
    ) -> None:
        await self.db.execute(
            update(IncidentORM)
            .where(IncidentORM.id == incident_id)
            .values(
                severity=severity,
                severity_confidence=confidence,
                severity_flagged_for_review=flagged,
                updated_at=datetime.now(timezone.utc),
            )
        )

    async def update_dispatch(
        self,
        incident_id: uuid.UUID,
        ambulance_id: uuid.UUID,
        eta_minutes: float,
        route_polyline: Optional[str],
    ) -> None:
        await self.db.execute(
            update(IncidentORM)
            .where(IncidentORM.id == incident_id)
            .values(
                status=IncidentStatus.DISPATCHED,
                assigned_ambulance_id=ambulance_id,
                estimated_arrival_minutes=eta_minutes,
                route_polyline=route_polyline,
                dispatched_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )

    async def update_status(
        self,
        incident_id: uuid.UUID,
        status: IncidentStatus,
        notes: Optional[str] = None,
    ) -> None:
        values: dict = {
            "status": status,
            "updated_at": datetime.now(timezone.utc),
        }
        if notes:
            values["notes"] = notes
        if status == IncidentStatus.ON_SCENE:
            values["arrived_at"] = datetime.now(timezone.utc)
        if status == IncidentStatus.CLOSED:
            values["closed_at"] = datetime.now(timezone.utc)

        await self.db.execute(
            update(IncidentORM).where(IncidentORM.id == incident_id).values(**values)
        )

    async def count_by_severity(self) -> dict[str, int]:
        """Summary counts grouped by severity — used by /metrics endpoint."""
        result = await self.db.execute(
            select(IncidentORM.severity, func.count())
            .where(IncidentORM.severity.isnot(None))
            .group_by(IncidentORM.severity)
        )
        return {row[0]: row[1] for row in result.fetchall()}

    async def average_response_time_minutes(self) -> Optional[float]:
        """Mean time from dispatch to on-scene arrival across closed incidents."""
        result = await self.db.execute(
            select(
                func.avg(
                    func.extract("epoch", IncidentORM.arrived_at - IncidentORM.dispatched_at) / 60
                )
            ).where(
                IncidentORM.arrived_at.isnot(None),
                IncidentORM.dispatched_at.isnot(None),
            )
        )
        val = result.scalar_one_or_none()
        return round(val, 2) if val is not None else None
