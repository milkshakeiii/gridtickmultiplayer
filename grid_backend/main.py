"""
Main FastAPI application for Grid Backend.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError, OperationalError, IntegrityError

from grid_backend.config import get_settings
from grid_backend.database import engine, init_db, close_db, async_session_factory
from grid_backend.api import api_router
from grid_backend.websocket.manager import ConnectionManager, set_connection_manager
from grid_backend.websocket.handler import WebSocketHandler
from grid_backend.tick_engine.engine import TickEngine, set_tick_engine
from grid_backend.game_logic import load_game_module, FrameworkAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Initializes and cleans up resources.
    """
    settings = get_settings()

    # Initialize database
    logger.info("Initializing database...")
    await init_db()

    # Initialize connection manager
    logger.info("Initializing connection manager...")
    manager = ConnectionManager()
    set_connection_manager(manager)

    # Load game logic module
    logger.info(f"Loading game module: {settings.game_module}")
    framework = FrameworkAPI(async_session_factory)
    game_logic = await load_game_module(settings.game_module, framework)

    # Initialize tick engine
    logger.info(f"Starting tick engine (rate: {settings.tick_rate_ms}ms)...")
    tick_engine = TickEngine(
        tick_rate_ms=settings.tick_rate_ms,
        db_session_factory=async_session_factory,
        game_logic_module=game_logic,
    )
    set_tick_engine(tick_engine)
    await tick_engine.start()

    logger.info("Grid Backend started successfully!")

    yield

    # Shutdown
    logger.info("Shutting down...")

    # Stop tick engine
    await tick_engine.stop()
    set_tick_engine(None)

    # Close database connections
    await close_db()

    logger.info("Grid Backend stopped.")


# Create FastAPI application
app = FastAPI(
    title="Grid Backend",
    description="A minimal Python backend framework for tick-based 2D grid multiplayer games",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api")


# Database error exception handlers
@app.exception_handler(OperationalError)
async def operational_error_handler(request: Request, exc: OperationalError):
    """Handle database connection/operational errors."""
    logger.error(f"Database operational error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Database connection error. Please try again later."},
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Handle database integrity constraint violations."""
    logger.error(f"Database integrity error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "Database integrity error. The operation conflicts with existing data."},
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    """Handle general SQLAlchemy errors."""
    logger.error(f"Database error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Database error. Please try again later."},
    )


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint for game connections.
    Requires token query parameter for authentication.
    """
    from grid_backend.websocket import get_connection_manager
    from grid_backend.database import get_db_context

    # Get token from query parameters
    token = websocket.query_params.get("token")

    if token is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    manager = get_connection_manager()
    if manager is None:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    # Authenticate
    async with get_db_context() as db:
        info = await manager.authenticate(websocket, token, db)

    if info is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Accept connection
    await websocket.accept()

    # Register connection
    await manager.connect(info)

    # Create handler and process messages
    # Handler owns the disconnect path (passes connection_id for safety)
    handler = WebSocketHandler(
        manager=manager,
        info=info,
        db_session_factory=async_session_factory,
    )

    await handler.handle_connection()


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from grid_backend.tick_engine import get_tick_engine

    engine = get_tick_engine()

    return {
        "status": "healthy",
        "tick_engine_running": engine is not None and engine.is_running,
        "tick_number": engine.tick_number if engine else 0,
    }


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "grid_backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
