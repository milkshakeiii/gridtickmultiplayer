"""
Tests for authentication endpoints.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """Test successful player registration."""
    response = await client.post(
        "/api/auth/register",
        json={"username": "newuser", "password": "password123"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["username"] == "newuser"


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient):
    """Test registration fails for duplicate username."""
    # First registration
    await client.post(
        "/api/auth/register",
        json={"username": "duplicate", "password": "password123"},
    )

    # Duplicate registration
    response = await client.post(
        "/api/auth/register",
        json={"username": "duplicate", "password": "different123"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient):
    """Test registration fails for short password."""
    response = await client.post(
        "/api/auth/register",
        json={"username": "shortpass", "password": "short"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Test successful login."""
    # Register first
    await client.post(
        "/api/auth/register",
        json={"username": "logintest", "password": "password123"},
    )

    # Login
    response = await client.post(
        "/api/auth/login",
        json={"username": "logintest", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert "player_id" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """Test login fails with wrong password."""
    # Register first
    await client.post(
        "/api/auth/register",
        json={"username": "wrongpass", "password": "password123"},
    )

    # Login with wrong password
    response = await client.post(
        "/api/auth/login",
        json={"username": "wrongpass", "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Test login fails for non-existent user."""
    response = await client.post(
        "/api/auth/login",
        json={"username": "nonexistent", "password": "password123"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(client: AsyncClient):
    """Test getting current player info when authenticated."""
    # Register and login
    await client.post(
        "/api/auth/register",
        json={"username": "metest", "password": "password123"},
    )
    login_response = await client.post(
        "/api/auth/login",
        json={"username": "metest", "password": "password123"},
    )
    token = login_response.json()["token"]

    # Get current player
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["username"] == "metest"


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient):
    """Test getting current player info without authentication."""
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    """Test logout invalidates token."""
    # Register and login
    await client.post(
        "/api/auth/register",
        json={"username": "logouttest", "password": "password123"},
    )
    login_response = await client.post(
        "/api/auth/login",
        json={"username": "logouttest", "password": "password123"},
    )
    token = login_response.json()["token"]

    # Logout
    response = await client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    # Try to use token after logout
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
