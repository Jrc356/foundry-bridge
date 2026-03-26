from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from typing import Any, Literal, Optional

from langchain.agents import create_agent
from langchain_core.tools import StructuredTool
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel, Field

import foundry_bridge.db as db
from foundry_bridge.models import EntityType, PlayerCharacter, Transcript
from foundry_bridge.note_generator import make_game_tools, validate_config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are the campaign continuity auditor for a D&D 5e tabletop RPG campaign.
Your task is to inspect transcripts against existing campaign data and propose
high-confidence corrections/additions in structured form.

You can use tools to inspect existing records and MUST use them before producing
updates. You are expected to operate with a conservative confidence policy.

Available tools:
- search_quests
- search_entities
- search_open_threads
- search_resolved_threads
- search_events
- search_past_notes
- search_decisions
- search_loot
- search_combat
- get_all_entities
- get_all_quests
- get_all_open_threads
- get_entity_by_id
- get_thread_by_id
- get_quest_by_id
- get_event_by_id
- get_decision_by_id
- get_loot_by_id
- get_note_by_id
- get_combat_by_id
- get_quote_by_id
- get_transcript_by_id

REQUIRED tool-use rules:
- Lookup before create: before proposing any item in new_entities/new_events/new_decisions/
  new_loot/new_quests/new_threads/new_quotes/new_combat, call the corresponding search
  tools first to verify it does not already exist.
- Verify IDs before correction/delete: before any correction/update/resolution that targets
    an existing row by ID, call the relevant search/list or get_*_by_id tool and confirm
    the ID exists.
  Never invent IDs.
- Quest ID resolution: any quest_id you output (for new_threads/new_loot/corrections) MUST
  be resolved via search_quests. Do not guess quest IDs.
- Entity description updates must be grounded in both transcript evidence and the current
  stored entity description from tools.
- Quest description/status updates must be grounded in transcript evidence and verified
  against existing quests from tools.
- Thread resolutions/text updates must verify the thread is currently open before output.
- Decision corrections must be verified via search_decisions.
- Loot corrections must be verified via search_loot.
- Quote corrections must be verified against transcript/note context via search_past_notes.
- Avoid calling the same tool with identical queries multiple times.

REQUIRED reconciliation workflow (execute in this exact order):
1) Thread state reconciliation
    - Start with get_all_open_threads, then use search_open_threads and search_resolved_threads
      to verify continuity state.
    - If an open thread is clearly resolved by transcript evidence, add thread_resolutions.
    - If a thread is missing and should exist, add new_threads.
2) Thread cleanup reconciliation
    - For duplicate/erroneous thread rows that should not exist, emit deletion_candidate flags
      with table="threads" and concrete record_id.
3) Entity (NPC/location/faction/item) reconciliation
    - Use get_all_entities + search_entities.
    - Update stale descriptions via entity_description_updates.
    - Create missing entities via new_entities when they are clearly present in transcript evidence.
    - For duplicate entities, prefer entity_duplicate (or deletion_candidate only when merge is
      not the right action).
4) Quest reconciliation
    - Use get_all_quests + search_quests.
    - Update quest text/status via quest_description_updates and quest_status_updates.
    - Create missing quests with new_quests only after verifying they do not already exist.
5) Event/decision/loot/quote/combat reconciliation
    - Verify each domain with its search tool before proposing new rows or corrections.
    - Use corrections only with confirmed IDs; use missing_* flags when low-confidence.
6) Final validation and flags
    - Before returning output, check for duplicates/conflicts across your own proposed changes.
    - Route all uncertain or ambiguous items to audit_flags using the allowed taxonomy and shapes.
    - Keep auto-apply fields for only unambiguous, high-confidence updates.

Confidence policy:
- Only put changes in auto-apply fields when transcript evidence is unambiguous.
- If uncertain or ambiguous, create an audit flag instead of auto-applying.
- Prefer false negatives over false positives for auto-apply fields.

Audit flag taxonomy and quality bar:
- You MUST use only these flag_type values:
    entity_duplicate | missing_entity | missing_event | missing_decision |
    missing_loot | loot_correction | decision_correction | deletion_candidate | other
- You MUST use only these target_type values when present:
    entity | quest | thread | loot | decision | note
