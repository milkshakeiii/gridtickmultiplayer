# Grid Backend Patch Plan (Implemented)

## Decisions (locked scope)

- **Database**: Make SQLite the official/default DB for now (easy setup); Postgres can be revisited later.
- **Game module contract**: Framework owns the authoritative entity snapshot. Game modules return entity deltas + non-entity `extras/events`. Per-player visibility is enforced server-side via `get_player_state` (fog-of-war/redaction).
- **Error handling (dev)**: Fail fast on internal errors (tick loop, game logic, DB mutations). Expected network/protocol errors (disconnects, timeouts, invalid client messages) should not crash the server.
- **Compatibility/migration**: None needed (new project).

## Phase 1 — Docs/config align to SQLite

- Update `README.md` to describe SQLite-first setup (`DATABASE_URL=sqlite+aiosqlite:///./gridbackend.db`) and remove “PostgreSQL required” language.
- Update `app_spec.txt` to reflect SQLite as the current target DB.
- Update `init.sh` to generate `.env` with SQLite URL by default and remove Postgres-specific setup steps (or gate them behind an explicit opt-in).
- Update `requirements.txt` to include `aiosqlite`; remove `asyncpg` entirely (Postgres support can be re-added later if needed).

## Phase 2 — Redefine the game-module contract (no redundant entity snapshot)

- Update `app_spec.txt` “Game Logic Module Interface”:
  - `on_tick(...)` returns:
    - entity deltas: creates/updates/deletes (persisted by framework)
    - `extras/events`: arbitrary payload **excluding** an entity snapshot
  - Clarify broadcast pipeline: framework builds post-apply base state → module filters per player.
- Update `grid_backend/game_logic/protocol.py`:
  - Rename/replace `TickResult.broadcast_state` with something like `extras` / `events` (dict payload), explicitly not an entity list.
  - Document that `get_player_state(...)` is the canonical fog-of-war/redaction hook.

## Phase 3 — Make tick broadcasting framework-authored + fog-of-war safe

- Update `grid_backend/tick_engine/engine.py` tick pipeline to:
  1) load zone/entities
  2) call `on_tick(...)`
  3) apply deltas (DB + in-memory consistency)
  4) build `base_state` from authoritative post-apply entities (includes creates/deletes same tick)
  5) merge in `result.extras/events`
  6) per subscriber: call `get_player_state(...)` and send that (never send unredacted base state)
- Ensure “same-tick correctness” for creates/deletes by either:
  - updating the in-memory entity list as you apply deltas, or
  - re-querying entities after apply/commit for the zone before building `base_state`.

## Phase 4 — Fix intent-queue concurrency

- Update `grid_backend/tick_engine/engine.py` so intent enqueue/dequeue can’t race (make `queue_intent` lock-protected; likely `async def queue_intent(...)` using `_intent_lock`).
- Update `grid_backend/websocket/handler.py` to `await` intent enqueue before acknowledging `intent_received`.

## Phase 5 — Fail-fast on internal errors

- Update `grid_backend/tick_engine/engine.py` to stop swallowing exceptions in the tick loop / zone processing / game logic; let errors propagate.
- Ensure a tick-task failure takes down the server (not just "silently stops ticking") so bugs are immediately visible.
- Narrow exception handling to *expected* network/protocol failures only (non-fatal):
  - WebSocket disconnects (`WebSocketDisconnect`)
  - send timeouts (`asyncio.TimeoutError`)
  - connection reset/broken pipe type I/O failures (best-effort cleanup)
  - invalid client messages (missing fields/unknown message types) should yield an error response, not a process crash.
  - invalid JSON payloads should **close immediately** with an appropriate WebSocket close code (e.g. 1007) and not be treated as internal errors.

## Phase 6 — Reconnect safety (prevent old connection from killing the new one)

- Update `grid_backend/websocket/manager.py`:
  - add a unique `connection_id` to `ConnectionInfo`.
  - make disconnect/unsubscribe operations conditional on `(player_id, connection_id)` so stale handlers can’t disconnect a newer socket.
  - best-effort close the old websocket when a new connection for the same player is established.
- Update `grid_backend/websocket/handler.py` and `grid_backend/main.py` so only one layer owns the disconnect path (no double-disconnect) and it passes the connection identity through.

## Phase 7 — Tests + scripts updated to the new reality

- Update `tests/conftest.py` to run on SQLite and set `DEBUG_USER` so debug-only endpoints can be exercised.
- Update `tests/test_websocket_live.py` to authenticate as the configured debug user before creating zones, and keep assertions aligned with the new tick payload shape (framework-built entities + per-player filtering + extras/events).
- Add one focused test proving fog-of-war behavior: two players subscribed to the same zone receive different filtered entity views via `get_player_state`.

## Acceptance criteria (definition of done)

- Server boots from scratch with SQLite using the documented steps.
- Tick messages include an entity snapshot consistent with the post-apply DB state for that tick (no 1-tick lag for creates/deletes).
- No client receives unfiltered/full state if the module redacts via `get_player_state`.
- Internal (server-side) logic errors crash the server; expected network/protocol failures do not.
- Reconnect cannot cause a stale socket to disconnect the new session.
