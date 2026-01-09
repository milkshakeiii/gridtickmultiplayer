"""
Session model for Grid Backend.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from grid_backend.database import Base

if TYPE_CHECKING:
    from grid_backend.models.player import Player


class Session(Base):
    """
    Session model for player authentication.
    Stores session tokens and expiration.
    """

    __tablename__ = "sessions"

    id: Mapped[Uuid] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )
    player_id: Mapped[Uuid] = mapped_column(
        Uuid,
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
    )
    token: Mapped[str] = mapped_column(
        String(500),
        unique=True,
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    # Relationships
    player: Mapped["Player"] = relationship(
        "Player",
        back_populates="sessions",
    )

    def is_expired(self) -> bool:
        """Check if session has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, player_id={self.player_id})>"
