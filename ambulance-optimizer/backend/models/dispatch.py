from sqlalchemy import Column, ForeignKey, DateTime, Float
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
from sqlalchemy.orm import relationship
import uuid

from backend.core.database import Base


class DispatchORM(Base):
    __tablename__ = "dispatches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)
    ambulance_id = Column(UUID(as_uuid=True), ForeignKey("ambulances.id"), nullable=False)

    eta_minutes = Column(Float, nullable=True)

    assigned_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))

    
    incident = relationship("IncidentORM", back_populates="dispatch")
    ambulance = relationship("AmbulanceORM", back_populates="dispatches")