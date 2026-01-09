"""
Zone model for Grid Backend.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from grid_backend.database import Base

if TYPE_CHECKING:
    from grid_backend.models.entity import Entity


class Zone(Base):
    """
    Zone model representing a 2D grid area.
    Zones contain entities and have configurable dimensions.
    """

    __tablename__ = "zones"

    id: Mapped[Uuid] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    width: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    height: Mapped[int] = mapped_column(
        Integer,
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
    entities: Mapped[list["Entity"]] = relationship(
        "Entity",
        back_populates="zone",
        cascade="all, delete-orphan",
    )

    def is_position_valid(self, x: int, y: int) -> bool:
        """Check if a position is within zone bounds."""
        return 0 <= x < self.width and 0 <= y < self.height

    def is_entity_in_bounds(self, x: int, y: int, width: int, height: int) -> bool:
        """Check if an entity (with dimensions) fits within zone bounds."""
        # Zero-dimension entities just need valid position
        if width == 0 and height == 0:
            return self.is_position_valid(x, y)
        # Entities with dimensions need to fit entirely within bounds
        return (
            0 <= x < self.width
            and 0 <= y < self.height
            and x + width <= self.width
            and y + height <= self.height
        )

    def __repr__(self) -> str:
        return f"<Zone(id={self.id}, name={self.name}, size={self.width}x{self.height})>"
