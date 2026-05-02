"""
Ambulance models — DB table and API schemas.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import String, Float, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column , relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy import Enum as SAEnum
from pydantic import BaseModel, Field

from backend.core.database import Base
from backend.models.incident import AmbulanceType


# ── Enums ──────────────────────────────────────────────────────────────────────

class AmbulanceStatus(str, Enum):
    AVAILABLE    = "available"    # Ready to be dispatched
    DISPATCHED   = "dispatched"   # En route to incident
    ON_SCENE     = "on_scene"     # At the incident location
    TRANSPORTING = "transporting" # Moving patient to hospital
    AT_HOSPITAL  = "at_hospital"  # Transferring patient
    OFFLINE      = "offline"      # Out of service / maintenance


# ── ORM Model ─────────────────────────────────────────────────────────────────

class AmbulanceORM(Base):
    __tablename__ = "ambulances"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Identity
    unit_number:  Mapped[str]  = mapped_column(String(20), unique=True)  # e.g. "AMB-04"
    station_name: Mapped[str]  = mapped_column(String(100))
    ambulance_type: Mapped[str] = mapped_column(SAEnum(AmbulanceType))

    # Status
    status: Mapped[str] = mapped_column(
        SAEnum(AmbulanceStatus), default=AmbulanceStatus.AVAILABLE
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Live location (updated via WebSocket)
    latitude:  Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_location_update: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    heading_degrees: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    speed_kmh:       Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Current assignment
    current_incident_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )

    #addedbackend.
    dispatches = relationship("DispatchORM", back_populates="ambulance")


# ── Pydantic Schemas ───────────────────────────────────────────────────────────

class AmbulanceCreate(BaseModel):
    unit_number:    str = Field(..., min_length=2, max_length=20, pattern=r"^AMB-\d+$")
    station_name:   str = Field(..., min_length=2, max_length=100)
    ambulance_type: AmbulanceType


class AmbulanceResponse(BaseModel):
    id:             uuid.UUID
    unit_number:    str
    station_name:   str
    ambulance_type: AmbulanceType
    status:         AmbulanceStatus
    is_active:      bool
    latitude:       Optional[float]
    longitude:      Optional[float]
    last_location_update: Optional[datetime]
    heading_degrees: Optional[float]
    speed_kmh:       Optional[float]
    current_incident_id: Optional[uuid.UUID]

    model_config = {"from_attributes": True}


class AmbulanceLocationUpdate(BaseModel):
    """Payload pushed by ambulance device via WebSocket."""
    ambulance_id:    uuid.UUID
    latitude:        float = Field(..., ge=-90.0,  le=90.0)
    longitude:       float = Field(..., ge=-180.0, le=180.0)
    heading_degrees: Optional[float] = Field(None, ge=0.0, le=360.0)
    speed_kmh:       Optional[float] = Field(None, ge=0.0, le=200.0)
    status:          Optional[AmbulanceStatus] = None
    timestamp:       datetime


class AmbulanceStatusUpdate(BaseModel):
    status: AmbulanceStatus
    current_incident_id: Optional[uuid.UUID] = None

