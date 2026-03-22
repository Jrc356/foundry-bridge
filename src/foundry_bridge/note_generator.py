import logging
import os
import time
from typing import Optional

from langchain.agents import create_agent
from langchain_core.tools import StructuredTool
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel, Field
from pydantic import Field as PydanticField

import foundry_bridge.db as db
from foundry_bridge.models import EntityType

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a meticulous scribe for a D&D 5e tabletop RPG campaign. Your task is to
extract structured session notes from speech-to-text transcripts of a play session.

You will receive:
- **Transcripts**: lines of dialogue and narration from the current batch, formatted
  as "[ID:N][SPEAKER]: text"
- **Recent notes**: structured notes from the last few sessions (for context)
- **Player characters**: names of the PCs — do NOT output these as entities

Use the following tools to look up relevant campaign history on demand:
- `search_entities`: Find existing NPCs, locations, quests, items, or factions
- `search_open_threads`: Find open unresolved plot threads by topic
- `search_resolved_threads`: Verify whether a thread was already resolved
- `search_events`: Find past story events for context or deduplication
- `search_past_notes`: Find broader historical session context
- `search_decisions`: Find past party decisions
- `search_loot`: Find previously acquired loot or items
- `search_combat`: Find past combat encounters

REQUIRED tool-use rules:
- Before adding any entry to `threads_opened`, you MUST call `search_open_threads`
  with a relevant query to check if the thread is already open. If found, do not re-open it.
- Before adding any IDs to `threads_closed`, you MUST call `search_open_threads` with
  a relevant query to find the correct thread IDs. Do NOT guess or invent IDs.
- Before outputting any entity, you MUST call `search_entities` with the entity's name
  to check if it already exists. If found, write a single updated description that
  incorporates both the prior description and any new information from this session.
  Do NOT omit previously known details — only add to or refine them.
- Avoid calling the same tool with identical queries twice. Use prior tool results
  instead of re-searching.

Guidelines:
- Write the summary in past tense, 3–6 sentences.
- Decisions are any agreements, plans, or choices the party made — "made_by" may be
  the group name, a PC name, or "the party".
- Loot entries must specify who acquired the item (use "the party" if shared).
- Combat entries should name the encounter and describe its outcome briefly.
- Important quotes must be verbatim lines from the transcripts. Only include
    quotes that are meaningfully impactful to the scene — emotionally charged,
    reveal character motivation, change the direction of the scene, mark a clear
    decision, or otherwise "pack a punch." Examples of good quotes:
    - "I will never forgive you!"
    - "We must leave now — it's the only way."
    - "The treasure is in the chest under the statue."
    Examples of bad quotes to omit: "uh, okay", "thanks", short filler words,
    routine greetings, or background chatter that doesn't advance plot or tone.
    Prefer at most 4 well-chosen quotes per note. Transcripts are formatted as
    "[ID:N][SPEAKER]: text"; include the N value as `transcript_id` and SPEAKER
    as `speaker` for each ImportantQuoteOutput.
- Entities are NPCs, locations, quests, items, or factions — never player characters.
- Events are a catch-all for notable story moments not captured in other fields (e.g. "Party arrived at the city of Neverwinter").
- Open new threads only for unresolved mysteries or plot hooks that emerged this session.
- Close threads (by ID) only if they were clearly resolved in the transcripts.
  For each closed thread, provide a brief resolution text in `thread_resolutions`
  (e.g. "The party found the missing key in the dungeon chest.").
