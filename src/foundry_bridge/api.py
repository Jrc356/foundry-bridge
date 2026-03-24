"""FastAPI REST API for browsing and editing campaign data."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Optional

import sqlalchemy as sa
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from foundry_bridge.db import (
    AsyncSessionLocal,
    search_combat,
    search_decisions,
    search_entities,
    search_events,
    search_loot,
    search_notes,
    search_open_threads,
    search_quests,
    search_resolved_threads,
)
from foundry_bridge.models import (
    CombatUpdate,
    Decision,
    Entity,
    Event,
    Game,
    ImportantQuote,
    Loot,
    Note,
    PlayerCharacter,
    Quest,
    QuestDescriptionHistory,
    Thread,
    Transcript,
)

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="Foundry Bridge API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── DB dependency ─────────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


# ── Pydantic schemas ──────────────────────────────────────────────────────────


class GameOut(BaseModel):
    id: int
    hostname: str
    world_id: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


class GameCreate(BaseModel):
    hostname: str
    world_id: str
    name: str


class NoteOut(BaseModel):
    id: int
    game_id: int
    summary: str
    source_transcript_ids: list[int]
    created_at: datetime

    class Config:
        from_attributes = True


class EntityOut(BaseModel):
    id: int
    game_id: int
    entity_type: str
    name: str
    description: str
    note_ids: list[int] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EntityCreate(BaseModel):
    entity_type: str
    name: str
    description: str


class EntityUpdate(BaseModel):
    entity_type: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None


class ThreadOut(BaseModel):
    id: int
    game_id: int
    text: str
    is_resolved: bool
    resolved_at: Optional[datetime]
    resolution: Optional[str]
    resolved_by_note_id: Optional[int]
    quest_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class ThreadCreate(BaseModel):
    text: str


class ThreadUpdate(BaseModel):
    text: Optional[str] = None
    is_resolved: Optional[bool] = None
    resolution: Optional[str] = None
    resolved_by_note_id: Optional[int] = None
    quest_id: Optional[int] = None


class TranscriptOut(BaseModel):
    id: int
    game_id: Optional[int]
    participant_id: str
    character_name: str
    turn_index: int
    text: str
    audio_window_start: float
    audio_window_end: float
    end_of_turn_confidence: float
    note_taker_processed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class LootOut(BaseModel):
    id: int
    game_id: int
    item_name: str
    acquired_by: str
    quest_id: Optional[int]
    note_ids: list[int] = []
    created_at: datetime

    class Config:
        from_attributes = True


class LootCreate(BaseModel):
    item_name: str
    acquired_by: str


class LootUpdate(BaseModel):
    item_name: Optional[str] = None
    acquired_by: Optional[str] = None
    quest_id: Optional[int] = None


class QuestOut(BaseModel):
    id: int
    game_id: int
    name: str
    description: str
    status: str
    quest_giver_entity_id: Optional[int]
    note_ids: list[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class QuestDescriptionHistoryOut(BaseModel):
    id: int
    quest_id: int
    description: str
    note_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class QuestCreate(BaseModel):
    name: str
    description: str
    quest_giver_entity_id: Optional[int] = None


class QuestUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    quest_giver_entity_id: Optional[int] = None


class DecisionOut(BaseModel):
    id: int
    game_id: int
    note_id: int
    decision: str
    made_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class DecisionCreate(BaseModel):
    note_id: int
    decision: str
    made_by: str


class EventOut(BaseModel):
    id: int
    game_id: int
    text: str
    note_ids: list[int] = []
    created_at: datetime

    class Config:
        from_attributes = True


class EventCreate(BaseModel):
    text: str


class CombatUpdateOut(BaseModel):
    id: int
    game_id: int
    note_id: int
    encounter: str
    outcome: str
    created_at: datetime

    class Config:
        from_attributes = True


class ImportantQuoteOut(BaseModel):
    id: int
    game_id: int
    note_id: int
    transcript_id: Optional[int]
    text: str
    speaker: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class PlayerCharacterOut(BaseModel):
    id: int
    game_id: int
    character_name: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Games ─────────────────────────────────────────────────────────────────────


@app.get("/api/games", response_model=list[GameOut])
async def list_games(db: AsyncSession = Depends(get_db)):
    result = await db.execute(sa.select(Game).order_by(Game.created_at.desc()))
    return result.scalars().all()


@app.post("/api/games", response_model=GameOut, status_code=201)
async def create_game(body: GameCreate, db: AsyncSession = Depends(get_db)):
    game = Game(hostname=body.hostname, world_id=body.world_id, name=body.name)
    db.add(game)
    await db.commit()
    await db.refresh(game)
    return game


@app.get("/api/games/{game_id}", response_model=GameOut)
async def get_game(game_id: int, db: AsyncSession = Depends(get_db)):
    game = await db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


@app.patch("/api/games/{game_id}", response_model=GameOut)
async def update_game(game_id: int, body: GameCreate, db: AsyncSession = Depends(get_db)):
    game = await db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    game.name = body.name
    game.hostname = body.hostname
    game.world_id = body.world_id
    await db.commit()
    await db.refresh(game)
    return game


@app.delete("/api/games/{game_id}", status_code=204)
async def delete_game(game_id: int, db: AsyncSession = Depends(get_db)):
    game = await db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    await db.delete(game)
    await db.commit()


# ── Notes ─────────────────────────────────────────────────────────────────────


@app.get("/api/games/{game_id}/notes", response_model=list[NoteOut])
async def list_notes(game_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        sa.select(Note)
        .where(Note.game_id == game_id)
        .order_by(Note.created_at.asc())
    )
    return result.scalars().all()


@app.delete("/api/notes/{note_id}", status_code=204)
async def delete_note(note_id: int, db: AsyncSession = Depends(get_db)):
    note = await db.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    await db.delete(note)
    await db.commit()


@app.get("/api/games/{game_id}/notes/{note_id}/events", response_model=list[EventOut])
async def list_note_events(game_id: int, note_id: int, db: AsyncSession = Depends(get_db)):
    """Get all events linked to a specific note (many-to-many via notes_events table)."""
    from foundry_bridge.models import notes_events_table
    
    result = await db.execute(
        sa.select(Event)
        .join(notes_events_table, Event.id == notes_events_table.c.event_id)
        .where(
            notes_events_table.c.note_id == note_id,
            Event.game_id == game_id,
        )
        .order_by(Event.created_at.asc())
    )
    return result.scalars().all()


@app.get("/api/games/{game_id}/notes/{note_id}/loot", response_model=list[LootOut])
async def list_note_loot(game_id: int, note_id: int, db: AsyncSession = Depends(get_db)):
    """Get all loot linked to a specific note (many-to-many via notes_loot table)."""
    from foundry_bridge.models import notes_loot_table
    
    result = await db.execute(
        sa.select(Loot)
        .join(notes_loot_table, Loot.id == notes_loot_table.c.loot_id)
        .where(
            notes_loot_table.c.note_id == note_id,
            Loot.game_id == game_id,
        )
        .order_by(Loot.created_at.asc())
    )
    return result.scalars().all()


# ── Entities ──────────────────────────────────────────────────────────────────


@app.get("/api/games/{game_id}/entities", response_model=list[EntityOut])
async def list_entities(
    game_id: int,
    entity_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    from foundry_bridge.models import notes_entities_table
    q = sa.select(Entity).where(Entity.game_id == game_id)
    if entity_type:
        q = q.where(Entity.entity_type == entity_type)
    q = q.order_by(Entity.entity_type, Entity.name)
    result = await db.execute(q)
    entities = list(result.scalars().all())
    if not entities:
        return []
    assoc = await db.execute(
        sa.select(notes_entities_table.c.entity_id, notes_entities_table.c.note_id)
        .where(notes_entities_table.c.entity_id.in_([e.id for e in entities]))
    )
    note_ids_by_entity: dict[int, list[int]] = {}
    for entity_id, note_id in assoc.all():
        note_ids_by_entity.setdefault(entity_id, []).append(note_id)
    return [
        EntityOut(
            id=e.id, game_id=e.game_id, entity_type=e.entity_type, name=e.name,
            description=e.description, created_at=e.created_at, updated_at=e.updated_at,
            note_ids=note_ids_by_entity.get(e.id, []),
        )
        for e in entities
    ]


@app.post("/api/games/{game_id}/entities", response_model=EntityOut, status_code=201)
async def create_entity(game_id: int, body: EntityCreate, db: AsyncSession = Depends(get_db)):
    entity = Entity(game_id=game_id, **body.model_dump())
    db.add(entity)
    await db.commit()
    await db.refresh(entity)
    return entity


@app.put("/api/entities/{entity_id}", response_model=EntityOut)
async def update_entity(entity_id: int, body: EntityUpdate, db: AsyncSession = Depends(get_db)):
    entity = await db.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(entity, field, value)
    entity.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(entity)
    return entity


@app.delete("/api/entities/{entity_id}", status_code=204)
async def delete_entity(entity_id: int, db: AsyncSession = Depends(get_db)):
    entity = await db.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    await db.delete(entity)
    await db.commit()


# ── Threads ───────────────────────────────────────────────────────────────────


@app.get("/api/games/{game_id}/threads", response_model=list[ThreadOut])
async def list_threads(
    game_id: int,
    resolved: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    q = sa.select(Thread).where(Thread.game_id == game_id)
    if resolved is not None:
        q = q.where(Thread.is_resolved == resolved)
    q = q.order_by(Thread.created_at.asc())
    result = await db.execute(q)
    return result.scalars().all()


@app.post("/api/games/{game_id}/threads", response_model=ThreadOut, status_code=201)
async def create_thread(game_id: int, body: ThreadCreate, db: AsyncSession = Depends(get_db)):
    thread = Thread(game_id=game_id, text=body.text)
    db.add(thread)
    await db.commit()
    await db.refresh(thread)
    return thread


@app.put("/api/threads/{thread_id}", response_model=ThreadOut)
async def update_thread(thread_id: int, body: ThreadUpdate, db: AsyncSession = Depends(get_db)):
    thread = await db.get(Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    updates = body.model_dump(exclude_none=True)
    if updates.get("is_resolved") and not thread.is_resolved:
        thread.resolved_at = datetime.now(timezone.utc)
    for field, value in updates.items():
        setattr(thread, field, value)
    await db.commit()
    await db.refresh(thread)
    return thread


@app.delete("/api/threads/{thread_id}", status_code=204)
async def delete_thread(thread_id: int, db: AsyncSession = Depends(get_db)):
    thread = await db.get(Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    await db.delete(thread)
    await db.commit()


# ── Transcripts ───────────────────────────────────────────────────────────────


@app.get("/api/games/{game_id}/transcripts", response_model=list[TranscriptOut])
async def list_transcripts(
    game_id: int,
    character_name: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    q = sa.select(Transcript).where(Transcript.game_id == game_id)
    if character_name:
        q = q.where(Transcript.character_name.ilike(f"%{character_name}%"))
    q = q.order_by(Transcript.created_at.asc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return result.scalars().all()


@app.delete("/api/transcripts/{transcript_id}", status_code=204)
async def delete_transcript(transcript_id: int, db: AsyncSession = Depends(get_db)):
    t = await db.get(Transcript, transcript_id)
    if not t:
        raise HTTPException(status_code=404, detail="Transcript not found")
    await db.delete(t)
    await db.commit()


# ── Loot ──────────────────────────────────────────────────────────────────────


@app.get("/api/games/{game_id}/loot", response_model=list[LootOut])
async def list_loot(game_id: int, db: AsyncSession = Depends(get_db)):
    from foundry_bridge.models import notes_loot_table
    result = await db.execute(
        sa.select(Loot).where(Loot.game_id == game_id).order_by(Loot.created_at.asc())
    )
    items = list(result.scalars().all())
    if not items:
        return []
    assoc = await db.execute(
        sa.select(notes_loot_table.c.loot_id, notes_loot_table.c.note_id)
        .where(notes_loot_table.c.loot_id.in_([i.id for i in items]))
    )
    note_ids_by_loot: dict[int, list[int]] = {}
    for loot_id, note_id in assoc.all():
        note_ids_by_loot.setdefault(loot_id, []).append(note_id)
    return [
        LootOut(
            id=i.id, game_id=i.game_id, item_name=i.item_name, acquired_by=i.acquired_by,
            quest_id=i.quest_id, created_at=i.created_at,
            note_ids=note_ids_by_loot.get(i.id, []),
        )
        for i in items
    ]


@app.post("/api/games/{game_id}/loot", response_model=LootOut, status_code=201)
async def create_loot(game_id: int, body: LootCreate, db: AsyncSession = Depends(get_db)):
    loot = Loot(game_id=game_id, **body.model_dump())
    db.add(loot)
    await db.commit()
    await db.refresh(loot)
    return loot


@app.delete("/api/loot/{loot_id}", status_code=204)
async def delete_loot(loot_id: int, db: AsyncSession = Depends(get_db)):
    loot = await db.get(Loot, loot_id)
    if not loot:
        raise HTTPException(status_code=404, detail="Loot not found")
    await db.delete(loot)
    await db.commit()


@app.patch("/api/loot/{loot_id}", response_model=LootOut)
async def update_loot(loot_id: int, body: LootUpdate, db: AsyncSession = Depends(get_db)):
    loot = await db.get(Loot, loot_id)
    if not loot:
        raise HTTPException(status_code=404, detail="Loot not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(loot, field, value)
    await db.commit()
    await db.refresh(loot)
    return loot


# ── Quests ────────────────────────────────────────────────────────────────────


@app.get("/api/games/{game_id}/quests", response_model=list[QuestOut])
async def list_quests(
    game_id: int,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    q = sa.select(Quest).where(Quest.game_id == game_id)
    if status:
        q = q.where(Quest.status == status)
    q = q.order_by(Quest.created_at.desc())
    result = await db.execute(q)
    return result.scalars().all()


@app.post("/api/games/{game_id}/quests", response_model=QuestOut, status_code=201)
async def create_quest(game_id: int, body: QuestCreate, db: AsyncSession = Depends(get_db)):
    quest = Quest(
        game_id=game_id,
        name=body.name,
        description=body.description,
        status="active",
        quest_giver_entity_id=body.quest_giver_entity_id,
        note_ids=[],
    )
    db.add(quest)
    await db.commit()
    await db.refresh(quest)
    return quest


@app.patch("/api/quests/{quest_id}", response_model=QuestOut)
async def update_quest(quest_id: int, body: QuestUpdate, db: AsyncSession = Depends(get_db)):
    quest = await db.get(Quest, quest_id)
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    updates = body.model_dump(exclude_none=True)
    if "status" in updates and updates["status"] not in ("active", "completed"):
        raise HTTPException(status_code=400, detail="status must be 'active' or 'completed'")
    for field, value in updates.items():
        setattr(quest, field, value)
    quest.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(quest)
    return quest


@app.delete("/api/quests/{quest_id}", status_code=204)
async def delete_quest(quest_id: int, db: AsyncSession = Depends(get_db)):
    quest = await db.get(Quest, quest_id)
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    await db.delete(quest)
    await db.commit()


@app.get("/api/quests/{quest_id}/history", response_model=list[QuestDescriptionHistoryOut])
async def get_quest_description_history(quest_id: int, db: AsyncSession = Depends(get_db)):
    quest = await db.get(Quest, quest_id)
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    result = await db.execute(
        sa.select(QuestDescriptionHistory)
        .where(QuestDescriptionHistory.quest_id == quest_id)
        .order_by(QuestDescriptionHistory.created_at.desc())
    )
    return result.scalars().all()


# ── Decisions ─────────────────────────────────────────────────────────────────


@app.get("/api/games/{game_id}/decisions", response_model=list[DecisionOut])
async def list_decisions(game_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        sa.select(Decision).where(Decision.game_id == game_id).order_by(Decision.created_at.asc())
    )
    return result.scalars().all()


@app.post("/api/games/{game_id}/decisions", response_model=DecisionOut, status_code=201)
async def create_decision(game_id: int, body: DecisionCreate, db: AsyncSession = Depends(get_db)):
    decision = Decision(game_id=game_id, **body.model_dump())
    db.add(decision)
    await db.commit()
    await db.refresh(decision)
    return decision


@app.delete("/api/decisions/{decision_id}", status_code=204)
async def delete_decision(decision_id: int, db: AsyncSession = Depends(get_db)):
    d = await db.get(Decision, decision_id)
    if not d:
        raise HTTPException(status_code=404, detail="Decision not found")
    await db.delete(d)
    await db.commit()


# ── Events ────────────────────────────────────────────────────────────────────


@app.get("/api/games/{game_id}/events", response_model=list[EventOut])
async def list_events(game_id: int, db: AsyncSession = Depends(get_db)):
    from foundry_bridge.models import notes_events_table
    result = await db.execute(
        sa.select(Event).where(Event.game_id == game_id).order_by(Event.created_at.asc())
    )
    events = list(result.scalars().all())
    if not events:
        return []
    assoc = await db.execute(
        sa.select(notes_events_table.c.event_id, notes_events_table.c.note_id)
        .where(notes_events_table.c.event_id.in_([e.id for e in events]))
    )
    note_ids_by_event: dict[int, list[int]] = {}
    for event_id, note_id in assoc.all():
        note_ids_by_event.setdefault(event_id, []).append(note_id)
    return [
        EventOut(
            id=e.id, game_id=e.game_id, text=e.text, created_at=e.created_at,
            note_ids=note_ids_by_event.get(e.id, []),
        )
        for e in events
    ]


@app.post("/api/games/{game_id}/events", response_model=EventOut, status_code=201)
async def create_event(game_id: int, body: EventCreate, db: AsyncSession = Depends(get_db)):
    event = Event(game_id=game_id, text=body.text)
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


@app.delete("/api/events/{event_id}", status_code=204)
async def delete_event(event_id: int, db: AsyncSession = Depends(get_db)):
    e = await db.get(Event, event_id)
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    await db.delete(e)
    await db.commit()


# ── Combat updates ────────────────────────────────────────────────────────────


@app.get("/api/games/{game_id}/combat", response_model=list[CombatUpdateOut])
async def list_combat(game_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        sa.select(CombatUpdate)
        .where(CombatUpdate.game_id == game_id)
        .order_by(CombatUpdate.created_at.asc())
    )
    return result.scalars().all()


@app.delete("/api/combat/{combat_id}", status_code=204)
async def delete_combat(combat_id: int, db: AsyncSession = Depends(get_db)):
    c = await db.get(CombatUpdate, combat_id)
    if not c:
        raise HTTPException(status_code=404, detail="Combat update not found")
    await db.delete(c)
    await db.commit()


# ── Quotes ────────────────────────────────────────────────────────────────────


@app.get("/api/games/{game_id}/quotes", response_model=list[ImportantQuoteOut])
async def list_quotes(game_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        sa.select(ImportantQuote)
        .where(ImportantQuote.game_id == game_id)
        .order_by(ImportantQuote.created_at.asc())
    )
    return result.scalars().all()


@app.delete("/api/quotes/{quote_id}", status_code=204)
async def delete_quote(quote_id: int, db: AsyncSession = Depends(get_db)):
    q = await db.get(ImportantQuote, quote_id)
    if not q:
        raise HTTPException(status_code=404, detail="Quote not found")
    await db.delete(q)
    await db.commit()


# ── Player characters ─────────────────────────────────────────────────────────


@app.get("/api/games/{game_id}/player_characters", response_model=list[PlayerCharacterOut])
async def list_player_characters(game_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        sa.select(PlayerCharacter)
        .where(PlayerCharacter.game_id == game_id)
        .order_by(PlayerCharacter.character_name)
    )
    return result.scalars().all()


# ── Semantic search ──────────────────────────────────────────────────────────

_SEARCHABLE_TYPES = frozenset({"entities", "notes", "threads", "events", "decisions", "loot", "combat", "quests"})


class SearchResultsOut(BaseModel):
    entities: list[EntityOut] = []
    notes: list[NoteOut] = []
    threads: list[ThreadOut] = []
    events: list[EventOut] = []
    decisions: list[DecisionOut] = []
    loot: list[LootOut] = []
    combat: list[CombatUpdateOut] = []
    quests: list[QuestOut] = []


@app.get("/api/games/{game_id}/search", response_model=SearchResultsOut)
async def search_game(
    game_id: int,
    q: str = Query(..., min_length=1),
    content_type: Optional[str] = Query(default=None),
    limit: int = Query(default=8, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    game = await db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if content_type is not None and content_type not in _SEARCHABLE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content_type. Must be one of: {', '.join(sorted(_SEARCHABLE_TYPES))}",
        )

    run_all = content_type is None

    async def _entities():
        if run_all or content_type == "entities":
            return await search_entities(game_id, q, k=limit)
        return []

    async def _notes():
        if run_all or content_type == "notes":
            return await search_notes(game_id, q, k=limit)
        return []

    async def _threads():
        if run_all or content_type == "threads":
            open_, resolved = await asyncio.gather(
                search_open_threads(game_id, q, k=limit),
                search_resolved_threads(game_id, q, k=limit),
            )
            seen: dict[int, object] = {}
            for t in open_ + resolved:
                if t.id not in seen:
                    seen[t.id] = t
            return list(seen.values())[:limit]
        return []

    async def _events():
        if run_all or content_type == "events":
            return await search_events(game_id, q, k=limit)
        return []

    async def _decisions():
        if run_all or content_type == "decisions":
            return await search_decisions(game_id, q, k=limit)
        return []

    async def _loot():
        if run_all or content_type == "loot":
            return await search_loot(game_id, q, k=limit)
        return []

    async def _combat():
        if run_all or content_type == "combat":
            return await search_combat(game_id, q, k=limit)
        return []

    async def _quests():
        if run_all or content_type == "quests":
            return await search_quests(game_id, q, k=limit)
        return []

    entities, notes, threads, events, decisions, loot, combat, quests = await asyncio.gather(
        _entities(), _notes(), _threads(), _events(), _decisions(), _loot(), _combat(), _quests()
    )

    return SearchResultsOut(
        entities=entities,
        notes=notes,
        threads=threads,
        events=events,
        decisions=decisions,
        loot=loot,
        combat=combat,
        quests=quests,
    )


# ── Static files (React SPA) ──────────────────────────────────────────────────

_FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


def mount_frontend() -> None:
    """Mount the built React app if the dist directory exists."""
    if _FRONTEND_DIST.exists():
        # Serve static assets (js, css, etc.) at their exact paths
        app.mount(
            "/assets",
            StaticFiles(directory=str(_FRONTEND_DIST / "assets")),
            name="assets",
        )

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):
            # If requesting a known static file, serve it directly
            requested = _FRONTEND_DIST / full_path
            if requested.is_file():
                return FileResponse(str(requested))
            # Otherwise fall through to SPA index.html
            return FileResponse(str(_FRONTEND_DIST / "index.html"))


mount_frontend()
