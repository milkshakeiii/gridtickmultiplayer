"""
Game logic module loader.
"""

import importlib
import logging
from typing import Any

from grid_backend.game_logic.protocol import GameLogicModule, FrameworkAPI

logger = logging.getLogger(__name__)


async def load_game_module(
    module_path: str,
    framework: FrameworkAPI,
) -> GameLogicModule | None:
    """
    Load and initialize a game logic module.

    Args:
        module_path: Python module path (e.g., "grid_backend.game_modules.example")
        framework: FrameworkAPI instance for module to use

    Returns:
        Initialized GameLogicModule or None if loading fails
    """
    try:
        module = importlib.import_module(module_path)

        # Look for a class that implements GameLogicModule
        game_class = None
        for name in dir(module):
            obj = getattr(module, name)
            if (
                isinstance(obj, type)
                and obj is not GameLogicModule
                and hasattr(obj, "on_init")
                and hasattr(obj, "on_tick")
                and hasattr(obj, "get_player_state")
            ):
                game_class = obj
                break

        if game_class is None:
            # Try to find a default instance
            if hasattr(module, "game_module"):
                instance = module.game_module
            else:
                logger.error(f"No game logic class found in {module_path}")
                return None
        else:
            instance = game_class()

        # Initialize the module (async)
        await instance.on_init(framework)

        logger.info(f"Loaded game logic module: {module_path}")
        return instance

    except ImportError as e:
        logger.error(f"Failed to import game module {module_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to load game module {module_path}: {e}", exc_info=True)
        return None
