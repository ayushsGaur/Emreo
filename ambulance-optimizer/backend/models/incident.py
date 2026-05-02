"""
Incident models — both the DB table (SQLAlchemy) and the API schemas (Pydantic).

Two separate model families, deliberately:
  - ORM models (IncidentORM)  → talk to the database
  - Pydantic schemas          → validate API input/output

They never mix. The repository layer translates between them.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import String, Float, Integer, DateTime, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from pydantic import BaseModel, Field, field_validator, model_validator
from backend.models.dispatch import DispatchORM
import re

from backend.core.database import Base


# ── Enums ──────────────────────────────────────────────────────────────────────

class SeverityPriority(str, Enum):
    P1_CRITICAL   = "P1"   # Life-threatening — cardiac arrest, major trauma
    P2_EMERGENT   = "P2"   # Serious — breathing difficulty, altered consciousness
    P3_URGENT     = "P3"   # Urgent but stable — fractures, moderate pain
    P4_NON_URGENT = "P4"   # Non-urgent — minor injuries, transfers


class IncidentStatus(str, Enum):
    RECEIVED    = "received"     # Logged, not yet dispatched
    DISPATCHING = "dispatching"  # Dispatcher running allocation + routing
    DISPATCHED  = "dispatched"   # Ambulance assigned and en route
    ON_SCENE    = "on_scene"     # Ambulance arrived
    TRANSPORTING = "transporting"# Patient in ambulance, en route to hospital
    CLOSED      = "closed"       # Incident resolved


class AmbulanceType(str, Enum):
    ALS = "ALS"   # Advanced Life Support — paramedic + advanced equipment
    BLS = "BLS"   # Basic Life Support    — EMT + basic equipment


# ── ORM Models ────────────────────────────────────────────────────────────────

class IncidentORM(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Caller information
    caller_name: Mapped[str]       = mapped_column(String(120))
    caller_phone: Mapped[str]      = mapped_column(String(20))

    # Location
    address: Mapped[str]           = mapped_column(String(300))
    latitude: Mapped[float]        = mapped_column(Float)
    longitude: Mapped[float]       = mapped_column(Float)

    # Clinical
    complaint: Mapped[str]         = mapped_column(Text)
    patient_age: Mapped[Optional[int]]   = mapped_column(Integer, nullable=True)
    patient_conscious: Mapped[Optional[bool]] = mapped_column(nullable=True)
    patient_breathing: Mapped[Optional[bool]] = mapped_column(nullable=True)

    # AI outputs
    severity: Mapped[Optional[str]] = mapped_column(
        SAEnum(SeverityPriority), nullable=True
    )
    severity_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    severity_flagged_for_review: Mapped[bool]    = mapped_column(default=False)

    # Dispatch
    status: Mapped[str]            = mapped_column(
        SAEnum(IncidentStatus), default=IncidentStatus.RECEIVED
    )
    assigned_ambulance_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
      #added
    dispatch = relationship("DispatchORM", back_populates="incident", uselist=False)
    dispatched_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    estimated_arrival_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    route_polyline: Mapped[Optional[str]]              = mapped_column(Text, nullable=True)

    # Resolution
    arrived_at: Mapped[Optional[datetime]]  = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]]   = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]]            = mapped_column(Text, nullable=True)


# ── Pydantic Schemas ───────────────────────────────────────────────────────────

class LocationSchema(BaseModel):
    """Reusable geographic coordinate pair with validation."""
    latitude: float  = Field(..., ge=-90.0,  le=90.0,  description="WGS-84 latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS-84 longitude")


class IncidentCreate(BaseModel):
    """
    Schema for POST /incidents — what the caller/form submits.
    Address OR coordinates must be provided.
    """
    caller_name:  str = Field(..., min_length=2, max_length=120)
    caller_phone: str = Field(..., description="Phone in E.164 or local format")
    complaint:    str = Field(..., min_length=5, max_length=1000)

    # Location — one of these must be present
    address:   Optional[str]   = Field(None, max_length=300)
    latitude:  Optional[float] = Field(None, ge=-90.0,  le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)

    # Optional clinical context (helps severity model)
    patient_age:        Optional[int]  = Field(None, ge=0, le=130)
    patient_conscious:  Optional[bool] = None
    patient_breathing:  Optional[bool] = None

    @field_validator("caller_phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = re.sub(r"[\s\-\(\)]", "", v)
        if not re.match(r"^\+?[\d]{7,15}$", cleaned):
            raise ValueError("Invalid phone number format")
        return cleaned

    @model_validator(mode="after")
    def location_required(self) -> "IncidentCreate":
        has_coords  = self.latitude is not None and self.longitude is not None
        has_address = self.address is not None and len(self.address.strip()) > 0
        if not has_coords and not has_address:
            raise ValueError("Either address or (latitude + longitude) must be provided")
        return self


class IncidentResponse(BaseModel):
    """Schema for all incident responses from the API."""
    id:                 uuid.UUID
    created_at:         datetime
    updated_at:         datetime
    caller_name:        str
    caller_phone:       str
    address:            str
    latitude:           float
    longitude:          float
    complaint:          str
    patient_age:        Optional[int]
    patient_conscious:  Optional[bool]
    patient_breathing:  Optional[bool]
    severity:           Optional[SeverityPriority]
    severity_confidence: Optional[float]
    severity_flagged_for_review: bool
    status:             IncidentStatus
    assigned_ambulance_id: Optional[uuid.UUID]
    estimated_arrival_minutes: Optional[float]
    dispatched_at:      Optional[datetime]
    arrived_at:         Optional[datetime]
    closed_at:          Optional[datetime]

    model_config = {"from_attributes": True}  # allows ORM → Pydantic conversion


class IncidentStatusUpdate(BaseModel):
    """Schema for PATCH /incidents/{id}/status"""
    status: IncidentStatus
    notes:  Optional[str] = Field(None, max_length=1000)


class DispatchResult(BaseModel):
    """What the dispatcher returns after a successful dispatch."""
    incident_id:                uuid.UUID
    assigned_ambulance_id:      uuid.UUID
    ambulance_type:             AmbulanceType
    severity:                   SeverityPriority
    severity_confidence:        float
    estimated_arrival_minutes:  float
    route_polyline:             Optional[str]
    dispatch_timestamp:         datetime
    flagged_for_review:         bool

  
