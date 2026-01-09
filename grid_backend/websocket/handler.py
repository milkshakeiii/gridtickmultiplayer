"""
WebSocket message handler for Grid Backend.
"""

import asyncio
import json
import logging
from typing import Any
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketState

from grid_backend.models.zone import Zone
from grid_backend.websocket.manager import ConnectionInfo, ConnectionManager

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """
    Handles WebSocket messages for a connected player.
    """

    def __init__(
        self,
        manager: ConnectionManager,
        info: ConnectionInfo,
        db_session_factory,
    ) -> None:
        self.manager = manager
        self.info = info
        self.db_session_factory = db_session_factory
        self._running = True

    async def handle_connection(self) -> None:
        """
        Main message loop for a WebSocket connection.

        Expected (non-fatal) errors:
        - WebSocketDisconnect: client disconnected
        - asyncio.TimeoutError: send timeout
        - ConnectionResetError, BrokenPipeError: connection lost
        - json.JSONDecodeError: invalid JSON -> close with 1007

        All other errors propagate (fail-fast).
        """
        try:
            while self._running:
                try:
                    raw = await self.info.websocket.receive_text()
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    # Invalid JSON - close immediately with protocol error code
                    logger.warning(f"Invalid JSON from player {self.info.player_id}, closing")
                    await self.info.websocket.close(code=1007)  # Invalid frame payload
                    return
                await self._handle_message(message)
        except WebSocketDisconnect:
            # Expected: client disconnected normally
            logger.info(f"Player {self.info.player_id} disconnected")
        except asyncio.TimeoutError:
            # Expected: send timeout
            logger.warning(f"Timeout for player {self.info.player_id}")
        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            # Expected: connection lost
            logger.info(f"Connection lost for player {self.info.player_id}: {e}")
        finally:
            # Pass connection_id to prevent stale handler from disconnecting newer connection
            await self.manager.disconnect(self.info.player_id, self.info.connection_id)

    async def _handle_message(self, message: dict[str, Any]) -> None:
        """Route incoming messages to appropriate handlers."""
        msg_type = message.get("type")

        if msg_type is None:
            await self._send_error("Missing message type")
            return

        handlers = {
            "subscribe": self._handle_subscribe,
            "intent": self._handle_intent,
        }

        handler = handlers.get(msg_type)
        if handler is None:
            await self._send_error(f"Unknown message type: {msg_type}")
            return

        await handler(message)

    async def _handle_subscribe(self, message: dict[str, Any]) -> None:
        """Handle zone subscription request."""
        zone_id_str = message.get("zone_id")

        if zone_id_str is None:
            await self._send_error("Missing zone_id")
            return

        try:
            zone_id = UUID(zone_id_str)
        except ValueError:
            await self._send_error("Invalid zone_id format")
            return

        # Verify zone exists
        async with self.db_session_factory() as db:
            result = await db.execute(
                select(Zone).where(Zone.id == zone_id)
            )
            zone = result.scalar_one_or_none()

            if zone is None:
                await self._send_error("Zone not found")
                return

        # Subscribe to zone
        success = await self.manager.subscribe_to_zone(self.info.player_id, zone_id)

        if success:
            await self.info.websocket.send_json({
                "type": "subscribed",
                "zone_id": str(zone_id),
            })
            logger.info(f"Player {self.info.player_id} subscribed to zone {zone_id}")
        else:
            await self._send_error("Failed to subscribe to zone")

    async def _handle_intent(self, message: dict[str, Any]) -> None:
        """Handle player intent submission."""
        if self.info.zone_id is None:
            await self._send_error("Must subscribe to a zone first")
            return

        intent_data = message.get("data")
        if intent_data is None:
            await self._send_error("Missing intent data")
            return

        # Queue intent for processing
        from grid_backend.tick_engine import get_tick_engine

        engine = get_tick_engine()
        if engine is None:
            await self._send_error("Tick engine not available")
            return

        # Await enqueue before acknowledging (ensures intent is queued)
        await engine.queue_intent(
            zone_id=self.info.zone_id,
            player_id=self.info.player_id,
            data=intent_data,
        )

        # Acknowledge intent receipt
        await self.info.websocket.send_json({
            "type": "intent_received",
        })

    async def _send_error(self, message: str) -> None:
        """Send error message to client."""
        try:
            await self.info.websocket.send_json({
                "type": "error",
                "message": message,
            })
        except Exception:
            pass  # Connection might be closed

    def stop(self) -> None:
        """Stop the message handler."""
        self._running = False