- Never invent new flag_type values.
- Do NOT emit meta/process flags about prompt/tool limitations, missing IDs in preamble,
    generic transcript quality, or vague timeline uncertainty without a concrete proposed
    derived-data action.
- For duplicate/conflicting existing rows in quests/threads/entities/events/loot/decisions,
    prefer entity_duplicate or deletion_candidate (with concrete record_id) instead of other.
- Use other only for note-scoped manual review items that cannot be represented by another
    flag shape. Do not use other for table-row cleanup candidates.
- Each flag should be actionable by a human reviewer and tied to concrete evidence.
    Include specific transcript IDs in the description when possible.
- suggested_change must match the exact shape for the chosen flag_type:
    - entity_duplicate: {"canonical_id": int, "duplicate_id": int}
    - missing_entity: {"name": str, "entity_type": str, "description": str}
    - missing_event: {"text": str}
    - missing_decision: {"decision": str, "made_by": str}
    - missing_loot: {"item_name": str, "acquired_by": str}
    - loot_correction: {"loot_id": int, "new_item_name": str, "new_acquired_by": str}
        - decision_correction: {"decision_id": int, "new_decision": str, "new_made_by": str}
        - deletion_candidate: {"table": str, "record_id": int, "reason": str}
            where table MUST be one of: quests | threads | entities | events | loot | decisions | important_quotes
    - other: {"description": str, "proposed_action": str}
- If no actionable low-confidence issue exists, return audit_flags as an empty list.

