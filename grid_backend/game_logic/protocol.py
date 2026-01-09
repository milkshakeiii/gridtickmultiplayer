"""
Protocol and types for game logic modules.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from grid_backend.models.entity import Entity


@dataclass
class Intent:
    """
    Represents a player intent passed to game logic.
    """

    player_id: UUID
    zone_id: UUID
    data: dict[str, Any]


@dataclass
class EntityCreate:
    """
    Describes a new entity to create.
    """

    x: int
    y: int
    width: int = 0
    height: int = 0
    owner_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityUpdate:
    """
    Describes updates to an existing entity.
    Only non-None fields will be updated.
    """

    id: UUID
    x: int | None = None
    y: int | None = None
    width: int | None = None
    height: int | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class TickResult:
    """
    Result returned by game logic after processing a tick.

    The framework owns the authoritative entity snapshot. Game modules return:
    - entity_creates/updates/deletes: deltas to apply (persisted by framework)
    - extras: arbitrary non-entity payload (events, notifications, etc.)

    Do NOT include an entity snapshot in extras - the framework builds that
    from post-apply state and passes it to get_player_state for filtering.
    """

    entity_creates: list[EntityCreate] = field(default_factory=list)
    entity_updates: list[EntityUpdate] = field(default_factory=list)
    entity_deletes: list[UUID] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)


class FrameworkAPI:
    """
    API provided to game logic modules for interacting with the framework.
    """

    def __init__(self, db_session_factory) -> None:
        self._db_session_factory = db_session_factory

    async def get_zones(self) -> list:
        """Get all zones."""
        from sqlalchemy import select
        from grid_backend.models.zone import Zone

        async with self._db_session_factory() as db:
            result = await db.execute(select(Zone))
            return list(result.scalars().all())

    async def get_zone_by_name(self, name: str):
        """Get a zone by name."""
        from sqlalchemy import select
        from grid_backend.models.zone import Zone

        async with self._db_session_factory() as db:
            result = await db.execute(
                select(Zone).where(Zone.name == name)
            )
            return result.scalar_one_or_none()

    async def create_zone(
        self,
        name: str,
        width: int = 100,
        height: int = 100,
        metadata: dict[str, Any] | None = None,
    ):
        """Create a new zone. Returns the created zone."""
        from grid_backend.models.zone import Zone

        async with self._db_session_factory() as db:
            zone = Zone(
                name=name,
                width=width,
                height=height,
                metadata_=metadata or {},
            )
            db.add(zone)
            await db.commit()
            await db.refresh(zone)
            return zone

    async def get_zone_entities(self, zone_id: UUID) -> list[Entity]:
        """Get all entities in a zone."""
        from sqlalchemy import select
        from grid_backend.models.entity import Entity

        async with self._db_session_factory() as db:
            result = await db.execute(
                select(Entity).where(Entity.zone_id == zone_id)
            )
            return list(result.scalars().all())

    async def get_entity(self, entity_id: UUID) -> Entity | None:
        """Get a specific entity by ID."""
        from sqlalchemy import select
        from grid_backend.models.entity import Entity

        async with self._db_session_factory() as db:
            result = await db.execute(
                select(Entity).where(Entity.id == entity_id)
            )
            return result.scalar_one_or_none()

    async def delete_entity(self, entity_id: UUID) -> bool:
        """Delete an entity by ID. Returns True if deleted, False if not found."""
        from sqlalchemy import delete
        from grid_backend.models.entity import Entity

        async with self._db_session_factory() as db:
            result = await db.execute(
                delete(Entity).where(Entity.id == entity_id)
            )
            await db.commit()
            return result.rowcount > 0


@runtime_checkable
class GameLogicModule(Protocol):
    """
    Protocol that game logic modules must implement.
    """

    async def on_init(self, framework: FrameworkAPI) -> None:
        """
        Called once when the module is loaded.
        Use to set up initial state or resources (e.g., create zones).
        """
        ...

    def on_tick(
        self,
        zone_id: UUID,
        entities: list[Entity],
        intents: list[Intent],
        tick_number: int,
    ) -> TickResult:
        """
        Called each tick for each zone.
        Process intents and return state changes.
        """
        ...

    def get_player_state(
        self,
        zone_id: UUID,
        player_id: UUID,
        full_state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Filter or transform state for a specific player.
        Canonical fog-of-war/redaction hook.

        full_state contains:
        - zone_id, tick_number
        - entities: framework-built authoritative snapshot (post-apply)
        - any extras from on_tick result

        Return the state to send to this specific player.
        """
        ...
