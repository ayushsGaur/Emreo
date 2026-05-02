"""
WebSocket Connection Manager

Manages two pools of WebSocket connections:
  1. Dashboard clients — browser tabs showing the live map
  2. Ambulance devices — tablets/phones in ambulances pushing GPS

Features:
  - Graceful disconnect handling
  - Broadcast to all dashboards
  - Targeted message to a specific ambulance
  - Heartbeat ping to detect stale connections
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from backend.core.logging import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    def __init__(self):
        # dashboard_id → WebSocket
        self._dashboard_clients: dict[str, WebSocket] = {}
        # ambulance_id (str) → WebSocket
        self._ambulance_clients: dict[str, WebSocket] = {}

    # ── Dashboard connections ──────────────────────────────────────────────────

    async def connect_dashboard(self, websocket: WebSocket) -> str:
        """Accept a dashboard client. Returns a generated client ID."""
        await websocket.accept()
        client_id = str(uuid.uuid4())
        self._dashboard_clients[client_id] = websocket
        # logger.info("Dashboard client connected", client_id=client_id,
        #             total_dashboards=len(self._dashboard_clients))
        logger.info(
        f"Dashboard client connected | client_id={client_id} | total_dashboards={len(self._dashboard_clients)}"
        )

        return client_id

    def disconnect_dashboard(self, client_id: str) -> None:
        self._dashboard_clients.pop(client_id, None)
        # logger.info("Dashboard client disconnected", client_id=client_id,
        #             total_dashboards=len(self._dashboard_clients))

        logger.info(
        f"Dashboard client disconnected | client_id={client_id} | total_dashboards={len(self._dashboard_clients)}"
    )

    async def broadcast_to_dashboards(self, event: str, data: Any) -> None:
        """Send a message to every connected dashboard. Dead connections are removed."""
        payload = json.dumps({
            "event": event,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, default=str)

        dead: list[str] = []
        for client_id, ws in self._dashboard_clients.items():
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(client_id)

        for client_id in dead:
            self.disconnect_dashboard(client_id)

    # ── Ambulance connections ──────────────────────────────────────────────────

    async def connect_ambulance(self, websocket: WebSocket, ambulance_id: str) -> None:
        """Accept an ambulance device connection."""
        await websocket.accept()
        self._ambulance_clients[ambulance_id] = websocket
        # logger.info("Ambulance connected", ambulance_id=ambulance_id,
        #             total_ambulances=len(self._ambulance_clients))

        logger.info(
        f"Ambulance connected | ambulance_id={ambulance_id} | total_ambulances={len(self._ambulance_clients)}"
        )

    def disconnect_ambulance(self, ambulance_id: str) -> None:
        self._ambulance_clients.pop(ambulance_id, None)
        logger.info(f"Ambulance disconnected | ambulance_id={ambulance_id}")

    async def send_to_ambulance(self, ambulance_id: str, event: str, data: Any) -> bool:
        """
        Send a message to a specific ambulance.
        Returns False if the ambulance is not connected.
        """
        ws = self._ambulance_clients.get(ambulance_id)
        if not ws:
            return False
        try:
            payload = json.dumps({"event": event, "data": data}, default=str)
            await ws.send_text(payload)
            return True
        except Exception as e:
            # logger.warning("Failed to send to ambulance", ambulance_id=ambulance_id, error=str(e))
            logger.warning(f"Failed to send to ambulance | ambulance_id={ambulance_id} | error={str(e)}")
            self.disconnect_ambulance(ambulance_id)
            return False

    # ── Status ─────────────────────────────────────────────────────────────────

    @property
    def dashboard_count(self) -> int:
        return len(self._dashboard_clients)

    @property
    def ambulance_count(self) -> int:
        return len(self._ambulance_clients)

    @property
    def connected_ambulance_ids(self) -> list[str]:
        return list(self._ambulance_clients.keys())

    # ── Heartbeat ──────────────────────────────────────────────────────────────

    async def start_heartbeat(self, interval_seconds: int = 30) -> None:
        """
        Periodically ping all clients to detect and remove stale connections.
        Run as a background task at startup.
        """
        while True:
            await asyncio.sleep(interval_seconds)
            all_clients = (
                list(self._dashboard_clients.items())
                + [(aid, ws) for aid, ws in self._ambulance_clients.items()]
            )
            for client_id, ws in all_clients:
                try:
                    await ws.send_text(json.dumps({"event": "ping"}))
                except Exception:
                    # Will be cleaned up on next broadcast
                    pass


# Singleton — shared across the entire application
connection_manager = ConnectionManager()
