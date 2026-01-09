"""
Player model for Grid Backend.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import String, DateTime, Boolean, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from grid_backend.database import Base

if TYPE_CHECKING:
    from grid_backend.models.session import Session


class Player(Base):
    """
    Player account model.
    Stores authentication credentials and account metadata.
    """

    __tablename__ = "players"

    id: Mapped[Uuid] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    is_debug: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    # Relationships
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="player",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Player(id={self.id}, username={self.username})>"
