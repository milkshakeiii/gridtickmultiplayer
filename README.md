# Grid Backend

A minimal, generic Python backend framework for tick-based 2D grid multiplayer games with swappable game logic modules.

## Overview

Grid Backend is designed for "massively" multiplayer persistent worlds with a 1-second tick rate, inspired by EVE Online's authoritative server architecture. The framework handles infrastructure (authentication, connections, persistence, tick loop) while game-specific logic is implemented via pluggable modules conforming to a defined interface.

### Key Features

- **Tick-based game loop**: Configurable tick rate (default 1 second) with accurate timing
- **WebSocket real-time communication**: Players connect via WebSocket for game state updates
- **Zone-based world**: 2D grid zones with entity management
- **Swappable game logic**: Implement your game rules in a pluggable module
- **Player authentication**: Username/password with session tokens
- **Persistence**: SQLite database for zones, entities, and player data (easy setup)
- **Debug tools**: Pause/resume ticks, inspect state, manual tick stepping

## Architecture Principles

1. **Minimal Framework**: The framework does as little as possible. All game-specific logic lives in swappable modules.
2. **Opaque Intents**: Intents are JSON blobs opaque to the framework. Game logic defines, validates, and resolves them.
3. **Single Shard**: One persistent world with unique zones. No instancing.
4. **One Ruleset Per Instance**: Each running server instance loads exactly one game logic module.
5. **Authoritative Server**: Server is the source of truth. No client prediction needed due to slow tick rate.

## Prerequisites

- Python 3.11 or higher
- Virtual environment (venv or similar)

## Quick Start

1. **Clone and setup**:
   ```bash
   git clone https://github.com/milkshakeiii/gridtickmultiplayer.git
   cd gridtickmultiplayer
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   ```

2. **Start the server**:
   ```bash
   source venv/bin/activate
   uvicorn grid_backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Access the API**:
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc
   - WebSocket: ws://localhost:8000/ws

## Configuration

Edit the `.env` file to customize settings:

```env
DATABASE_URL=sqlite+aiosqlite:///./gridbackend.db
SECRET_KEY=your-secret-key-here
DEBUG_MODE=true
TICK_RATE_MS=1000
SESSION_TIMEOUT_SECONDS=0
MIN_PASSWORD_LENGTH=8
GAME_MODULE=grid_backend.game_modules.example
HOST=0.0.0.0
PORT=8000
```

## API Endpoints

### REST - Authentication
- `POST /api/auth/register` - Register new player
- `POST /api/auth/login` - Login and get session token
- `POST /api/auth/logout` - Logout and invalidate session
- `GET /api/auth/me` - Get current player info

### REST - Zones
- `GET /api/zones` - List all zones
- `GET /api/zones/{zone_id}` - Get zone details
- `POST /api/zones` - Create zone (debug only)
- `DELETE /api/zones/{zone_id}` - Delete zone (debug only)

### REST - Debug (requires debug role)
- `POST /api/debug/tick/pause` - Pause tick engine
- `POST /api/debug/tick/resume` - Resume tick engine
- `POST /api/debug/tick/step` - Trigger single tick when paused
- `GET /api/debug/zones/{zone_id}/state` - Inspect zone state
- `GET /api/debug/entities/{entity_id}` - Inspect entity state
- `GET /api/debug/connections` - View connected players

### WebSocket
- `WS /ws` - Main game connection

#### Client to Server Messages
```json
{"type": "subscribe", "zone_id": "..."}
{"type": "intent", "data": {...}}
```

#### Server to Client Messages
```json
{"type": "subscribed", "zone_id": "..."}
{"type": "tick", "tick_number": 123, "state": {...}}
{"type": "error", "message": "..."}
```

## Game Logic Module Interface

Game logic modules must implement this Python protocol:

```python
from typing import Protocol
from uuid import UUID
from dataclasses import dataclass

@dataclass
class TickResult:
    entity_creates: list[EntityCreate]
    entity_updates: list[EntityUpdate]
    entity_deletes: list[UUID]
    extras: dict  # Non-entity payload (events, notifications)

class GameLogicModule(Protocol):
    async def on_init(self, framework: FrameworkAPI) -> None:
        """Called once when module is loaded. Use for setup (e.g., create zones)."""
        ...

    def on_tick(
        self,
        zone_id: UUID,
        entities: list[Entity],
        intents: list[Intent],
        tick_number: int
    ) -> TickResult:
        """Called each tick for each zone. Returns entity deltas + extras."""
        ...

    def get_player_state(
        self,
        zone_id: UUID,
        player_id: UUID,
        full_state: dict
    ) -> dict:
        """Filter/transform state for a specific player (fog-of-war)."""
        ...
