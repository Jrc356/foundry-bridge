import logging
import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from foundry_bridge.models import Base, Transcript

logger = logging.getLogger(__name__)

_DATABASE_URL = os.environ.get("DATABASE_URL")
if not _DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Accept plain postgresql:// URLs and convert to the asyncpg scheme.
if _DATABASE_URL.startswith("postgresql://"):
    _DATABASE_URL = _DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(_DATABASE_URL, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_schema() -> None:
    """Create all tables if they don't already exist (safe for first startup)."""
    logger.info("Running schema init (create_all)")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Schema init complete")


async def store_transcript(
    *,
    participant_id: str,
    character_name: str,
    turn_index: int,
    transcript: str,
    audio_window_start: float,
    audio_window_end: float,
    end_of_turn_confidence: float,
) -> None:
    logger.info(
        "Storing transcript: participant=%s character=%s turn=%d text=%r",
        participant_id,
        character_name,
        turn_index,
        transcript,
    )
    row = Transcript(
        participant_id=participant_id,
        character_name=character_name,
        turn_index=turn_index,
        transcript=transcript,
        audio_window_start=audio_window_start,
        audio_window_end=audio_window_end,
        end_of_turn_confidence=end_of_turn_confidence,
    )
    async with AsyncSessionLocal() as session:
        session.add(row)
        await session.commit()
    logger.info(
        "Transcript stored: participant=%s character=%s turn=%d",
        participant_id,
        character_name,
        turn_index,
    )
        await session.commit()
