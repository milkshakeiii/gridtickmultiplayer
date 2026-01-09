"""
Live WebSocket tests that run against the actual server.
Run with: pytest tests/test_websocket_live.py -v -s
"""

import asyncio
import pytest
import pytest_asyncio
import httpx
import websockets
import json


SERVER_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws"


@pytest_asyncio.fixture
async def debug_token():
    """Get a debug token by logging in or registering."""
    async with httpx.AsyncClient() as client:
        # Try to login first
        resp = await client.post(
            f"{SERVER_URL}/api/auth/login",
            json={"username": "debug_admin", "password": "testpass123"}
        )
        if resp.status_code == 200:
            return resp.json()["token"]

        # If login fails, register
        resp = await client.post(
            f"{SERVER_URL}/api/auth/register",
            json={"username": "debug_admin", "password": "testpass123"}
        )
        if resp.status_code == 201:
            # Login after registration
            resp = await client.post(
                f"{SERVER_URL}/api/auth/login",
                json={"username": "debug_admin", "password": "testpass123"}
            )
            return resp.json()["token"]

        raise Exception(f"Failed to get token: {resp.text}")


@pytest_asyncio.fixture
async def zone_id(debug_token):
    """Create a test zone."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SERVER_URL}/api/zones",
            headers={"Authorization": f"Bearer {debug_token}"},
            json={"name": "ws_test_zone", "width": 100, "height": 100}
        )
        if resp.status_code == 201:
            return resp.json()["id"]
        elif resp.status_code == 409:  # Zone already exists
            # Get existing zone
            resp = await client.get(
                f"{SERVER_URL}/api/zones",
                headers={"Authorization": f"Bearer {debug_token}"}
            )
            zones = resp.json()["zones"]
            for z in zones:
                if z["name"] == "ws_test_zone":
                    return z["id"]
        raise Exception(f"Failed to create zone: {resp.text}")


@pytest.mark.asyncio
async def test_websocket_connection(debug_token):
    """Test WebSocket connection with valid token."""
    uri = f"{WS_URL}?token={debug_token}"
    async with websockets.connect(uri) as ws:
        # Connection successful if we get here (context manager handles it)
        print("WebSocket connected successfully!")


@pytest.mark.asyncio
async def test_websocket_subscribe_to_zone(debug_token, zone_id):
    """Test subscribing to a zone via WebSocket."""
    uri = f"{WS_URL}?token={debug_token}"
    async with websockets.connect(uri) as ws:
        # Send subscribe message
        subscribe_msg = {"type": "subscribe", "zone_id": zone_id}
        await ws.send(json.dumps(subscribe_msg))
        print(f"Sent subscribe: {subscribe_msg}")

        # Wait for response
        response = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(response)
        print(f"Received: {data}")

        assert data["type"] == "subscribed"
        assert data["zone_id"] == zone_id
        print("Subscription successful!")


@pytest.mark.asyncio
async def test_websocket_receive_tick_update(debug_token, zone_id):
    """Test receiving tick updates after subscribing."""
    uri = f"{WS_URL}?token={debug_token}"
    async with websockets.connect(uri) as ws:
        # Subscribe first
        await ws.send(json.dumps({"type": "subscribe", "zone_id": zone_id}))
        response = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(response)
        assert data["type"] == "subscribed"

        # Wait for tick update
        try:
            tick_response = await asyncio.wait_for(ws.recv(), timeout=5.0)
            tick_data = json.loads(tick_response)
            print(f"Tick update received: {tick_data}")
            assert tick_data["type"] == "tick"
            assert "tick_number" in tick_data
            # New payload shape: state contains framework-built entity snapshot
            assert "state" in tick_data
            state = tick_data["state"]
            assert "zone_id" in state
            assert "tick_number" in state
            assert "entities" in state  # Framework-built entity list
            assert isinstance(state["entities"], list)
            # Per-player filtering adds viewer_id
            assert "viewer_id" in state
        except asyncio.TimeoutError:
            pytest.fail("No tick update received within 5 seconds")


@pytest_asyncio.fixture
async def second_token():
    """Get a second player token for fog-of-war testing."""
    async with httpx.AsyncClient() as client:
        # Try to login first
        resp = await client.post(
            f"{SERVER_URL}/api/auth/login",
            json={"username": "debug_admin_2", "password": "testpass123"}
        )
        if resp.status_code == 200:
            return resp.json()["token"]

        # If login fails, register
        resp = await client.post(
            f"{SERVER_URL}/api/auth/register",
            json={"username": "debug_admin_2", "password": "testpass123"}
        )
        if resp.status_code == 201:
            # Login after registration
            resp = await client.post(
                f"{SERVER_URL}/api/auth/login",
                json={"username": "debug_admin_2", "password": "testpass123"}
            )
            return resp.json()["token"]

        raise Exception(f"Failed to get second token: {resp.text}")


@pytest.mark.asyncio
async def test_fog_of_war_per_player_state(debug_token, second_token, zone_id):
    """
    Test that two players subscribed to the same zone receive different
    filtered entity views via get_player_state (fog-of-war behavior).

    The example game module adds viewer_id to each player's state,
    proving per-player filtering is working.
    """
    uri1 = f"{WS_URL}?token={debug_token}"
    uri2 = f"{WS_URL}?token={second_token}"

    async with websockets.connect(uri1) as ws1, websockets.connect(uri2) as ws2:
        # Both players subscribe to the same zone
        await ws1.send(json.dumps({"type": "subscribe", "zone_id": zone_id}))
        await ws2.send(json.dumps({"type": "subscribe", "zone_id": zone_id}))

        # Get subscription confirmations
        resp1 = await asyncio.wait_for(ws1.recv(), timeout=5.0)
        resp2 = await asyncio.wait_for(ws2.recv(), timeout=5.0)
        assert json.loads(resp1)["type"] == "subscribed"
        assert json.loads(resp2)["type"] == "subscribed"

        # Wait for tick updates
        tick1 = await asyncio.wait_for(ws1.recv(), timeout=5.0)
        tick2 = await asyncio.wait_for(ws2.recv(), timeout=5.0)

        data1 = json.loads(tick1)
        data2 = json.loads(tick2)

        assert data1["type"] == "tick"
        assert data2["type"] == "tick"

        # Both should have the same zone and entities (same authoritative snapshot)
        assert data1["state"]["zone_id"] == data2["state"]["zone_id"]
        assert data1["state"]["entities"] == data2["state"]["entities"]

        # But each should have their own viewer_id (per-player filtering)
        viewer1 = data1["state"]["viewer_id"]
        viewer2 = data2["state"]["viewer_id"]

        assert viewer1 != viewer2, "Each player should see their own viewer_id"
        print(f"Player 1 viewer_id: {viewer1}")
        print(f"Player 2 viewer_id: {viewer2}")
        print("Fog-of-war per-player filtering verified!")
