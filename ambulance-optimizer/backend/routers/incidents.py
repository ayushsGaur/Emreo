"""
Incidents Router

Routes:
  POST   /api/v1/incidents              — log a new incident
  GET    /api/v1/incidents              — list all active incidents
  GET    /api/v1/incidents/{id}         — get a specific incident
  PATCH  /api/v1/incidents/{id}/status  — update incident status
"""


import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.exceptions import IncidentNotFoundError, IncidentAlreadyClosedError
from backend.models.incident import (
    IncidentCreate, IncidentResponse, IncidentStatusUpdate, IncidentStatus
)
from backend.repositories.incident_repo import IncidentRepository
from backend.services.severity import severity_service
from backend.services.websocket_manager import connection_manager
from backend.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


async def _resolve_coordinates(data: IncidentCreate) -> tuple[float, float]:
    """
    If coordinates are provided, use them directly.
    If only an address is provided, geocode it via Nominatim.
    """
    if data.latitude is not None and data.longitude is not None:
        return data.latitude, data.longitude

    # Geocoding via Nominatim (free, OpenStreetMap)
    import httpx
    from backend.core.config import settings
    from backend.core.exceptions import GeocodingFailedError

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.NOMINATIM_BASE_URL}/search",
                params={"q": data.address, "format": "json", "limit": 1},
                headers={"User-Agent": "AmbulanceOptimizer/1.0"},
                timeout=5.0,
            )
            results = response.json()
            if not results:
                raise GeocodingFailedError(detail=f"No results for: {data.address}")
            return float(results[0]["lat"]), float(results[0]["lon"])
        except GeocodingFailedError:
            raise
        except Exception as e:
            raise GeocodingFailedError(detail=str(e))


@router.post(
    "/incidents",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log a new emergency incident",
)
async def create_incident(
    data: IncidentCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Log a new emergency incident from a call center, web form, or API.

    - Geocodes the address if coordinates are not provided
    - Runs severity prediction immediately
    - Broadcasts the new incident to all connected dashboards
    """
    # 1. Resolve coordinates
    latitude, longitude = await _resolve_coordinates(data)

    # 2. Persist incident
    repo = IncidentRepository(db)
    incident = await repo.create(data, latitude, longitude)

    # 3. Run severity prediction (non-blocking — doesn't hold up the response)
    try:
        result = severity_service.predict(data)
        await repo.update_severity(
            incident.id, result.priority, result.confidence, result.flagged_for_review
        )
        incident.severity = result.priority
        incident.severity_confidence = result.confidence
        incident.severity_flagged_for_review = result.flagged_for_review
    except Exception as e:
        logger.error(f"Severity prediction failed for incident | incident_id={str(incident.id)} | error={str(e)}")
        # Continue — incident is still logged, dispatcher can triage manually

    # 4. Notify dashboards
    await connection_manager.broadcast_to_dashboards("incident.new", {
        "incident_id": str(incident.id),
        "severity": incident.severity.value if incident.severity else None,
        "location": {"lat": latitude, "lng": longitude},
        "complaint": data.complaint[:100],
    })

    return IncidentResponse.model_validate(incident)


@router.get(
    "/incidents",
    response_model=list[IncidentResponse],
    summary="List all active incidents",
)
async def list_incidents(db: AsyncSession = Depends(get_db)):
    repo = IncidentRepository(db)
    incidents = await repo.list_active()
    return [IncidentResponse.model_validate(i) for i in incidents]


@router.get(
    "/incidents/{incident_id}",
    response_model=IncidentResponse,
    summary="Get a specific incident by ID",
)
async def get_incident(incident_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    repo = IncidentRepository(db)
    incident = await repo.get_by_id(incident_id)
    if not incident:
        raise IncidentNotFoundError()
    return IncidentResponse.model_validate(incident)


@router.patch(
    "/incidents/{incident_id}/status",
    response_model=IncidentResponse,
    summary="Update an incident's status",
)
async def update_incident_status(
    incident_id: uuid.UUID,
    data: IncidentStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    repo = IncidentRepository(db)
    incident = await repo.get_by_id(incident_id)

    if not incident:
        raise IncidentNotFoundError()
    if incident.status == IncidentStatus.CLOSED:
        raise IncidentAlreadyClosedError()

    await repo.update_status(incident_id, data.status, data.notes)

    # Notify dashboards of status change
    await connection_manager.broadcast_to_dashboards("incident.status_changed", {
        "incident_id": str(incident_id),
        "new_status": data.status.value,
    })

    incident = await repo.get_by_id(incident_id)
    return IncidentResponse.model_validate(incident)
