# Foundry Bridge

A full-stack application for capturing, transcribing, and exploring tabletop RPG game sessions. Foundry Bridge automatically transcribes audio, extracts game entities, tracks quests and decisions, and provides a searchable interface to explore your campaign.

## What is Foundry Bridge?

Foundry Bridge bridges the gap between your tabletop RPG sessions and organized campaign documentation. It:

- **Captures live session audio** via WebSocket connection
- **Transcribes speech to text** using Deepgram's AI
- **Extracts game data** including NPCs, locations, quests, combat encounters, and more
- **Enables semantic search** using vector embeddings to find moments across sessions
- **Provides a browsable interface** to explore campaign history, character interactions, and key decisions

Perfect for Dungeon Masters, players, and campaign archivists who want to preserve and explore the narrative of their campaigns.

## Tech Stack

- **Backend**: FastAPI + SQLAlchemy with async support
- **Database**: PostgreSQL with pgvector for semantic search
- **Audio**: Deepgram SDK for speech-to-text transcription
- **AI/ML**: LangChain + OpenAI for embeddings and entity extraction
- **Frontend**: React + TypeScript + Vite
- **Infrastructure**: Docker + Docker Compose

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js (for local frontend development)
- Python 3.10+ (for local backend development)
- API keys for [Deepgram](https://www.deepgram.com/) and [OpenAI](https://platform.openai.com/)

### Using Docker (Recommended)

1. **Clone and configure**
   ```bash
   git clone <repo-url>
   cd foundry-bridge
   cp .env.example .env  # Create and edit with your API keys
   ```

2. **Start the stack**
   ```bash
   docker compose up
   ```

   The application will be available at:
   - Frontend: http://localhost:5173
   - API: http://localhost:8767
   - WebSocket: ws://localhost:8765

3. **Stop everything**
   ```bash
   docker compose down
   ```

### Local Development

#### Backend Setup

1. **Install dependencies**
   ```bash
   uv sync
   ```

2. **Start the database** (if not using Docker)
   ```bash
   docker compose up postgres
   ```

3. **Run migrations**
   ```bash
   uv run alembic upgrade head
   ```

4. **Start the server**
   ```bash
   uv run foundry-bridge
   ```

   Or run individual components:
   ```bash
   make run-api          # FastAPI server
   make run              # Main server (WebSocket + HTTP)
   ```

#### Frontend Setup

1. **Install dependencies**
   ```bash
   cd frontend
   npm install
   ```

2. **Start development server**
   ```bash
   npm run dev
   ```

   The frontend will be available at http://localhost:5173

## Project Structure

```
.
├── src/foundry_bridge/          # Python backend
│   ├── server.py               # WebSocket + HTTP server entry point
│   ├── api.py                  # FastAPI routes
│   ├── db.py                   # Database setup and utilities
│   ├── models.py               # SQLAlchemy ORM models
│   ├── transcriber.py          # Deepgram integration
│   ├── note_taker.py           # Entity extraction and processing
│   └── note_generator.py       # AI-driven content generation
├── frontend/                    # React + TypeScript frontend
│   ├── src/
│   │   ├── pages/              # Game detail and list pages
│   │   ├── components/         # Reusable UI components
│   │   ├── tabs/               # Feature-specific data views
│   │   ├── api.ts              # Frontend API client
│   │   └── types.ts            # TypeScript interfaces
│   └── vite.config.ts          # Build configuration
├── alembic/                     # Database migrations
├── seeds/                       # Demo data SQL
└── docker-compose.yml          # Multi-container setup
```

## Key Features

### Transcription
Real-time audio transcription from connected clients via WebSocket, powered by Deepgram's automatic speech recognition.

### Game Sessions
Organize transcripts by game session with metadata tracking, participant management, and turn-by-turn conversation records.

### Entity Extraction
Automatically identify and catalog:
- **NPCs** (characters, relationships, attributes)
- **Locations** (places, descriptions, significance)
- **Items** (equipment, treasures, quest objects)
- **Quests** (objectives, rewards, status)
- **Factions** (organizations, allegiances, conflicts)

### Semantic Search
Search across all sessions using natural language. Vector embeddings enable finding relevant moments even with different phrasing.

### Browsable Interface
Explore your campaign through multiple views:
- **Transcripts**: Full session conversations
- **Entities**: NPCs, locations, items organized and linked
- **Quests**: Quest log with status and connections
- **Combat**: Combat encounters, tactics, outcomes
- **Decisions**: Key campaign decisions and their impacts
- **Notes**: AI-generated summaries and custom annotations

## Configuration

Set these environment variables in `.env`:

```bash
# Deepgram
DEEPGRAM_API_KEY=your_deepgram_key

# OpenAI
OPENAI_API_KEY=your_openai_key

# Database
DATABASE_URL=postgresql://foundry:password@localhost:5432/foundry_bridge
POSTGRES_PASSWORD=password

# Server ports
WS_PORT=8765        # WebSocket server
HTTP_PORT=8766      # HTTP server
API_PORT=8767       # FastAPI REST API

# Optional features
LOG_LEVEL=INFO
```

## Development Workflow

### Common Tasks

```bash
# Sync Python dependencies
make sync

# Run tests (when available)
make test

# Format code
make format

# Database operations
make db-upgrade      # Apply pending migrations
make db-downgrade    # Revert migrations
```

### Database Migrations

Create a new migration after changing models:

```bash
uv run alembic revision --autogenerate -m "description of changes"
uv run alembic upgrade head
```

### Loading Demo Data

Demo data is provided in the `seeds/` directory:

```bash
psql -U foundry -d foundry_bridge -f seeds/01_first_session.sql
```

## API Documentation

Once the API server is running, interactive API docs are available at:
- **Swagger UI**: http://localhost:8767/docs
- **ReDoc**: http://localhost:8767/redoc

## Troubleshooting

### Database connection refused
Ensure PostgreSQL is running:
```bash
docker compose up postgres
```

### Audio transcription not working
- Check that `DEEPGRAM_API_KEY` is set in `.env`
- Verify audio is being sent to the WebSocket server
- Check server logs for transcription errors

### Frontend can't reach API
- Ensure the FastAPI server is running on port 8767
- Check `frontend/src/api.ts` for the correct API base URL
- Verify CORS is properly configured if hosting on different domains

### Out of memory in Docker
Increase Docker's memory limit in Docker Desktop settings or adjust service resource limits in `docker-compose.yml`.

## Contributing

1. Create a feature branch
2. Make your changes
3. Test thoroughly locally
4. Submit a pull request with a clear description

## License

[Add your license here]

## Support

For issues and questions:
- Check existing GitHub issues
- Review the troubleshooting section above
- Open a new issue with details about your setup and the problem
