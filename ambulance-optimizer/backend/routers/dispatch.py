"""
Dispatch Router

Routes:
  POST /api/v1/dispatch/{incident_id}   — trigger dispatch for an incident
  GET  /api/v1/dispatch/{incident_id}   — get dispatch result for an incident
  WS   /api/v1/ws/dashboard             — dashboard real-time event stream
  WS   /api/v1/ws/ambulance/{id}        — ambulance device GPS push channel
"""

import uuid
import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.exceptions import IncidentNotFoundError
from backend.models.incident import DispatchResult, IncidentResponse
from backend.repositories.incident_repo import IncidentRepository
from backend.repositories.ambulance_repo import AmbulanceRepository
from backend.services.dispatcher import dispatcher_service
from backend.services.websocket_manager import connection_manager
from backend.models.ambulance import AmbulanceLocationUpdate
from backend.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ── REST Endpoints ────────────────────────────────────────────────────────────

@router.post(
    "/dispatch/{incident_id}",
    response_model=DispatchResult,
    status_code=status.HTTP_200_OK,
    summary="Trigger dispatch for an incident",
)
async def trigger_dispatch(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Run the full dispatch pipeline for an incident:
    severity prediction → resource allocation → route computation → notify ambulance.

    Idempotent: if the incident is already dispatched, returns the existing dispatch info.
    """
    from backend.models.incident import IncidentStatus
    incident_repo = IncidentRepository(db)
    incident = await incident_repo.get_by_id(incident_id)

    if not incident:
        raise IncidentNotFoundError()

    # If already dispatched, return current state
    if incident.status == IncidentStatus.DISPATCHED and incident.assigned_ambulance_id:
        return DispatchResult(
            incident_id=incident.id,
            assigned_ambulance_id=incident.assigned_ambulance_id,
            ambulance_type="ALS",  # will be fetched from ambulance record in full impl
            severity=incident.severity,
            severity_confidence=incident.severity_confidence or 0.0,
            estimated_arrival_minutes=incident.estimated_arrival_minutes or 0.0,
            route_polyline=incident.route_polyline,
            dispatch_timestamp=incident.dispatched_at,
            flagged_for_review=incident.severity_flagged_for_review,
        )

    return await dispatcher_service.dispatch(db=db, incident_id=incident_id)


# ── WebSocket: Dashboard ──────────────────────────────────────────────────────

@router.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    """
    Real-time event stream for dispatcher dashboard clients.

    Events pushed from server:
      - incident.new          — new incident logged
      - incident.status_changed
      - dispatch.completed    — ambulance assigned and en route
      - ambulance.location    — GPS position update
      - ping                  — heartbeat

    Messages from client:
      - {"event": "pong"}     — heartbeat response (keep-alive)
    """
    client_id = await connection_manager.connect_dashboard(websocket)
    try:
        # Send current connection state immediately on connect
        await websocket.send_json({
            "event": "connected",
            "data": {
                "client_id": client_id,
                "message": "Connected to Ambulance Optimizer real-time feed",
            }
        })

        while True:
            # Listen for client messages (pong, filter requests, etc.)
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                event = msg.get("event")
                if event == "pong":
                    pass  # heartbeat acknowledged
                else:
                    logger.debug("Dashboard message received", event=event, client_id=client_id)
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        connection_manager.disconnect_dashboard(client_id)
    except Exception as e:
        # logger.error("Dashboard WebSocket error", client_id=client_id, error=str(e))
        logger.error(f"Dashboard WebSocket error | client_id={client_id} | error={str(e)}", exc_info=True)
        connection_manager.disconnect_dashboard(client_id)


# ── WebSocket: Ambulance Device ───────────────────────────────────────────────

@router.websocket("/ws/ambulance/{ambulance_id}")
async def ambulance_websocket(
    websocket: WebSocket,
    ambulance_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Bidirectional WebSocket channel for ambulance devices.

    Device pushes:
      {"event": "location", "data": {lat, lng, heading, speed, status, timestamp}}

    Server pushes:
      {"event": "dispatch.assigned", "data": {destination, route, complaint, ...}}
      {"event": "ping"}
    """
    amb_id_str = str(ambulance_id)
    await connection_manager.connect_ambulance(websocket, amb_id_str)

    ambulance_repo = AmbulanceRepository(db)

    
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                event = msg.get("event")
                data = msg.get("data", {})

                if event == "location":
                    # update = AmbulanceLocationUpdate(
                    #     ambulance_id=ambulance_id,
                    #     **data
                    # )
                   data.pop("ambulance_id", None)
                   update = AmbulanceLocationUpdate(
                    ambulance_id=ambulance_id,
                        **data
                     )

                    # Persist to DB
                   await ambulance_repo.update_location(
                        ambulance_id=ambulance_id,
                        latitude=update.latitude,
                        longitude=update.longitude,
                        heading=update.heading_degrees,
                        speed_kmh=update.speed_kmh,
                        status=update.status,
                    )
                   await db.commit()

                    # Broadcast GPS position to all dashboards
                   await connection_manager.broadcast_to_dashboards(
                        "ambulance.location",
                        {
                            "ambulance_id": amb_id_str,
                            "lat": update.latitude,
                            "lng": update.longitude,
                            "heading": update.heading_degrees,
                            "speed_kmh": update.speed_kmh,
                            "status": update.status.value if update.status else None,
                            "timestamp": update.timestamp.isoformat(),
                        }
                    )

                elif event == "pong":
                     pass

                else:
                    logger.debug("Unknown ambulance event", event=event, ambulance_id=amb_id_str)

            except Exception as e:
                # logger.warning("Failed to process ambulance message",
                #                ambulance_id=amb_id_str, error=str(e))
                logger.warning(f"Failed to process ambulance message | ambulance_id={amb_id_str} | error={str(e)}")

    except WebSocketDisconnect:
        connection_manager.disconnect_ambulance(amb_id_str)
    except Exception as e:
        logger.error(f"Ambulance WebSocket error | ambulance_id={amb_id_str} | error={str(e)}")
        connection_manager.disconnect_ambulance(amb_id_str)
