#!/bin/bash
# Grid Backend - Development Environment Setup Script
# This script sets up and runs the development environment for the Grid Backend framework

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Grid Backend - Development Setup${NC}"
echo -e "${BLUE}========================================${NC}"

# Check Python version
echo -e "\n${YELLOW}Checking Python version...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is not installed. Please install Python 3.11+${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${GREEN}Python version: $PYTHON_VERSION${NC}"

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo -e "\n${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
echo -e "\n${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Upgrade pip
echo -e "\n${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip

# Install dependencies
echo -e "\n${YELLOW}Installing dependencies...${NC}"
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo -e "${RED}requirements.txt not found. Installing core dependencies...${NC}"
    pip install fastapi uvicorn[standard] websockets sqlalchemy[asyncio] aiosqlite pydantic passlib[bcrypt] python-jose[cryptography] alembic pytest pytest-asyncio httpx

    # Generate requirements.txt
    pip freeze > requirements.txt
    echo -e "${GREEN}Generated requirements.txt${NC}"
fi

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "\n${YELLOW}Creating .env file with defaults...${NC}"
    cat > .env << EOF
# Grid Backend Configuration
DATABASE_URL=sqlite+aiosqlite:///./gridbackend.db
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
DEBUG_MODE=true
TICK_RATE_MS=1000
SESSION_TIMEOUT_SECONDS=0
MIN_PASSWORD_LENGTH=8
GAME_MODULE=grid_backend.game_modules.example
HOST=0.0.0.0
PORT=8000
EOF
    echo -e "${GREEN}.env file created${NC}"
fi

# Load environment variables
export $(grep -v '^#' .env | xargs)

# Run database migrations if they exist
if [ -d "alembic" ]; then
    echo -e "\n${YELLOW}Running database migrations...${NC}"
    alembic upgrade head || echo -e "${YELLOW}Migrations failed or not yet configured${NC}"
fi

# Initialize the database tables
echo -e "\n${YELLOW}Initializing database tables...${NC}"
python3 -c "
import asyncio
from grid_backend.database import init_db

async def setup():
    try:
        await init_db()
        print('Database tables initialized successfully')
    except Exception as e:
        print(f'Database init skipped: {e}')

asyncio.run(setup())
" 2>/dev/null || echo -e "${YELLOW}Database initialization will run on first start${NC}"

# Print startup information
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "\n${BLUE}To start the development server:${NC}"
echo -e "  ${YELLOW}source venv/bin/activate${NC}"
echo -e "  ${YELLOW}uvicorn grid_backend.main:app --reload --host 0.0.0.0 --port 8000${NC}"
echo -e "\n${BLUE}Or use the quick start command:${NC}"
echo -e "  ${YELLOW}./run.sh${NC}"
echo -e "\n${BLUE}API Documentation will be available at:${NC}"
echo -e "  ${YELLOW}http://localhost:8000/docs${NC} (Swagger UI)"
echo -e "  ${YELLOW}http://localhost:8000/redoc${NC} (ReDoc)"
echo -e "\n${BLUE}WebSocket endpoint:${NC}"
echo -e "  ${YELLOW}ws://localhost:8000/ws${NC}"
echo -e "\n${BLUE}Environment Configuration:${NC}"
echo -e "  Edit ${YELLOW}.env${NC} file to customize settings"
echo -e "\n${BLUE}Database:${NC}"
echo -e "  SQLite database will be created automatically at ${YELLOW}./gridbackend.db${NC}"