"""

_MODEL_STR = f"{os.environ.get('MODEL_PROVIDER', 'openai')}:{os.environ.get('MODEL', 'gpt-5.4')}"

_STRUCTURED_OUTPUT_PROMPT = (
    "Extract the structured note data from the conversation above. "
    "Fill in all fields based on what was discussed and the tool results retrieved."
)


# ── Search tools (per-call) ─────────────────────────────────────────────────

class _SearchInput(BaseModel):
    query: str = PydanticField(description="Natural language search query")


class _EntitySearchInput(BaseModel):
    query: str = PydanticField(description="Natural language search query")
    entity_type: Optional[EntityType] = PydanticField(
        default=None,
        description="Optional filter: npc, location, quest, item, faction, or other. Leave blank to search all.",
    )


def make_game_tools(game_id: int) -> list:
    """Return the 8 search tools bound to a specific game_id."""

    async def search_entities(query: str, entity_type: Optional[EntityType] = None) -> str:
        start_time = time.time()
        logger.debug(
            "search_entities invoked",
            extra={"game_id": game_id, "query": query, "entity_type": entity_type},
        )
        try:
            rows = await db.search_entities(game_id, query, entity_type=entity_type)
            result_count = len(rows)
            elapsed = time.time() - start_time
            if result_count == 0:
                logger.info(
                    "search_entities returned no results",
                    extra={"game_id": game_id, "query": query, "result_count": result_count, "elapsed_sec": elapsed},
                )
                return "No matching entities found."
            logger.info(
                "search_entities succeeded",
                extra={
                    "game_id": game_id,
                    "query": query,
                    "result_count": result_count,
                    "elapsed_sec": elapsed,
                },
            )
            return "\n".join(f"[{r.entity_type}] {r.name}: {r.description}" for r in rows)
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                "search_entities failed",
                exc_info=True,
                extra={
                    "game_id": game_id,
                    "query": query,
                    "elapsed_sec": elapsed,
                    "error": str(e),
                },
            )
            return f"Error searching entities: {str(e)}"

    async def search_open_threads(query: str) -> str:
        start_time = time.time()
        logger.debug(
            "search_open_threads invoked",
            extra={"game_id": game_id, "query": query},
        )
        try:
            rows = await db.search_open_threads(game_id, query)
            result_count = len(rows)
            elapsed = time.time() - start_time
            if result_count == 0:
                logger.info(
                    "search_open_threads returned no results",
                    extra={"game_id": game_id, "query": query, "result_count": result_count, "elapsed_sec": elapsed},
                )
                return "No matching open threads found."
            logger.info(
                "search_open_threads succeeded",
                extra={
                    "game_id": game_id,
                    "query": query,
                    "result_count": result_count,
                    "elapsed_sec": elapsed,
                },
            )
            return "\n".join(f"ID {r.id}: {r.text}" for r in rows)
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                "search_open_threads failed",
                exc_info=True,
                extra={
                    "game_id": game_id,
                    "query": query,
                    "elapsed_sec": elapsed,
                    "error": str(e),
                },
            )
            return f"Error searching open threads: {str(e)}"

    async def search_resolved_threads(query: str) -> str:
        start_time = time.time()
        logger.debug(
            "search_resolved_threads invoked",
            extra={"game_id": game_id, "query": query},
        )
        try:
            rows = await db.search_resolved_threads(game_id, query)
            result_count = len(rows)
            elapsed = time.time() - start_time
            if result_count == 0:
                logger.info(
                    "search_resolved_threads returned no results",
                    extra={"game_id": game_id, "query": query, "result_count": result_count, "elapsed_sec": elapsed},
                )
                return "No matching resolved threads found."
            logger.info(
                "search_resolved_threads succeeded",
                extra={
                    "game_id": game_id,
                    "query": query,
                    "result_count": result_count,
                    "elapsed_sec": elapsed,
                },
            )
            return "\n".join(
                f"ID {r.id}: {r.text} (resolved: {r.resolution or 'no details'})" for r in rows
            )
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                "search_resolved_threads failed",
                exc_info=True,
                extra={
                    "game_id": game_id,
                    "query": query,
                    "elapsed_sec": elapsed,
                    "error": str(e),
                },
            )
            return f"Error searching resolved threads: {str(e)}"

    async def search_events(query: str) -> str:
        start_time = time.time()
        logger.debug(
            "search_events invoked",
            extra={"game_id": game_id, "query": query},
        )
        try:
            rows = await db.search_events(game_id, query)
            result_count = len(rows)
            elapsed = time.time() - start_time
            if result_count == 0:
                logger.info(
                    "search_events returned no results",
                    extra={"game_id": game_id, "query": query, "result_count": result_count, "elapsed_sec": elapsed},
                )
                return "No matching events found."
            logger.info(
                "search_events succeeded",
                extra={
                    "game_id": game_id,
                    "query": query,
                    "result_count": result_count,
                    "elapsed_sec": elapsed,
                },
            )
            return "\n".join(r.text for r in rows)
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                "search_events failed",
                exc_info=True,
                extra={
                    "game_id": game_id,
                    "query": query,
                    "elapsed_sec": elapsed,
                    "error": str(e),
                },
            )
            return f"Error searching events: {str(e)}"

    async def search_past_notes(query: str) -> str:
        start_time = time.time()
        logger.debug(
            "search_past_notes invoked",
            extra={"game_id": game_id, "query": query},
        )
        try:
            rows = await db.search_notes(game_id, query)
            result_count = len(rows)
            elapsed = time.time() - start_time
            if result_count == 0:
                logger.info(
                    "search_past_notes returned no results",
                    extra={"game_id": game_id, "query": query, "result_count": result_count, "elapsed_sec": elapsed},
                )
                return "No matching notes found."
            logger.info(
                "search_past_notes succeeded",
                extra={
                    "game_id": game_id,
                    "query": query,
                    "result_count": result_count,
                    "elapsed_sec": elapsed,
                },
            )
            return "\n".join(f"[{r.created_at}] {r.summary}" for r in rows)
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                "search_past_notes failed",
                exc_info=True,
                extra={
                    "game_id": game_id,
                    "query": query,
                    "elapsed_sec": elapsed,
                    "error": str(e),
                },
            )
            return f"Error searching past notes: {str(e)}"

    async def search_decisions(query: str) -> str:
        start_time = time.time()
        logger.debug(
            "search_decisions invoked",
            extra={"game_id": game_id, "query": query},
        )
        try:
            rows = await db.search_decisions(game_id, query)
            result_count = len(rows)
            elapsed = time.time() - start_time
            if result_count == 0:
                logger.info(
                    "search_decisions returned no results",
                    extra={"game_id": game_id, "query": query, "result_count": result_count, "elapsed_sec": elapsed},
                )
                return "No matching decisions found."
            logger.info(
                "search_decisions succeeded",
                extra={
                    "game_id": game_id,
                    "query": query,
                    "result_count": result_count,
                    "elapsed_sec": elapsed,
                },
            )
            return "\n".join(f"{r.made_by}: {r.decision}" for r in rows)
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                "search_decisions failed",
                exc_info=True,
                extra={
                    "game_id": game_id,
                    "query": query,
                    "elapsed_sec": elapsed,
                    "error": str(e),
                },
            )
            return f"Error searching decisions: {str(e)}"

    async def search_loot(query: str) -> str:
        start_time = time.time()
        logger.debug(
            "search_loot invoked",
            extra={"game_id": game_id, "query": query},
        )
        try:
            rows = await db.search_loot(game_id, query)
            result_count = len(rows)
            elapsed = time.time() - start_time
            if result_count == 0:
                logger.info(
                    "search_loot returned no results",
                    extra={"game_id": game_id, "query": query, "result_count": result_count, "elapsed_sec": elapsed},
                )
                return "No matching loot found."
            logger.info(
                "search_loot succeeded",
                extra={
                    "game_id": game_id,
                    "query": query,
                    "result_count": result_count,
                    "elapsed_sec": elapsed,
                },
            )
            return "\n".join(f"{r.acquired_by}: {r.item_name}" for r in rows)
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                "search_loot failed",
                exc_info=True,
                extra={
                    "game_id": game_id,
                    "query": query,
                    "elapsed_sec": elapsed,
                    "error": str(e),
                },
            )
            return f"Error searching loot: {str(e)}"

    async def search_combat(query: str) -> str:
        start_time = time.time()
        logger.debug(
            "search_combat invoked",
            extra={"game_id": game_id, "query": query},
        )
        try:
            rows = await db.search_combat(game_id, query)
            result_count = len(rows)
            elapsed = time.time() - start_time
            if result_count == 0:
                logger.info(
                    "search_combat returned no results",
                    extra={"game_id": game_id, "query": query, "result_count": result_count, "elapsed_sec": elapsed},
                )
                return "No matching combat records found."
            logger.info(
                "search_combat succeeded",
                extra={
                    "game_id": game_id,
                    "query": query,
                    "result_count": result_count,
                    "elapsed_sec": elapsed,
                },
            )
            return "\n".join(f"{r.encounter}: {r.outcome}" for r in rows)
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                "search_combat failed",
                exc_info=True,
                extra={
                    "game_id": game_id,
                    "query": query,
                    "elapsed_sec": elapsed,
                    "error": str(e),
                },
            )
            return f"Error searching combat: {str(e)}"

    return [
        StructuredTool.from_function(
            coroutine=search_entities,
            name="search_entities",
            description="Find existing NPCs, locations, quests, items, or factions by description.",
            args_schema=_EntitySearchInput,
        ),
        StructuredTool.from_function(
            coroutine=search_open_threads,
            name="search_open_threads",
            description="Find open unresolved plot threads by topic. REQUIRED before adding thread IDs to threads_closed.",
            args_schema=_SearchInput,
        ),
        StructuredTool.from_function(
            coroutine=search_resolved_threads,
            name="search_resolved_threads",
            description="Verify whether a thread was already resolved. REQUIRED before opening new threads.",
            args_schema=_SearchInput,
        ),
        StructuredTool.from_function(
            coroutine=search_events,
            name="search_events",
            description="Find past story events for context or deduplication.",
            args_schema=_SearchInput,
        ),
        StructuredTool.from_function(
            coroutine=search_past_notes,
            name="search_past_notes",
            description="Find broader historical session context from past notes.",
            args_schema=_SearchInput,
        ),
        StructuredTool.from_function(
            coroutine=search_decisions,
            name="search_decisions",
            description="Find past party decisions.",
            args_schema=_SearchInput,
        ),
        StructuredTool.from_function(
            coroutine=search_loot,
            name="search_loot",
            description="Find previously acquired loot or items.",
            args_schema=_SearchInput,
        ),
        StructuredTool.from_function(
            coroutine=search_combat,
            name="search_combat",
            description="Find past combat encounters.",
            args_schema=_SearchInput,
        ),
    ]


# ── Output schema ──────────────────────────────────────────────────────────────

class LootItem(BaseModel):
    item_name: str
    acquired_by: str  # PC name or "the party"


class ImportantQuoteOutput(BaseModel):
    text: str  # verbatim transcript line
    transcript_id: Optional[int] = None  # ID from [ID:N] prefix if identifiable
    speaker: Optional[str] = None  # character name who said it


class CombatUpdate(BaseModel):
    encounter: str
    outcome: str


class Decision(BaseModel):
    decision: str
    made_by: str  # PC name, NPC name, or "the party"


class EntityOutput(BaseModel):
    entity_type: EntityType  # npc | location | quest | item | faction | other
    name: str
    description: str


class NoteOutput(BaseModel):
    summary: str = Field(description="Brief 2–4 sentence summary of events in this transcript batch")
    events: list[str] = Field(description="Notable plot/story events not covered by other specific fields (catch-all)")
    decisions: list[Decision] = Field(description="Decisions made by players; each has decision text and made_by")
    loot: list[LootItem] = Field(description="Items acquired; each has item name and acquired_by (PC name or 'the party')")
    combat_updates: list[CombatUpdate] = Field(description="Combat encounters; each has encounter name and outcome")
    entities: list[EntityOutput] = Field(description="NPCs, locations, quests, items, factions, or other notable entities")
    threads_opened: list[str] = Field(description="New unresolved questions or plot threads to track (plain text)")
    threads_closed: list[int] = Field(description="DB IDs of currently-open threads that have been resolved in this session")
    thread_resolutions: dict[str, str] = Field(
        default_factory=dict,
        description="Map of thread_id (as string) → resolution text; coerce keys to int in _run_pipeline",
    )
    important_quotes: list[ImportantQuoteOutput] = Field(
        description="Verbatim lines from the transcripts that are significant; include the ID from the [ID:N] prefix if known and the speaker name"
    )


# ── Config validation ────────────────────────────────────────────────────────

_PROVIDER_KEY_MAP = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


def validate_config() -> None:
    """Validate LLM config at startup. Raises if required API key is missing."""
    provider = os.environ.get("MODEL_PROVIDER", "openai")
    required_key = _PROVIDER_KEY_MAP.get(provider)
    if required_key and not os.environ.get(required_key):
        logger.error(
            "Missing required API key: MODEL_PROVIDER=%r requires %s to be set",
            provider, required_key,
        )
        raise RuntimeError(
            f"MODEL_PROVIDER is '{provider}' but {required_key} is not set"
        )
    logger.info("LLM config validated (model=%s)", _MODEL_STR)


# ── Prompt builder ─────────────────────────────────────────────────────────────

def _filter_important_quotes(quotes: list) -> list:
    """Post-filter for important quotes (placeholder — returns quotes unchanged)."""
    return quotes


def _build_user_prompt(
    transcripts: list,
    recent_notes: list,
    *,
    player_characters: list,
) -> str:
    lines = ["## Transcripts (format: [ID:N][SPEAKER]: text — use N as transcript_id, SPEAKER as speaker)"]
    for t in transcripts:
        lines.append(f"[ID:{t.id}][{t.character_name}]: {t.text}")

    lines.append("\n## Recent Notes")
    if recent_notes:
        for n in recent_notes:
            lines.append(f"### Note from {n.created_at}\n{n.summary}")
    else:
        lines.append("None yet.")

    lines.append("\n## Player Characters")
    if player_characters:
        lines.append(", ".join(pc.character_name for pc in player_characters))
    else:
        lines.append("None specified.")

    lines.append("\nExtract structured notes from the above transcripts.")
    return "\n".join(lines)


# ── Exported function ──────────────────────────────────────────────────────────

async def generate_note(
    game_id: int,
    transcripts: list,
    recent_notes: list,
    *,
    player_characters: list,
) -> NoteOutput:
    """Create a per-call agent with game-scoped search tools and return a NoteOutput."""
    tools = make_game_tools(game_id)
    agent = create_agent(
        model=_MODEL_STR,
        tools=tools,
        response_format=NoteOutput,
        debug=os.getenv("LOG_LEVEL", "").lower() == "debug" or os.getenv("AGENT_DEBUG", "false").lower() == "true",
    )
    prompt = _build_user_prompt(transcripts, recent_notes, player_characters=player_characters)
    logger.info(
        "Calling LLM: game_id=%d transcripts=%d prompt_chars=%d model=%s",
        game_id, len(transcripts), len(prompt), _MODEL_STR,
    )
    try:
        result = await agent.ainvoke(
            {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"{prompt}\n\n{_STRUCTURED_OUTPUT_PROMPT}"},
                ]
            },
            config={"recursion_limit": 25},
        )
    except GraphRecursionError:
        logger.warning(
            "Agent recursion limit hit for game_id=%d; transcripts will be retried on next poll",
            game_id,
        )
        raise  # handled by _run_pipeline in note_taker.py — transcripts not marked processed

    # Post-filter: remove any entity whose name matches a known player character
    pc_names = {pc.character_name.lower() for pc in player_characters}
    note_output = result["structured_response"]
    note_output.entities = [
        e for e in note_output.entities
        if e.name.strip().lower() not in pc_names
    ]
    # Post-filter important quotes with conservative heuristics to avoid noisy / trivial quotes
    try:
        note_output.important_quotes = _filter_important_quotes(note_output.important_quotes)
    except Exception:
        logger.exception("Error filtering important quotes; falling back to LLM output")
    logger.info(
        "LLM returned: entities=%d threads_opened=%d threads_closed=%d "
        "events=%d decisions=%d loot=%d combat=%d quotes=%d",
        len(note_output.entities),
        len(note_output.threads_opened),
        len(note_output.threads_closed),
        len(note_output.events),
        len(note_output.decisions),
        len(note_output.loot),
        len(note_output.combat_updates),
        len(note_output.important_quotes),
    )
    return note_output
