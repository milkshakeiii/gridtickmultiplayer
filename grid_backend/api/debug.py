"""
Debug API routes for Grid Backend.
All endpoints require debug role access.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from grid_backend.database import get_db
from grid_backend.models.player import Player
from grid_backend.models.zone import Zone
from grid_backend.models.entity import Entity
from grid_backend.api.auth import get_debug_player

router = APIRouter()


# Response schemas
class EntityResponse(BaseModel):
    """Response schema for entity info."""

    id: UUID
    zone_id: UUID
    x: int
    y: int
    width: int
    height: int
    metadata: dict[str, Any] | None

    class Config:
        from_attributes = True


class ZoneStateResponse(BaseModel):
    """Response schema for zone state inspection."""

    id: UUID
    name: str
    width: int
    height: int
    metadata: dict[str, Any] | None
    entities: list[EntityResponse]


class ConnectionInfo(BaseModel):
    """Info about a connected player."""

    player_id: UUID
    username: str
    zone_id: UUID | None


class ConnectionsResponse(BaseModel):
    """Response schema for connected players list."""

    connections: list[ConnectionInfo]


class TickStatusResponse(BaseModel):
    """Response schema for tick engine status."""

    tick_number: int
    is_running: bool
    tick_rate_ms: int


class EntityCreateRequest(BaseModel):
    """Request schema for entity creation (debug only)."""

    zone_id: UUID
    x: int
    y: int
    width: int = 1
    height: int = 1
    metadata: dict[str, Any] | None = None


class EntityUpdateRequest(BaseModel):
    """Request schema for entity update (debug only)."""

    x: int | None = None
    y: int | None = None
    width: int | None = None
    height: int | None = None
    metadata: dict[str, Any] | None = None


# Routes
@router.post("/entities", response_model=EntityResponse, status_code=status.HTTP_201_CREATED)
async def create_entity(
    request: EntityCreateRequest,
    player: Annotated[Player, Depends(get_debug_player)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EntityResponse:
    """
    Create an entity for debugging purposes.
    """
    # Verify zone exists
    result = await db.execute(
        select(Zone).where(Zone.id == request.zone_id)
    )
    zone = result.scalar_one_or_none()

    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )

    # Validate entity bounds within zone
    if request.x < 0 or request.y < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Entity position cannot be negative",
        )
    if request.x + request.width > zone.width or request.y + request.height > zone.height:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Entity must be within zone bounds",
        )

    # Create entity
    entity = Entity(
        zone_id=request.zone_id,
        x=request.x,
        y=request.y,
        width=request.width,
        height=request.height,
        metadata_=request.metadata or {},
    )
    db.add(entity)
    await db.flush()
    await db.refresh(entity)

    return EntityResponse(
        id=entity.id,
        zone_id=entity.zone_id,
        x=entity.x,
        y=entity.y,
        width=entity.width,
        height=entity.height,
        metadata=entity.metadata_,
    )


@router.patch("/entities/{entity_id}", response_model=EntityResponse)
async def update_entity(
    entity_id: UUID,
    request: EntityUpdateRequest,
    player: Annotated[Player, Depends(get_debug_player)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EntityResponse:
    """
    Update an entity for debugging purposes.
    """
    result = await db.execute(
        select(Entity).where(Entity.id == entity_id)
    )
    entity = result.scalar_one_or_none()

    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )

    # Get zone for bounds validation
    zone_result = await db.execute(
        select(Zone).where(Zone.id == entity.zone_id)
    )
    zone = zone_result.scalar_one()

    # Calculate new position/size (use existing values if not provided)
    new_x = request.x if request.x is not None else entity.x
    new_y = request.y if request.y is not None else entity.y
    new_width = request.width if request.width is not None else entity.width
    new_height = request.height if request.height is not None else entity.height

    # Validate bounds
    if new_x < 0 or new_y < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Entity position cannot be negative",
        )
    if new_x + new_width > zone.width or new_y + new_height > zone.height:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Entity must be within zone bounds",
        )

    # Update fields if provided
    if request.x is not None:
        entity.x = request.x
    if request.y is not None:
        entity.y = request.y
    if request.width is not None:
        entity.width = request.width
    if request.height is not None:
        entity.height = request.height
    if request.metadata is not None:
        entity.metadata_ = request.metadata

    await db.flush()
    await db.refresh(entity)

    return EntityResponse(
        id=entity.id,
        zone_id=entity.zone_id,
        x=entity.x,
        y=entity.y,
        width=entity.width,
        height=entity.height,
        metadata=entity.metadata_,
    )


@router.delete("/entities/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity(
    entity_id: UUID,
    player: Annotated[Player, Depends(get_debug_player)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """
    Delete an entity for debugging purposes.
    """
    result = await db.execute(
        select(Entity).where(Entity.id == entity_id)
    )
    entity = result.scalar_one_or_none()

    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )

    await db.delete(entity)
    await db.flush()


@router.post("/tick/pause")
async def pause_tick(
    player: Annotated[Player, Depends(get_debug_player)],
) -> dict:
    """
    Pause the tick engine.
    """
    # Import here to avoid circular dependency
    from grid_backend.tick_engine import get_tick_engine

    engine = get_tick_engine()
    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tick engine not initialized",
        )

    engine.pause()
    return {"message": "Tick engine paused", "tick_number": engine.tick_number}


@router.post("/tick/resume")
async def resume_tick(
    player: Annotated[Player, Depends(get_debug_player)],
) -> dict:
    """
    Resume the tick engine.
    """
    from grid_backend.tick_engine import get_tick_engine

    engine = get_tick_engine()
    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tick engine not initialized",
        )

    engine.resume()
    return {"message": "Tick engine resumed", "tick_number": engine.tick_number}


@router.post("/tick/step")
async def step_tick(
    player: Annotated[Player, Depends(get_debug_player)],
) -> dict:
    """
    Trigger a single tick when the engine is paused.
    """
    from grid_backend.tick_engine import get_tick_engine

    engine = get_tick_engine()
    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tick engine not initialized",
        )

    if engine.is_running:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tick engine must be paused to step manually",
        )

    await engine.step()
    return {"message": "Tick executed", "tick_number": engine.tick_number}


@router.get("/tick/status", response_model=TickStatusResponse)
async def get_tick_status(
    player: Annotated[Player, Depends(get_debug_player)],
) -> TickStatusResponse:
    """
    Get the current tick engine status.
    """
    from grid_backend.tick_engine import get_tick_engine
    from grid_backend.config import get_settings

    engine = get_tick_engine()
    settings = get_settings()

    if engine is None:
        return TickStatusResponse(
            tick_number=0,
            is_running=False,
            tick_rate_ms=settings.tick_rate_ms,
        )

    return TickStatusResponse(
        tick_number=engine.tick_number,
        is_running=engine.is_running,
        tick_rate_ms=settings.tick_rate_ms,
    )


@router.get("/zones/{zone_id}/state", response_model=ZoneStateResponse)
async def get_zone_state(
    zone_id: UUID,
    player: Annotated[Player, Depends(get_debug_player)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ZoneStateResponse:
    """
    Inspect full zone state including all entities.
    """
    result = await db.execute(
        select(Zone)
        .where(Zone.id == zone_id)
        .options(selectinload(Zone.entities))
    )
    zone = result.scalar_one_or_none()

    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )

    return ZoneStateResponse(
        id=zone.id,
        name=zone.name,
        width=zone.width,
        height=zone.height,
        metadata=zone.metadata_,
        entities=[
            EntityResponse(
                id=entity.id,
                zone_id=entity.zone_id,
                x=entity.x,
                y=entity.y,
                width=entity.width,
                height=entity.height,
                metadata=entity.metadata_,
            )
            for entity in zone.entities
        ],
    )


@router.get("/entities/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: UUID,
    player: Annotated[Player, Depends(get_debug_player)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EntityResponse:
    """
    Inspect a specific entity's state.
    """
    result = await db.execute(
        select(Entity).where(Entity.id == entity_id)
    )
    entity = result.scalar_one_or_none()

    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )

    return EntityResponse(
        id=entity.id,
        zone_id=entity.zone_id,
        x=entity.x,
        y=entity.y,
        width=entity.width,
        height=entity.height,
        metadata=entity.metadata_,
    )


class EntitiesInAreaResponse(BaseModel):
    """Response schema for entities in area query."""
    entities: list[EntityResponse]


@router.get("/zones/{zone_id}/entities", response_model=EntitiesInAreaResponse)
async def get_entities_in_area(
    zone_id: UUID,
    player: Annotated[Player, Depends(get_debug_player)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x1: int = 0,
    y1: int = 0,
    x2: int | None = None,
    y2: int | None = None,
) -> EntitiesInAreaResponse:
    """
    Query entities in a zone, optionally filtered by area.
    Returns entities that overlap with the specified rectangular area.
    If x2/y2 not provided, returns all entities in zone.
    """
    # Verify zone exists
    result = await db.execute(
        select(Zone).where(Zone.id == zone_id)
    )
    zone = result.scalar_one_or_none()

    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )

    # Get all entities in zone
    result = await db.execute(
        select(Entity).where(Entity.zone_id == zone_id)
    )
    all_entities = result.scalars().all()

    # If no area filter, return all
    if x2 is None or y2 is None:
        return EntitiesInAreaResponse(
            entities=[
                EntityResponse(
                    id=e.id,
                    zone_id=e.zone_id,
                    x=e.x,
                    y=e.y,
                    width=e.width,
                    height=e.height,
                    metadata=e.metadata_,
                )
                for e in all_entities
            ]
        )

    # Filter by rectangular overlap
    # Entity is at (ex, ey) with size (ew, eh)
    # Query area is (x1, y1) to (x2, y2)
    # Overlap if: ex < x2 and ex + ew > x1 and ey < y2 and ey + eh > y1
    overlapping = []
    for e in all_entities:
        ex, ey, ew, eh = e.x, e.y, e.width, e.height
        # For zero-dimension entities, treat as a point
        if ew == 0 and eh == 0:
            if x1 <= ex <= x2 and y1 <= ey <= y2:
                overlapping.append(e)
        else:
            # Standard rectangle overlap check
            if ex < x2 and ex + ew > x1 and ey < y2 and ey + eh > y1:
                overlapping.append(e)

    return EntitiesInAreaResponse(
        entities=[
            EntityResponse(
                id=e.id,
                zone_id=e.zone_id,
                x=e.x,
                y=e.y,
                width=e.width,
                height=e.height,
                metadata=e.metadata_,
            )
            for e in overlapping
        ]
    )


@router.get("/connections", response_model=ConnectionsResponse)
async def get_connections(
    player: Annotated[Player, Depends(get_debug_player)],
) -> ConnectionsResponse:
    """
    List all connected players and their subscribed zones.
    """
    from grid_backend.websocket import get_connection_manager

    manager = get_connection_manager()
    if manager is None:
        return ConnectionsResponse(connections=[])

    connections = []
    for player_id, info in manager.get_all_connections().items():
        connections.append(
            ConnectionInfo(
                player_id=player_id,
                username=info.username,
                zone_id=info.zone_id,
            )
        )

    return ConnectionsResponse(connections=connections)
