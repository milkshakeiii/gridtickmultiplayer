"""
Example game logic module demonstrating the module interface.

This module implements a simple movement system where players can move
entities around the grid via intents.

Note: The framework owns the authoritative entity snapshot. This module returns:
- Entity deltas (creates/updates/deletes) which the framework persists
- Extras (non-entity payload like events) which the framework merges into broadcast

The framework builds the entity snapshot from post-apply DB state and passes
it to get_player_state for fog-of-war filtering.
"""

import logging
from typing import Any
from uuid import UUID

from grid_backend.models.entity import Entity
from grid_backend.game_logic.protocol import (
    FrameworkAPI,
    GameLogicModule,
    Intent,
    TickResult,
    EntityUpdate,
    EntityCreate,
)

logger = logging.getLogger(__name__)


class ExampleGameModule:
    """
    Example game module with basic movement.

    Supported intents:
    - {"action": "move", "entity_id": "...", "dx": 1, "dy": 0}
    - {"action": "create_entity", "x": 0, "y": 0, "width": 1, "height": 1}
    - {"action": "delete_entity", "entity_id": "..."}
    - {"action": "owner_disconnect", "player_id": "..."} (synthetic, from framework)
    """

    # Default zone configuration
    DEFAULT_ZONE_NAME = "demo"
    DEFAULT_ZONE_WIDTH = 60
    DEFAULT_ZONE_HEIGHT = 35

    async def on_init(self, framework: FrameworkAPI) -> None:
        """Initialize the module and ensure default zone exists."""

        # Create default zone if it doesn't exist
        zone = await framework.get_zone_by_name(self.DEFAULT_ZONE_NAME)
        if zone is None:
            zone = await framework.create_zone(
                name=self.DEFAULT_ZONE_NAME,
                width=self.DEFAULT_ZONE_WIDTH,
                height=self.DEFAULT_ZONE_HEIGHT,
            )
            logger.info(f"Created default zone '{self.DEFAULT_ZONE_NAME}' ({zone.id})")
        else:
            logger.info(f"Using existing zone '{self.DEFAULT_ZONE_NAME}' ({zone.id})")

        # Clean up orphan entities from previous sessions
        # At startup, no players are connected, so any owned entity is stale
        entities = await framework.get_zone_entities(zone.id)
        orphan_count = 0
        for entity in entities:
            if entity.owner_id is not None:
                await framework.delete_entity(entity.id)
                orphan_count += 1
        if orphan_count > 0:
            logger.info(f"Cleaned up {orphan_count} orphan entities from previous session")

        logger.info("Example game module initialized")

    def on_tick(
        self,
        zone_id: UUID,
        entities: list[Entity],
        intents: list[Intent],
        tick_number: int,
    ) -> TickResult:
        """
        Process a tick for a zone.
        Handles movement and entity creation intents.
        """
        updates: list[EntityUpdate] = []
        creates: list[EntityCreate] = []
        deletes: list[UUID] = []
        entity_map = {e.id: e for e in entities}

        for intent in intents:
            try:
                action = intent.data.get("action")

                if action == "move":
                    update = self._handle_move(
                        intent=intent,
                        entity_map=entity_map,
                    )
                    if update is not None:
                        updates.append(update)

                elif action == "create_entity":
                    create = self._handle_create_entity(intent)
                    if create is not None:
                        creates.append(create)

                elif action == "delete_entity":
                    entity_id = self._handle_delete_entity(intent, entity_map)
                    if entity_id is not None:
                        deletes.append(entity_id)

                elif action == "owner_disconnect":
                    # Delete all entities owned by the disconnecting player
                    disconnected_ids = self._handle_owner_disconnect(intent, entities)
                    deletes.extend(disconnected_ids)

            except Exception as e:
                logger.warning(
                    f"Error processing intent from {intent.player_id}: {e}"
                )

        # Build extras (non-entity payload)
        # NOTE: Do NOT include entity snapshot here - framework builds that
        extras: dict[str, Any] = {}

        # Example: could add game-specific events here
        if creates:
            extras["events"] = extras.get("events", [])
            extras["events"].append({"type": "entities_created", "count": len(creates)})

        return TickResult(
            entity_creates=creates,
            entity_updates=updates,
            entity_deletes=deletes,
            extras=extras,
        )

    def _handle_move(
        self,
        intent: Intent,
        entity_map: dict[UUID, Entity],
    ) -> EntityUpdate | None:
        """Handle a movement intent."""
        entity_id_str = intent.data.get("entity_id")
        if entity_id_str is None:
            return None

        try:
            entity_id = UUID(entity_id_str)
        except ValueError:
            return None

        entity = entity_map.get(entity_id)
        if entity is None:
            return None

        dx = intent.data.get("dx", 0)
        dy = intent.data.get("dy", 0)

        if not isinstance(dx, int) or not isinstance(dy, int):
            return None

        # Calculate new position
        new_x = entity.x + dx
        new_y = entity.y + dy

        # Basic bounds check (game logic can enforce zone-specific rules)
        if new_x < 0 or new_y < 0:
            return None

        # Apply the update
        entity.x = new_x
        entity.y = new_y

        return EntityUpdate(
            id=entity_id,
            x=new_x,
            y=new_y,
        )

    def _handle_delete_entity(
        self,
        intent: Intent,
        entity_map: dict[UUID, Entity],
    ) -> UUID | None:
        """Handle an entity deletion intent."""
        entity_id_str = intent.data.get("entity_id")
        if entity_id_str is None:
            return None

        try:
            entity_id = UUID(entity_id_str)
        except ValueError:
            return None

        # Verify entity exists
        if entity_id not in entity_map:
            return None

        return entity_id

    def _handle_create_entity(self, intent: Intent) -> EntityCreate | None:
        """Handle an entity creation intent."""
        x = intent.data.get("x", 0)
        y = intent.data.get("y", 0)
        width = intent.data.get("width", 1)
        height = intent.data.get("height", 1)
        metadata = intent.data.get("metadata", {})

        if not all(isinstance(v, int) for v in [x, y, width, height]):
            return None

        if x < 0 or y < 0 or width < 0 or height < 0:
            return None

        return EntityCreate(
            x=x,
            y=y,
            width=width,
            height=height,
            owner_id=intent.player_id,  # Set owner to the player creating the entity
            metadata=metadata,
        )

    def _handle_owner_disconnect(
        self,
        intent: Intent,
        entities: list[Entity],
    ) -> list[UUID]:
        """
        Handle owner disconnect - delete all entities owned by the player.
        This is a synthetic intent queued by the framework when a player disconnects.
        """
        player_id_str = intent.data.get("player_id")
        if player_id_str is None:
            return []

        try:
            player_id = UUID(player_id_str)
        except ValueError:
            return []

        # Find all entities owned by this player
        to_delete = []
        for entity in entities:
            if entity.owner_id == player_id:
                to_delete.append(entity.id)
                logger.info(f"Deleting entity {entity.id} owned by disconnected player {player_id}")

        return to_delete

    def get_player_state(
        self,
        zone_id: UUID,
        player_id: UUID,
        full_state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Get player-specific state (fog-of-war hook).

        full_state contains:
        - zone_id, tick_number (from framework)
        - entities: authoritative snapshot built by framework
        - any extras from on_tick

        In a real game, this could:
        - Filter entities by visibility/distance
        - Hide certain entity metadata
        - Add player-specific data
        """
        # Copy state and add player-specific info
        player_state = dict(full_state)
        player_state["viewer_id"] = str(player_id)

        # Example fog-of-war: could filter entities here based on player position
        # For now, just pass through all entities
        return player_state


# Module instance for the loader
game_module = ExampleGameModule()
