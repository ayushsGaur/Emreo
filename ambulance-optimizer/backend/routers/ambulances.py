"""
Ambulances Router

Routes:
  POST  /api/v1/ambulances              — register a new ambulance unit
  GET   /api/v1/ambulances              — list all active units with live status
  GET   /api/v1/ambulances/{id}         — get a specific unit
  PATCH /api/v1/ambulances/{id}/status  — manually update unit status
"""

import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.exceptions import AmbulanceNotFoundError
from backend.models.ambulance import (
    AmbulanceCreate, AmbulanceResponse, AmbulanceStatusUpdate
)
from backend.repositories.ambulance_repo import AmbulanceRepository
from backend.services.websocket_manager import connection_manager
from backend.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post(
    "/ambulances",
    response_model=AmbulanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new ambulance unit",
)
async def register_ambulance(
    data: AmbulanceCreate,
    db: AsyncSession = Depends(get_db),
):
    repo = AmbulanceRepository(db)
    ambulance = await repo.create(data)
    return AmbulanceResponse.model_validate(ambulance)


@router.get(
    "/ambulances",
    response_model=list[AmbulanceResponse],
    summary="List all active ambulance units",
)
async def list_ambulances(db: AsyncSession = Depends(get_db)):
    repo = AmbulanceRepository(db)
    ambulances = await repo.list_all_active()
    return [AmbulanceResponse.model_validate(a) for a in ambulances]


@router.get(
    "/ambulances/available",
    response_model=list[AmbulanceResponse],
    summary="List only available ambulances",
)
async def list_available_ambulances(db: AsyncSession = Depends(get_db)):
    repo = AmbulanceRepository(db)
    ambulances = await repo.list_available()
    return [AmbulanceResponse.model_validate(a) for a in ambulances]


@router.get(
    "/ambulances/{ambulance_id}",
    response_model=AmbulanceResponse,
    summary="Get a specific ambulance unit",
)
async def get_ambulance(
    ambulance_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    repo = AmbulanceRepository(db)
    ambulance = await repo.get_by_id(ambulance_id)
    if not ambulance:
        raise AmbulanceNotFoundError()
    return AmbulanceResponse.model_validate(ambulance)


@router.patch(
    "/ambulances/{ambulance_id}/status",
    response_model=AmbulanceResponse,
    summary="Manually update an ambulance's operational status",
)
async def update_ambulance_status(
    ambulance_id: uuid.UUID,
    data: AmbulanceStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    repo = AmbulanceRepository(db)
    ambulance = await repo.get_by_id(ambulance_id)
    if not ambulance:
        raise AmbulanceNotFoundError()

    await repo.update_status(
        ambulance_id=ambulance_id,
        status=data.status,
        incident_id=data.current_incident_id,
    )

    # Notify dashboards of fleet change
    await connection_manager.broadcast_to_dashboards("ambulance.status_changed", {
        "ambulance_id": str(ambulance_id),
        "unit_number": ambulance.unit_number,
        "new_status": data.status.value,
    })

    ambulance = await repo.get_by_id(ambulance_id)
    return AmbulanceResponse.model_validate(ambulance)
