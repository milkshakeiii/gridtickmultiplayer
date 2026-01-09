"""
WebSocket handling for Grid Backend.
"""

from grid_backend.websocket.manager import ConnectionManager, get_connection_manager

__all__ = ["ConnectionManager", "get_connection_manager"]
