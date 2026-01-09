"""
Authentication API routes for Grid Backend.
"""

from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import bcrypt
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from grid_backend.config import Settings, get_settings
from grid_backend.database import get_db
from grid_backend.models.player import Player
from grid_backend.models.session import Session
from grid_backend.api.utils import create_token

router = APIRouter()
security = HTTPBearer(auto_error=False)


# Request/Response schemas
class RegisterRequest(BaseModel):
    """Request schema for player registration."""

    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(...)


class LoginRequest(BaseModel):
    """Request schema for player login."""

    username: str = Field(...)
    password: str = Field(...)


class PlayerResponse(BaseModel):
    """Response schema for player info."""

    id: UUID
    username: str
    is_debug: bool
    created_at: datetime
    last_login: datetime | None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Response schema for login success."""

    token: str
    player_id: UUID


# Helper functions
def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    # bcrypt has a 72-byte limit, so truncate if needed
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    # bcrypt has a 72-byte limit, so truncate if needed (must match hash_password)
    password_bytes = plain_password.encode('utf-8')[:72]
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


async def get_current_player(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Player:
    """
    Dependency to get the current authenticated player.
    Raises HTTPException if not authenticated or token is invalid/expired.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Find session by token
    result = await db.execute(
        select(Session).where(Session.token == token)
    )
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if session.is_expired():
        # Clean up expired session
        await db.delete(session)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Load and return the player
    result = await db.execute(
        select(Player).where(Player.id == session.player_id)
    )
    player = result.scalar_one_or_none()

    if player is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Player not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return player


async def get_debug_player(
    player: Annotated[Player, Depends(get_current_player)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Player:
    """
    Dependency to get current player with debug access.
    Raises HTTPException if player doesn't have debug role.
    """
    if not settings.debug_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debug mode is not enabled",
        )

    if not player.is_debug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debug access required",
        )

    return player


# Routes
@router.post("/register", response_model=PlayerResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Player:
    """
    Register a new player.
    Returns the created player information.
    """
    # Validate password length
    if len(request.password) < settings.min_password_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {settings.min_password_length} characters",
        )

    # Check if username already exists
    result = await db.execute(
        select(Player).where(Player.username == request.username)
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    # Check if user should get debug access
    is_debug = bool(settings.debug_user and request.username == settings.debug_user)

    # Create new player
    player = Player(
        username=request.username,
        password_hash=hash_password(request.password),
        is_debug=is_debug,
    )
    db.add(player)
    await db.flush()
    await db.refresh(player)

    return player


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """
    Login with username and password.
    Returns a session token for authentication.
    """
    # Find player by username
    result = await db.execute(
        select(Player).where(Player.username == request.username)
    )
    player = result.scalar_one_or_none()

    # Generic error message to prevent info leakage
    if player is None or not verify_password(request.password, player.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Update last login
    player.last_login = datetime.utcnow()

    # Create session token
    token = create_token(player.id, settings.secret_key)

    # Calculate expiration if configured
    expires_at = None
    if settings.session_timeout_seconds > 0:
        expires_at = datetime.utcnow() + timedelta(seconds=settings.session_timeout_seconds)

    # Create session record
    session = Session(
        player_id=player.id,
        token=token,
        expires_at=expires_at,
    )
    db.add(session)
    await db.flush()

    return TokenResponse(token=token, player_id=player.id)


@router.post("/logout")
async def logout(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """
    Logout and invalidate the current session.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    token = credentials.credentials

    # Find and delete session
    result = await db.execute(
        select(Session).where(Session.token == token)
    )
    session = result.scalar_one_or_none()

    if session is not None:
        await db.delete(session)
        await db.commit()

    return {"message": "Logged out successfully"}


@router.get("/me", response_model=PlayerResponse)
async def get_me(
    player: Annotated[Player, Depends(get_current_player)],
) -> Player:
    """
    Get the current authenticated player's information.
    """
    return player
