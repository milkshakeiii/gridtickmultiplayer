"""
Entity model for Grid Backend.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from grid_backend.database import Base

if TYPE_CHECKING:
    from grid_backend.models.zone import Zone


class Entity(Base):
    """
    Entity model representing objects in a zone.
    Entities have position, dimensions, and arbitrary metadata.
    Zero-dimension (0x0) entities are allowed for markers, equipment, etc.
    """

    __tablename__ = "entities"

    id: Mapped[Uuid] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )
    zone_id: Mapped[Uuid] = mapped_column(
        Uuid,
        ForeignKey("zones.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    owner_id: Mapped[Uuid | None] = mapped_column(
        Uuid,
        ForeignKey("players.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    x: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    y: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    width: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    height: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    zone: Mapped["Zone"] = relationship(
        "Zone",
        back_populates="entities",
    )

    def overlaps(self, x: int, y: int, width: int, height: int) -> bool:
        """
        Check if this entity overlaps with a rectangular area.
        Zero-dimension entities overlap only if their position is within the area.
        """
        # Zero-dimension entities - check if point is in the query area
        if self.width == 0 and self.height == 0:
            return (
                x <= self.x < x + width
                and y <= self.y < y + height
            )

        # Query area is a point - check if it's within this entity
        if width == 0 and height == 0:
            return (
                self.x <= x < self.x + self.width
                and self.y <= y < self.y + self.height
            )

        # Both have dimensions - check rectangle overlap
        return (
            self.x < x + width
            and self.x + self.width > x
            and self.y < y + height
            and self.y + self.height > y
        )

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        """Return entity bounds as (x, y, width, height)."""
        return (self.x, self.y, self.width, self.height)

    def __repr__(self) -> str:
        return (
            f"<Entity(id={self.id}, zone_id={self.zone_id}, "
            f"pos=({self.x}, {self.y}), size={self.width}x{self.height})>"
        )
