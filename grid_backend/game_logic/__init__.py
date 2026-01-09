"""
Game logic module system for Grid Backend.
"""

from grid_backend.game_logic.protocol import (
    GameLogicModule,
    TickResult,
    EntityCreate,
    EntityUpdate,
    Intent,
    FrameworkAPI,
)
from grid_backend.game_logic.loader import load_game_module

__all__ = [
    "GameLogicModule",
    "TickResult",
    "EntityCreate",
    "EntityUpdate",
    "Intent",
    "FrameworkAPI",
    "load_game_module",
]