Transcript interpretation:
- Transcript lines are formatted as "[ID:N][SPEAKER]: text".
- Use N as transcript_id when referencing quotes.
- Ignore clear out-of-character chatter that does not affect in-world continuity.
"""

_MODEL_STR = f"{os.environ.get('MODEL_PROVIDER', 'openai')}:{os.environ.get('MODEL', 'gpt-5.4')}"

_STRUCTURED_OUTPUT_PROMPT = (
    "Return only structured audit output. "
    "Populate high-confidence auto-apply fields only when evidence is clear; "
    "route uncertainty to audit_flags."
)


# -- Tool input schemas --------------------------------------------------------

class _NoArgsInput(BaseModel):
    pass


_ALLOWED_FLAG_TYPES = {
    "entity_duplicate",
    "missing_entity",
    "missing_event",
    "missing_decision",
    "missing_loot",
    "loot_correction",
    "decision_correction",
    "deletion_candidate",
    "other",
}

_ALLOWED_TARGET_TYPES = {
    "entity",
    "quest",
    "thread",
    "loot",
    "decision",
    "note",
}

_DELETION_TABLE_ALIASES = {
    "quest": "quests",
    "quests": "quests",
    "thread": "threads",
    "threads": "threads",
    "entity": "entities",
    "entities": "entities",
    "event": "events",
    "events": "events",
    "loot": "loot",
    "loots": "loot",
    "decision": "decisions",
    "decisions": "decisions",
    "quote": "important_quotes",
    "quotes": "important_quotes",
    "important_quote": "important_quotes",
    "important_quotes": "important_quotes",
}

_ALLOWED_DELETION_TABLES = {
    "quests",
    "threads",
    "entities",
    "events",
    "loot",
    "decisions",
    "important_quotes",
}


def _is_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_valid_suggested_change(flag_type: str, change: dict[str, Any]) -> bool:
    if flag_type == "entity_duplicate":
        return isinstance(change.get("canonical_id"), int) and isinstance(change.get("duplicate_id"), int)
    if flag_type == "missing_entity":
        return _is_str(change.get("name")) and _is_str(change.get("entity_type")) and _is_str(change.get("description"))
    if flag_type == "missing_event":
        return _is_str(change.get("text"))
    if flag_type == "missing_decision":
        return _is_str(change.get("decision")) and _is_str(change.get("made_by"))
    if flag_type == "missing_loot":
        return _is_str(change.get("item_name")) and _is_str(change.get("acquired_by"))
    if flag_type == "loot_correction":
        return (
            isinstance(change.get("loot_id"), int)
            and _is_str(change.get("new_item_name"))
            and _is_str(change.get("new_acquired_by"))
        )
    if flag_type == "decision_correction":
        return (
            isinstance(change.get("decision_id"), int)
            and _is_str(change.get("new_decision"))
            and _is_str(change.get("new_made_by"))
        )
    if flag_type == "deletion_candidate":
        table = change.get("table")
        return (
            isinstance(table, str)
            and table in _ALLOWED_DELETION_TABLES
            and isinstance(change.get("record_id"), int)
            and _is_str(change.get("reason"))
        )
    if flag_type == "other":
        return _is_str(change.get("description")) and _is_str(change.get("proposed_action"))
    return False


def _normalize_audit_flags(flags: list[AuditFlagOutput], *, game_id: int) -> list[AuditFlagOutput]:
    cleaned: list[AuditFlagOutput] = []
    dropped = 0

    for flag in flags:
        if flag.flag_type == "deletion_candidate":
            raw_table = flag.suggested_change.get("table")
            if isinstance(raw_table, str):
                canonical_table = _DELETION_TABLE_ALIASES.get(raw_table.strip().lower())
                if canonical_table is not None:
                    flag.suggested_change["table"] = canonical_table
        if flag.flag_type not in _ALLOWED_FLAG_TYPES:
            dropped += 1
            continue
        if flag.target_type is not None and flag.target_type not in _ALLOWED_TARGET_TYPES:
            dropped += 1
            continue
        if not _is_valid_suggested_change(flag.flag_type, flag.suggested_change):
            dropped += 1
            continue
        if not _is_str(flag.description):
            dropped += 1
            continue
        if flag.flag_type == "other" and flag.target_type != "note":
            dropped += 1
            continue
        cleaned.append(flag)

    if dropped:
        logger.warning(
            "Dropped %d invalid audit flags from generator output (game_id=%d kept=%d)",
            dropped,
            game_id,
            len(cleaned),
        )
    return cleaned


# -- Output schema -------------------------------------------------------------

class EntityDescriptionUpdate(BaseModel):
    entity_id: int
    description: str


class QuestDescriptionUpdate(BaseModel):
    quest_id: int
    description: str


class QuestStatusUpdate(BaseModel):
    quest_id: int
    status: Literal["active", "completed"]


class ThreadResolutionUpdate(BaseModel):
    thread_id: int
    resolution: str


class EntityOutput(BaseModel):
    entity_type: EntityType
    name: str
    description: str


class EventOutput(BaseModel):
    text: str


class DecisionOutput(BaseModel):
    decision: str
    made_by: str


class LootOutput(BaseModel):
    item_name: str
    acquired_by: str
    quest_id: Optional[int] = None


class QuestOutput(BaseModel):
    name: str
    description: str
    status: Literal["active", "completed"] = "active"


class ThreadOutput(BaseModel):
    text: str
    quest_id: Optional[int] = None


class QuoteOutput(BaseModel):
    text: str
    transcript_id: Optional[int] = None
    speaker: Optional[str] = None


class CombatOutput(BaseModel):
    encounter: str
    outcome: str


class ThreadTextUpdate(BaseModel):
    thread_id: int
    text: str


class EventTextUpdate(BaseModel):
    event_id: int
    text: str


class DecisionCorrection(BaseModel):
    decision_id: int
    decision: str
    made_by: Optional[str] = None


class LootCorrection(BaseModel):
    loot_id: int
    item_name: Optional[str] = None
    acquired_by: Optional[str] = None
    quest_id: Optional[int] = None


class QuoteCorrection(BaseModel):
    quote_id: int
    text: Optional[str] = None
    speaker: Optional[str] = None
    transcript_id: Optional[int] = None


class AuditFlagOutput(BaseModel):
    flag_type: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    description: str
    suggested_change: dict[str, Any] = Field(default_factory=dict)


class AuditOutput(BaseModel):
    entity_description_updates: list[EntityDescriptionUpdate] = Field(default_factory=list)
    quest_description_updates: list[QuestDescriptionUpdate] = Field(default_factory=list)
    quest_status_updates: list[QuestStatusUpdate] = Field(default_factory=list)
    thread_resolutions: list[ThreadResolutionUpdate] = Field(default_factory=list)
    new_entities: list[EntityOutput] = Field(default_factory=list)
    new_events: list[EventOutput] = Field(default_factory=list)
    new_decisions: list[DecisionOutput] = Field(default_factory=list)
    new_loot: list[LootOutput] = Field(default_factory=list)
    new_quests: list[QuestOutput] = Field(default_factory=list)
    new_threads: list[ThreadOutput] = Field(default_factory=list)
    new_quotes: list[QuoteOutput] = Field(default_factory=list)
    new_combat: list[CombatOutput] = Field(default_factory=list)
    thread_text_updates: list[ThreadTextUpdate] = Field(default_factory=list)
    event_text_updates: list[EventTextUpdate] = Field(default_factory=list)
    decision_corrections: list[DecisionCorrection] = Field(default_factory=list)
    loot_corrections: list[LootCorrection] = Field(default_factory=list)
    quote_corrections: list[QuoteCorrection] = Field(default_factory=list)
    audit_flags: list[AuditFlagOutput] = Field(default_factory=list)


# -- Prompt builders -----------------------------------------------------------

def _truncate_text(text: str, limit: int = 140) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 3]}..."


async def _build_context_preamble(game_id: int, player_characters: list[PlayerCharacter]) -> str:
    entities = await db.get_entities_for_game(game_id)
    quests = await db.get_quests_for_game(game_id)
    open_threads = await db.get_open_threads_for_game(game_id)

    entities_by_type: dict[str, list[str]] = defaultdict(list)
    for entity in entities:
        entities_by_type[str(entity.entity_type)].append(entity.name)

    lines: list[str] = ["## Context Preamble"]

    lines.append("### Entities by Type")
    if entities_by_type:
        for entity_type in sorted(entities_by_type):
            names = sorted(entities_by_type[entity_type])
            lines.append(f"- {entity_type} ({len(names)}): {', '.join(names)}")
    else:
        lines.append("- None")

    lines.append("\n### Quests")
    if quests:
        for quest in quests:
            lines.append(f"- [{quest.status}] {quest.name}")
    else:
        lines.append("- None")

    lines.append("\n### Open Threads")
    lines.append(f"- Count: {len(open_threads)}")
    if open_threads:
        for thread in open_threads:
            lines.append(f"- ID {thread.id}: {_truncate_text(thread.text)}")
    else:
        lines.append("- None")

    lines.append("\n### Player Characters")
    if player_characters:
        lines.append(", ".join(sorted(pc.character_name for pc in player_characters)))
    else:
        lines.append("None specified.")

    return "\n".join(lines)


def _build_user_prompt(transcripts: list[Transcript], context_preamble: str) -> str:
    lines = [context_preamble]
    lines.append("\n## Transcripts (format: [ID:N][SPEAKER]: text)")
    for transcript in sorted(transcripts, key=lambda t: t.turn_index):
        lines.append(f"[ID:{transcript.id}][{transcript.character_name}]: {transcript.text}")
    lines.append("\nAnalyze continuity and return structured audit output.")
    return "\n".join(lines)


# -- Tool assembly -------------------------------------------------------------

def _make_listing_tools(game_id: int) -> list:
    async def get_all_entities() -> str:
        start_time = time.time()
        logger.debug("get_all_entities invoked", extra={"game_id": game_id})
        try:
            rows = await db.get_entities_for_game(game_id)
            elapsed = time.time() - start_time
            if not rows:
                logger.info(
                    "get_all_entities returned no results",
                    extra={"game_id": game_id, "elapsed_sec": elapsed},
                )
                return "No entities found."
            logger.info(
                "get_all_entities succeeded",
                extra={"game_id": game_id, "result_count": len(rows), "elapsed_sec": elapsed},
            )
            return "\n".join(
                f"ID {row.id} [{row.entity_type}] {row.name}: {row.description}" for row in rows
            )
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                "get_all_entities failed",
                exc_info=True,
                extra={"game_id": game_id, "elapsed_sec": elapsed, "error": str(e)},
            )
            return f"Error listing entities: {str(e)}"

    async def get_all_quests() -> str:
        start_time = time.time()
        logger.debug("get_all_quests invoked", extra={"game_id": game_id})
        try:
            rows = await db.get_quests_for_game(game_id)
            elapsed = time.time() - start_time
            if not rows:
                logger.info(
                    "get_all_quests returned no results",
                    extra={"game_id": game_id, "elapsed_sec": elapsed},
                )
                return "No quests found."
            logger.info(
                "get_all_quests succeeded",
                extra={"game_id": game_id, "result_count": len(rows), "elapsed_sec": elapsed},
            )
            return "\n".join(
                f"ID {row.id} [{row.status}] {row.name}: {row.description}" for row in rows
            )
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                "get_all_quests failed",
                exc_info=True,
                extra={"game_id": game_id, "elapsed_sec": elapsed, "error": str(e)},
            )
            return f"Error listing quests: {str(e)}"

    async def get_all_open_threads() -> str:
        start_time = time.time()
        logger.debug("get_all_open_threads invoked", extra={"game_id": game_id})
        try:
            rows = await db.get_open_threads_for_game(game_id)
            elapsed = time.time() - start_time
            if not rows:
                logger.info(
                    "get_all_open_threads returned no results",
                    extra={"game_id": game_id, "elapsed_sec": elapsed},
                )
                return "No open threads found."
            logger.info(
                "get_all_open_threads succeeded",
                extra={"game_id": game_id, "result_count": len(rows), "elapsed_sec": elapsed},
            )
            return "\n".join(f"ID {row.id}: {row.text}" for row in rows)
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                "get_all_open_threads failed",
                exc_info=True,
                extra={"game_id": game_id, "elapsed_sec": elapsed, "error": str(e)},
            )
            return f"Error listing open threads: {str(e)}"

    return [
        StructuredTool.from_function(
            coroutine=get_all_entities,
            name="get_all_entities",
            description="List all non-deleted entities for this game with IDs, types, names, and descriptions.",
            args_schema=_NoArgsInput,
        ),
        StructuredTool.from_function(
            coroutine=get_all_quests,
            name="get_all_quests",
            description="List all non-deleted quests for this game with IDs, names, statuses, and descriptions.",
            args_schema=_NoArgsInput,
        ),
        StructuredTool.from_function(
            coroutine=get_all_open_threads,
            name="get_all_open_threads",
            description="List all non-deleted open threads for this game with IDs and text.",
            args_schema=_NoArgsInput,
        ),
    ]


def make_audit_tools(game_id: int) -> list:
    return [*make_game_tools(game_id), *_make_listing_tools(game_id)]


# -- Exported function ---------------------------------------------------------

async def generate_audit(
    game_id: int,
    transcripts: list[Transcript],
    player_characters: list[PlayerCharacter],
) -> AuditOutput:
    """Run the audit agent for a game and return structured audit actions/flags."""
    validate_config()
    tools = make_audit_tools(game_id)
    agent = create_agent(
        model=_MODEL_STR,
        tools=tools,
        response_format=AuditOutput,
        debug=os.getenv("LOG_LEVEL", "").lower() == "debug" or os.getenv("AGENT_DEBUG", "false").lower() == "true",
    )

    context_preamble = await _build_context_preamble(game_id, player_characters)
    prompt = _build_user_prompt(transcripts, context_preamble)
    logger.info(
        "Calling audit LLM: game_id=%d transcripts=%d prompt_chars=%d model=%s",
        game_id,
        len(transcripts),
        len(prompt),
        _MODEL_STR,
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
            "Audit agent recursion limit hit for game_id=%d",
            game_id,
        )
        raise

    audit_output = result["structured_response"]
    audit_output.audit_flags = _normalize_audit_flags(audit_output.audit_flags, game_id=game_id)
    logger.info(
        "Audit LLM returned: entity_updates=%d quest_desc_updates=%d quest_status_updates=%d thread_resolutions=%d "
        "new_entities=%d new_events=%d new_decisions=%d new_loot=%d new_quests=%d new_threads=%d "
        "new_quotes=%d new_combat=%d thread_text_updates=%d event_text_updates=%d decision_corrections=%d "
        "loot_corrections=%d quote_corrections=%d audit_flags=%d",
        len(audit_output.entity_description_updates),
        len(audit_output.quest_description_updates),
        len(audit_output.quest_status_updates),
        len(audit_output.thread_resolutions),
        len(audit_output.new_entities),
        len(audit_output.new_events),
        len(audit_output.new_decisions),
        len(audit_output.new_loot),
        len(audit_output.new_quests),
        len(audit_output.new_threads),
        len(audit_output.new_quotes),
        len(audit_output.new_combat),
        len(audit_output.thread_text_updates),
        len(audit_output.event_text_updates),
        len(audit_output.decision_corrections),
        len(audit_output.loot_corrections),
        len(audit_output.quote_corrections),
        len(audit_output.audit_flags),
    )
    return audit_output
