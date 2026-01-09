#!/bin/bash
# Grid Backend - Quick Start Script
# Starts the development server with auto-reload

set -e

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Load environment variables
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Default values
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8000}

echo "Starting Grid Backend server..."
echo "API: http://$HOST:$PORT"
echo "Docs: http://$HOST:$PORT/docs"
echo "WebSocket: ws://$HOST:$PORT/ws"
echo ""

uvicorn grid_backend.main:app --reload --host $HOST --port $PORT
