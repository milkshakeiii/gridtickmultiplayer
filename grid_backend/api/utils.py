"""
Utility functions for the API module.
"""

import secrets
from datetime import datetime, timedelta
from uuid import UUID

from jose import jwt


def create_token(player_id: UUID, secret_key: str, expires_delta: timedelta | None = None) -> str:
    """
    Create a JWT token for a player.

    Args:
        player_id: The player's UUID
        secret_key: Secret key for signing
        expires_delta: Optional expiration time delta

    Returns:
        JWT token string
    """
    data = {
        "sub": str(player_id),
        "iat": datetime.utcnow(),
        "jti": secrets.token_hex(16),  # Unique token ID
    }

    if expires_delta:
        data["exp"] = datetime.utcnow() + expires_delta

    return jwt.encode(data, secret_key, algorithm="HS256")


def decode_token(token: str, secret_key: str) -> dict | None:
    """
    Decode and verify a JWT token.

    Args:
        token: JWT token string
        secret_key: Secret key for verification

    Returns:
        Decoded token data or None if invalid
    """
    try:
        return jwt.decode(token, secret_key, algorithms=["HS256"])
    except Exception:
        return None
