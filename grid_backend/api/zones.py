"""
Zone management API routes for Grid Backend.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from grid_backend.config import Settings, get_settings
from grid_backend.database import get_db
from grid_backend.models.player import Player
from grid_backend.models.zone import Zone
from grid_backend.api.auth import get_current_player, get_debug_player

router = APIRouter()


# Request/Response schemas
class ZoneCreateRequest(BaseModel):
    """Request schema for zone creation."""

    name: str = Field(..., min_length=1, max_length=100)
    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)
    metadata: dict[str, Any] | None = Field(default=None)


class ZoneResponse(BaseModel):
    """Response schema for zone info."""

    id: UUID
    name: str
    width: int
    height: int
    metadata: dict[str, Any] | None

    class Config:
        from_attributes = True


class ZoneListResponse(BaseModel):
    """Response schema for zone list."""

    zones: list[ZoneResponse]


# Routes
@router.get("", response_model=ZoneListResponse)
async def list_zones(
    player: Annotated[Player, Depends(get_current_player)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ZoneListResponse:
    """
    List all zones.
    """
    result = await db.execute(select(Zone))
    zones = result.scalars().all()

    return ZoneListResponse(
        zones=[
            ZoneResponse(
                id=zone.id,
                name=zone.name,
                width=zone.width,
                height=zone.height,
                metadata=zone.metadata_,
            )
            for zone in zones
        ]
    )


@router.get("/{zone_id}", response_model=ZoneResponse)
async def get_zone(
    zone_id: UUID,
    player: Annotated[Player, Depends(get_current_player)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ZoneResponse:
    """
    Get zone details by ID.
    """
    result = await db.execute(
        select(Zone).where(Zone.id == zone_id)
    )
    zone = result.scalar_one_or_none()

    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )

    return ZoneResponse(
        id=zone.id,
        name=zone.name,
        width=zone.width,
        height=zone.height,
        metadata=zone.metadata_,
    )


@router.post("", response_model=ZoneResponse, status_code=status.HTTP_201_CREATED)
async def create_zone(
    request: ZoneCreateRequest,
    player: Annotated[Player, Depends(get_debug_player)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ZoneResponse:
    """
    Create a new zone.
    Requires debug role.
    """
    # Check if zone name already exists
    result = await db.execute(
        select(Zone).where(Zone.name == request.name)
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Zone name already exists",
        )

    # Create zone
    zone = Zone(
        name=request.name,
        width=request.width,
        height=request.height,
        metadata_=request.metadata or {},
    )
    db.add(zone)
    await db.flush()
    await db.refresh(zone)

    return ZoneResponse(
        id=zone.id,
        name=zone.name,
        width=zone.width,
        height=zone.height,
        metadata=zone.metadata_,
    )


@router.delete("/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_zone(
    zone_id: UUID,
    player: Annotated[Player, Depends(get_debug_player)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """
    Delete a zone and all associated entities.
    Requires debug role.
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

    await db.delete(zone)
    await db.commit()
