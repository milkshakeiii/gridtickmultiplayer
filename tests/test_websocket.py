#!/usr/bin/env python3
"""Test WebSocket zone subscription."""

import asyncio
import sys
import json
import websockets

async def test_websocket_subscription(token: str, zone_id: str):
    """Test WebSocket connection and zone subscription."""
    uri = f"ws://localhost:8000/ws?token={token}"

    try:
        async with websockets.connect(uri) as ws:
            print(f"Connected to WebSocket")

            # Subscribe to zone
            subscribe_msg = {
                "type": "subscribe",
                "zone_id": zone_id
            }
            await ws.send(json.dumps(subscribe_msg))
            print(f"Sent subscribe message: {subscribe_msg}")

            # Wait for response
            response = await asyncio.wait_for(ws.recv(), timeout=5.0)
            print(f"Received: {response}")

            # Wait for a tick update
            try:
                tick_update = await asyncio.wait_for(ws.recv(), timeout=3.0)
                print(f"Tick update: {tick_update}")
            except asyncio.TimeoutError:
                print("No tick update received within 3 seconds")

            return True
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: test_websocket.py <token> <zone_id>")
        sys.exit(1)

    token = sys.argv[1]
    zone_id = sys.argv[2]

    result = asyncio.run(test_websocket_subscription(token, zone_id))
    sys.exit(0 if result else 1)
