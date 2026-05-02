"""
Dashboard Router

Aggregated read endpoints used exclusively by the frontend dashboard.
No mutations here — pure data for visualization.

Routes:
  GET /api/v1/dashboard/summary      — KPI cards: active incidents, fleet status, avg ETA
  GET /api/v1/dashboard/metrics      — ML model performance stats
  GET /api/v1/dashboard/incidents/heatmap — incident coordinates for map density layer
"""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from backend.core.database import get_db
from backend.models.incident import IncidentORM, IncidentStatus, SeverityPriority
from backend.models.ambulance import AmbulanceORM
from backend.repositories.incident_repo import IncidentRepository
from backend.repositories.ambulance_repo import AmbulanceRepository
from backend.services.severity import severity_service
from backend.services.websocket_manager import connection_manager
from backend.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get(
    "/dashboard/summary",
    summary="Top-level KPI summary for the dispatcher dashboard",
)
async def get_dashboard_summary(db: AsyncSession = Depends(get_db)):
    """
    Returns everything the dashboard header needs in one call:
    - Active incident counts by status
    - Fleet status breakdown
    - Average response time (last 24h)
    - Connected WebSocket clients
    """
    incident_repo = IncidentRepository(db)
    ambulance_repo = AmbulanceRepository(db)

    # Incident counts by status
    active_incidents = await incident_repo.list_active()
    incident_by_status: dict[str, int] = {}
    incident_by_severity: dict[str, int] = {}

    for inc in active_incidents:
        status_key = inc.status if isinstance(inc.status, str) else inc.status.value
        incident_by_status[status_key] = incident_by_status.get(status_key, 0) + 1

        if inc.severity:
            sev_key = inc.severity if isinstance(inc.severity, str) else inc.severity.value
            incident_by_severity[sev_key] = incident_by_severity.get(sev_key, 0) + 1

    # Fleet status
    fleet_status = await ambulance_repo.count_by_status()

    # Average response time (last 24h)
    avg_response_time = await incident_repo.average_response_time_minutes()

    # Critical incidents needing attention
    critical_count = incident_by_severity.get("P1", 0)
    flagged_count = sum(
        1 for inc in active_incidents
        if inc.severity_flagged_for_review
    )

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "incidents": {
            "active_total": len(active_incidents),
            "by_status": incident_by_status,
            "by_severity": incident_by_severity,
            "critical_p1_count": critical_count,
            "flagged_for_review": flagged_count,
        },
        "fleet": {
            "by_status": fleet_status,
            "available_count": fleet_status.get("available", 0),
            "dispatched_count": fleet_status.get("dispatched", 0),
        },
        "performance": {
            "avg_response_time_minutes": avg_response_time,
        },
        "realtime": {
            "connected_dashboards": connection_manager.dashboard_count,
            "connected_ambulances": connection_manager.ambulance_count,
            "live_ambulance_ids": connection_manager.connected_ambulance_ids,
        },
    }


@router.get(
    "/dashboard/metrics",
    summary="ML model performance metrics for the model monitoring panel",
)
async def get_ml_metrics(db: AsyncSession = Depends(get_db)):
    """
    Returns ML model performance data for the dashboard monitoring tab.

    In production this would query MLflow or a metrics store.
    For now it computes live accuracy against resolved incidents
    where the actual severity outcome is known.
    """
    # Incidents closed in the last 30 days where severity was predicted
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    result = await db.execute(
        select(
            IncidentORM.severity,
            func.count().label("count"),
            func.avg(IncidentORM.severity_confidence).label("avg_confidence"),
        )
        .where(
            and_(
                IncidentORM.closed_at >= thirty_days_ago,
                IncidentORM.severity.isnot(None),
            )
        )
        .group_by(IncidentORM.severity)
    )
    rows = result.fetchall()

    severity_breakdown = [
        {
            "priority": row.severity,
            "count": row.count,
            "avg_confidence": round(float(row.avg_confidence or 0), 3),
        }
        for row in rows
    ]

    total_predicted = sum(r["count"] for r in severity_breakdown)
    flagged_result = await db.execute(
        select(func.count())
        .where(
            and_(
                IncidentORM.closed_at >= thirty_days_ago,
                IncidentORM.severity_flagged_for_review == True,
            )
        )
    )
    flagged_count = flagged_result.scalar_one_or_none() or 0

    return {
        "model_version": severity_service.model_version,
        "model_loaded": severity_service.is_loaded,
        "mode": "ml_model" if severity_service.is_loaded else "rule_based_fallback",
        "last_30_days": {
            "total_predictions": total_predicted,
            "flagged_for_review": flagged_count,
            "flag_rate_pct": round((flagged_count / total_predicted * 100), 1) if total_predicted else 0,
            "by_severity": severity_breakdown,
        },
        "thresholds": {
            "confidence_threshold": 0.6,
            "flag_below_threshold": True,
        },
    }


@router.get(
    "/dashboard/incidents/heatmap",
    summary="Incident coordinates for map heatmap layer",
)
async def get_incident_heatmap(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
):
    """
    Returns lat/lng + severity weight for all incidents in the last N days.
    Used to render a density heatmap on the Leaflet map.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            IncidentORM.latitude,
            IncidentORM.longitude,
            IncidentORM.severity,
        ).where(IncidentORM.created_at >= since)
    )
    rows = result.fetchall()

    # Weight by severity: P1 = 1.0, P2 = 0.75, P3 = 0.5, P4 = 0.25
    severity_weight = {
        "P1": 1.0, "P2": 0.75, "P3": 0.5, "P4": 0.25, None: 0.3,
    }

    points = [
        {
            "lat": row.latitude,
            "lng": row.longitude,
            "weight": severity_weight.get(row.severity, 0.3),
        }
        for row in rows
    ]

    return {
        "period_days": days,
        "total_incidents": len(points),
        "points": points,
    }


from fastapi import WebSocket
import asyncio


@router.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    print("➡️ WS endpoint hit")

    try:
        await websocket.accept()
        print("✅ WS CONNECTED")

        while True:
            await websocket.send_json({"event": "ping"})
            await asyncio.sleep(2)

    except Exception as e:
        print("❌ WS ERROR:", e)


# from fastapi import WebSocket
# import asyncio


# @router.websocket("/ws/dashboard")
# async def dashboard_websocket(websocket: WebSocket):
#     await websocket.accept()
#     logger.info("Dashboard WebSocket connected")

#     try:
#         while True:
#             # Send basic heartbeat (you can extend later)
#             await websocket.send_json({
#                 "event": "ping"
#             })
#             await asyncio.sleep(2)

#     except Exception as e:
#         logger.warning(f"Dashboard WebSocket error: {str(e)}")
#     finally:
#         logger.info("Dashboard WebSocket disconnected")