```

The framework builds the authoritative entity snapshot after applying deltas, then calls `get_player_state` for each subscriber to apply fog-of-war/redaction.

### Entity Ownership

Entities can have an `owner_id` linking them to a player. When creating entities via `EntityCreate`, set the `owner_id` field:

```python
EntityCreate(
    x=10, y=10,
    owner_id=intent.player_id,  # Link to creating player
    metadata={"char": "@"}
)
```

When a player disconnects, the framework automatically queues a synthetic `owner_disconnect` intent:

```python
{"action": "owner_disconnect", "player_id": "..."}
```

Game modules should handle this intent to clean up player-owned entities:

```python
def on_tick(self, zone_id, entities, intents, tick_number) -> TickResult:
    deletes = []
    for intent in intents:
        if intent.data.get("action") == "owner_disconnect":
            player_id = UUID(intent.data["player_id"])
            for entity in entities:
                if entity.owner_id == player_id:
                    deletes.append(entity.id)
    return TickResult(entity_deletes=deletes, ...)
```

### External Game Modules

Game modules can live in a separate repository. Options:

**1. Install as pip package (recommended)**

Your game module repo needs a minimal `pyproject.toml`:

```toml
[project]
name = "my-game-module"
version = "0.1.0"
dependencies = []

[project.optional-dependencies]
dev = ["gridtickmultiplayer"]  # For type hints during development
```

Then install and configure:

```bash
# Install from git
pip install git+https://github.com/you/my-game-module.git

# Or install locally for development
pip install -e /path/to/my-game-module

# Configure in .env
GAME_MODULE=my_game_module.main
```

**2. PYTHONPATH**

```bash
PYTHONPATH=/path/to/my-game-repo:$PYTHONPATH python -m grid_backend.main
```

**3. Symlink into game_modules/**

```bash
ln -s /path/to/my-game-repo/my_module grid_backend/game_modules/my_module
# GAME_MODULE=grid_backend.game_modules.my_module
```

Your module must export a `game_module` instance implementing the `GameLogicModule` protocol:

```python
# my_game_module/main.py
class MyGame:
    async def on_init(self, framework): ...
    def on_tick(self, zone_id, entities, intents, tick_number): ...
    def get_player_state(self, zone_id, player_id, full_state): ...

game_module = MyGame()
```

## Project Structure

```
gridtickmultiplayer/
├── grid_backend/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry
│   ├── config.py            # Configuration management
│   ├── database.py          # Database connection and session
│   ├── models/              # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── player.py
│   │   ├── session.py
│   │   ├── zone.py
│   │   └── entity.py
│   ├── api/                 # REST API routes
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── zones.py
│   │   └── debug.py
│   ├── websocket/           # WebSocket handling
│   │   ├── __init__.py
│   │   ├── handler.py
│   │   └── manager.py
│   ├── tick_engine/         # Tick loop implementation
│   │   ├── __init__.py
│   │   └── engine.py
│   ├── game_logic/          # Game logic interface
│   │   ├── __init__.py
│   │   ├── protocol.py
│   │   └── loader.py
│   └── game_modules/        # Example game modules
│       ├── __init__.py
│       └── example.py
├── tests/                   # Test suite
├── .env.example             # Example configuration
├── init.sh                  # Setup script
├── run.sh                   # Run script
├── requirements.txt         # Python dependencies
├── .env                     # Environment configuration
└── README.md
```

## User Roles

### Player
- Can register and login
- Can connect via WebSocket
- Can subscribe to one zone at a time
- Can submit intents
- Can receive tick state updates

### Debug
- All player permissions
- Can pause/resume tick engine
- Can inspect zone state
- Can inspect entity state
- Can view connected players

Debug access is for development only and controlled via config/environment.

## Database Schema

### Tables
- **players**: id, username, password_hash, created_at, last_login
- **sessions**: id, player_id, token, created_at, expires_at
- **zones**: id, name, width, height, metadata, created_at, updated_at
- **entities**: id, zone_id, owner_id, x, y, width, height, metadata, created_at, updated_at

The `owner_id` field links entities to their owning player, enabling automatic cleanup when players disconnect.

## Development

### Running Tests
```bash
pytest
```

### Running with Debug Mode
```bash
DEBUG_MODE=true uvicorn grid_backend.main:app --reload
```

## License

[Add your license here]
