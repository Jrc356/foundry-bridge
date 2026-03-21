import logging
import os
from typing import Any, Optional

from langchain.agents import create_agent
from typing import Any, Optional, List
import re

from foundry_bridge.models import EntityType

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a meticulous scribe for a D&D 5e tabletop RPG campaign. Your task is to
extract structured session notes from speech-to-text transcripts of a play session.

You will receive:
- **Transcripts**: lines of dialogue and narration from the current batch, formatted
  as "[SPEAKER]: text"
- **Recent notes**: structured notes from the last few sessions (for context)
- **Open threads**: unresolved plot threads with their IDs; close any that were resolved
  this session by including their ID in `threads_closed`
- **Resolved threads**: previously closed threads — do NOT re-open these as new threads
- **Known entities**: NPCs, locations, items, factions, and quests already recorded
- **Player characters**: names of the PCs — do NOT output these as entities

Guidelines:
- Write the summary in past tense, 3–6 sentences.
- Decisions are any agreements, plans, or choices the party made — "made_by" may be
  the group name, a PC name, or "the party".
- Loot entries must specify who acquired the item (use "the party" if shared).
- Combat entries should name the encounter and describe its outcome briefly.
- Important quotes must be verbatim lines from the transcripts. Transcripts are
  formatted as "[ID:N][SPEAKER]: text"; include the N value as transcript_id in
  the ImportantQuoteOutput and the SPEAKER value as speaker.
- Entities are NPCs, locations, quests, items, or factions — never player characters.
- Events are a catch-all for notable story moments not captured in other fields (e.g. "Party arrived at the city of Neverwinter").
- Open new threads only for unresolved mysteries or plot hooks that emerged this session.
- Close threads (by ID) only if they were clearly resolved in the transcripts.
  For each closed thread, provide a brief resolution text in `thread_resolutions`
  (e.g. "The party found the missing key in the dungeon chest.").
"""

_agent: Any = None


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


# ── Agent singleton ──────────────────────────────────────────────────────────────

_MODEL_STR = f"{os.environ.get('MODEL_PROVIDER', 'openai')}:{os.environ.get('MODEL', 'gpt-5.4')}"


def _get_agent() -> Any:
    global _agent
    if _agent is None:
        _agent = create_agent(
            model=_MODEL_STR,
            tools=[],
            response_format=NoteOutput,
            system_prompt=SYSTEM_PROMPT,
        )
    return _agent


_PROVIDER_KEY_MAP = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


def init_agent() -> None:
    """Eagerly initialize the LLM agent. Raises if required API key is missing."""
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
    _get_agent()
    logger.info("LLM agent initialised (model=%s)", _MODEL_STR)


# ── Prompt builder ─────────────────────────────────────────────────────────────

def _build_user_prompt(
    transcripts: list,
    entities: list,
    recent_notes: list,
    open_threads: list,
    resolved_threads: list,
    *,
    game_events: list,
    player_characters: list,
) -> str:
    lines = ["## Transcripts (format: [ID:N][SPEAKER]: text — use N as transcript_id, SPEAKER as speaker)"]
    for t in transcripts:
        lines.append(f"[ID:{t.id}][{t.character_name}]: {t.text}")

    lines.append("\n## Recent Notes")
    if recent_notes:
        for n in recent_notes[-3:]:
            lines.append(f"### Note from {n.created_at}\n{n.summary}")
    else:
        lines.append("None yet.")

    lines.append("\n## Open Threads")
    if open_threads:
        for thread in open_threads:
            lines.append(f"- ID {thread.id}: {thread.text}")
    else:
        lines.append("None.")

    lines.append("\n## Resolved Threads (do NOT re-open these)")
    if resolved_threads:
        for thread in resolved_threads:
            lines.append(f"- ID {thread.id}: {thread.text} (resolved: {thread.resolution or 'no details'})")
    else:
        lines.append("None.")

    lines.append("\n## Known Entities")
    if entities:
        for e in entities:
            lines.append(f"- [{e.entity_type}] {e.name}: {e.description}")
    else:
        lines.append("None yet.")

    lines.append("\n## Previous Events")
    if game_events:
        for ev in game_events:
            lines.append(f"- {ev.text}")
    else:
        lines.append("None recorded yet.")

    lines.append("\n## Player Characters")
    if player_characters:
        lines.append(", ".join(pc.character_name for pc in player_characters))
    else:
        lines.append("None specified.")

    lines.append("\nExtract structured notes from the above transcripts.")
    return "\n".join(lines)


# ── Exported function ──────────────────────────────────────────────────────────

async def generate_note(
    transcripts: list,
    entities: list,
    recent_notes: list,
    open_threads: list,
    resolved_threads: list,
    *,
    game_events: list,
    player_characters: list,
) -> NoteOutput:
    """Call the agent and return a structured NoteOutput."""
    prompt = _build_user_prompt(
        transcripts, entities, recent_notes, open_threads, resolved_threads,
        game_events=game_events, player_characters=player_characters,
    )
    logger.info(
        "Calling LLM: transcripts=%d prompt_chars=%d model=%s",
        len(transcripts), len(prompt), _MODEL_STR,
    )
    agent = _get_agent()
    result = await agent.ainvoke({
        "messages": [{"role": "user", "content": prompt}]
    })
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
