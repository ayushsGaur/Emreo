"""
Central Dispatcher Service

The heart of the system. Orchestrates all AI/logic modules in the
correct sequence to produce a complete dispatch decision.

Flow:
  1. Validate incident exists and is dispatchable
  2. Predict severity (ML model or rule-based fallback)
  3. Allocate best available ambulance (weighted scoring)
  4. Compute optimal route (OSRM or haversine fallback)
  5. Persist dispatch decision to DB
  6. Update ambulance status to DISPATCHED
  7. Broadcast real-time update to all dashboards
  8. Send route + instructions to the assigned ambulance device
  9. Return structured DispatchResult

Each step is logged. Each failure raises a specific exception.
The dispatcher never swallows errors silently.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.incident import (
    IncidentORM, IncidentStatus, DispatchResult, SeverityPriority
)
from backend.models.ambulance import AmbulanceStatus
from backend.repositories.incident_repo import IncidentRepository
from backend.repositories.ambulance_repo import AmbulanceRepository
from backend.services.severity import severity_service
from backend.services.resource import resource_service
from backend.services.routing import routing_service
from backend.services.websocket_manager import connection_manager
from backend.core.exceptions import (
    IncidentNotFoundError,
    IncidentAlreadyClosedError,
    AmbulanceAlreadyDispatchedError,
)
from backend.core.logging import get_logger

logger = get_logger(__name__)


class DispatcherService:

    async def dispatch(
        self,
        db: AsyncSession,
        incident_id: uuid.UUID,
    ) -> DispatchResult:
        """
        Execute a full dispatch cycle for a given incident.

        Can be triggered:
          - Automatically on incident creation (auto-dispatch)
          - Manually by the dispatcher from the dashboard
          - Via the POST /api/v1/dispatch endpoint
        """
        incident_repo = IncidentRepository(db)
        ambulance_repo = AmbulanceRepository(db)

        # ── Step 1: Validate incident ─────────────────────────────────────────
        incident = await incident_repo.get_by_id(incident_id)
        if not incident:
            raise IncidentNotFoundError()
        if incident.status == IncidentStatus.CLOSED:
            raise IncidentAlreadyClosedError()

        # logger.info("Dispatch started", incident_id=str(incident_id),
        #             current_status=incident.status)
        logger.info(
        f"Dispatch started | incident_id={str(incident_id)} | current_status={incident.status}"
        )

        # Mark as dispatching so concurrent calls don't double-dispatch
        await incident_repo.update_status(incident_id, IncidentStatus.DISPATCHING)

        # ── Step 2: Severity prediction ───────────────────────────────────────
        severity, confidence, flagged = await self._get_or_predict_severity(
            incident, incident_repo
        )
        # logger.info("Severity confirmed", priority=severity.value,
        #             confidence=confidence, flagged=flagged)
        logger.info(
        f"Severity confirmed | priority={severity.value} | confidence={confidence} | flagged={flagged}"
        )

        # ── Step 3: Resource allocation ───────────────────────────────────────
        allocation = await resource_service.find_best_unit(
            db=db,
            incident_lat=incident.latitude,
            incident_lng=incident.longitude,
            severity=severity,
        )
        # logger.info("Ambulance allocated",
        #             unit=allocation.unit_number,
        #             distance_km=allocation.distance_km,
        #             type_matched=allocation.type_matched)
        logger.info(
        f"Ambulance allocated | unit={allocation.unit_number} | distance_km={allocation.distance_km} | type_matched={allocation.type_matched}"
        )

        # ── Step 4: Route computation ─────────────────────────────────────────
        ambulance = await ambulance_repo.get_by_id(allocation.ambulance_id)
        route = await routing_service.compute_route(
            origin_lat=ambulance.latitude,
            origin_lng=ambulance.longitude,
            dest_lat=incident.latitude,
            dest_lng=incident.longitude,
        )
        # logger.info("Route computed",
        #             distance_km=route.distance_km,
        #             eta_minutes=route.duration_minutes,
        #             via_osrm=route.via_osrm)
        logger.info(
        f"Route computed | distance_km={route.distance_km} | eta_minutes={route.duration_minutes} | via_osrm={route.via_osrm}"
        )

        # ── Step 5: Persist dispatch decision ─────────────────────────────────
        await incident_repo.update_dispatch(
            incident_id=incident_id,
            ambulance_id=allocation.ambulance_id,
            eta_minutes=route.duration_minutes,
            route_polyline=route.polyline,
        )

        # ── Step 6: Update ambulance status ───────────────────────────────────
        await ambulance_repo.update_status(
            ambulance_id=allocation.ambulance_id,
            status=AmbulanceStatus.DISPATCHED,
            incident_id=incident_id,
        )

        # ── Step 7: Broadcast to all dashboards ───────────────────────────────
        dispatch_payload = {
            "incident_id":    str(incident_id),
            "ambulance_id":   str(allocation.ambulance_id),
            "unit_number":    allocation.unit_number,
            "severity":       severity.value,
            "eta_minutes":    route.duration_minutes,
            "distance_km":    route.distance_km,
            "flagged":        flagged,
            "incident_location": {
                "lat": incident.latitude,
                "lng": incident.longitude,
            },
        }
        await connection_manager.broadcast_to_dashboards(
            "dispatch.completed", dispatch_payload
        )

        # ── Step 8: Notify the assigned ambulance device ──────────────────────
        ambulance_instruction = {
            "incident_id":     str(incident_id),
            "destination_lat": incident.latitude,
            "destination_lng": incident.longitude,
            "address":         incident.address,
            "complaint":       incident.complaint,
            "severity":        severity.value,
            "route_polyline":  route.polyline,
            "eta_minutes":     route.duration_minutes,
        }
        sent = await connection_manager.send_to_ambulance(
            str(allocation.ambulance_id), "dispatch.assigned", ambulance_instruction
        )
        if not sent:
            # logger.warning(
            #     "Ambulance device not connected via WebSocket — dispatch logged only",
            #     ambulance_id=str(allocation.ambulance_id),
            # )
            logger.warning(
            f"Ambulance device not connected via WebSocket — dispatch logged only | ambulance_id={str(allocation.ambulance_id)}"
            )

        # ── Step 9: Build and return result ───────────────────────────────────
        result = DispatchResult(
            incident_id=incident_id,
            assigned_ambulance_id=allocation.ambulance_id,
            ambulance_type=allocation.ambulance_type,
            severity=severity,
            severity_confidence=confidence,
            estimated_arrival_minutes=route.duration_minutes,
            route_polyline=route.polyline,
            dispatch_timestamp=datetime.now(timezone.utc),
            flagged_for_review=flagged,
        )

        # logger.info(
        #     "Dispatch completed successfully",
        #     incident_id=str(incident_id),
        #     unit=allocation.unit_number,
        #     eta=route.duration_minutes,
        #     severity=severity.value,
        # )

        logger.info(
        f"Dispatch completed successfully | incident_id={str(incident_id)} | unit={allocation.unit_number} | eta={route.duration_minutes} | severity={severity.value}"
        )


        return result

    async def _get_or_predict_severity(
        self,
        incident: IncidentORM,
        repo: IncidentRepository,
    ) -> tuple[SeverityPriority, float, bool]:
        """
        Use existing severity if already predicted (e.g. at intake).
        Re-predict only if not yet scored or flagged for review.
        """
        if incident.severity and not incident.severity_flagged_for_review:
            return (
                SeverityPriority(incident.severity),
                incident.severity_confidence or 0.0,
                False,
            )

        # Build a minimal IncidentCreate-like object for the model
        from models.incident import IncidentCreate
        data = IncidentCreate(
            caller_name="dispatcher-repredict",
            caller_phone="0000000000",
            complaint=incident.complaint,
            latitude=incident.latitude,
            longitude=incident.longitude,
            patient_age=incident.patient_age,
            patient_conscious=incident.patient_conscious,
            patient_breathing=incident.patient_breathing,
        )

        result = severity_service.predict(data)
        await repo.update_severity(
            incident.id, result.priority, result.confidence, result.flagged_for_review
        )
        return result.priority, result.confidence, result.flagged_for_review


# Singleton
dispatcher_service = DispatcherService()
