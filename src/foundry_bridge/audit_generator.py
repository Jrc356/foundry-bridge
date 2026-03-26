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
from foundry_bridge.models import PlayerCharacter, Transcript
from foundry_bridge.note_generator import make_game_tools, validate_config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are the campaign continuity auditor for a D&D 5e tabletop RPG campaign.
Your task is to inspect transcripts against existing campaign data and return
operation-based CRUD changes in structured form.

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

Output contract:
- Return exactly one `TableChangeset` object for each table:
    entities, quests, threads, events, decisions, loot, important_quotes, combat_updates.
- Each table contains CRUD operation lists: creates, updates, deletes, merges.
- Use operation schema:
    - create: {confidence, description, data}
    - update: {id, confidence, description, changes}
    - delete: {id, confidence, description}
    - merge: {canonical_id, duplicate_id, confidence, description}
- Do not populate any temporary legacy compatibility fields.

REQUIRED tool-use rules:
- Before any create/update/delete/merge operation in a table, call the relevant search/list/get
    tool(s) to confirm current state.
- For update/delete/merge IDs, verify IDs exist first using get_*_by_id or equivalent search/list.
- Never invent IDs.
- Resolve quest_id/entity_id with tools whenever available.
- If an ID is unknown but a cross-reference is still needed, use `quest_name` or `entity_name`
    inside create `data` instead of inventing numeric IDs.
- Avoid repeating identical tool calls.

Confidence policy:
- Use `high` only when evidence is unambiguous and tool checks confirm actionability.
- Use `medium` or `low` when uncertainty remains after tool checks.
- Prefer false negatives over false positives.

Merge guidance:
- Use merge operations for duplicate records in all non-transcript tables when one row should be
    canonical and the other should be merged away.
- Merge operations must include concrete canonical_id and duplicate_id, both verified by tools.

Transcript interpretation:
- Transcript lines are formatted as "[ID:N][SPEAKER]: text".
- Use N as transcript_id when referencing quotes.
- Ignore clear out-of-character chatter that does not affect in-world continuity.
"""

_MODEL_STR = f"{os.environ.get('MODEL_PROVIDER', 'openai')}:{os.environ.get('MODEL', 'gpt-5.4')}"

_STRUCTURED_OUTPUT_PROMPT = (
    "Return only structured audit output matching the CRUD table schema. "
    "Do not emit narrative text."
)


# -- Tool input schemas --------------------------------------------------------

class _NoArgsInput(BaseModel):
    pass


_ALLOWED_CONFIDENCE = {"low", "medium", "high"}
_ALLOWED_CREATE_ENTITY_TYPES = {"npc", "location", "item", "faction", "other"}
_AUDIT_TABLES: tuple[str, ...] = (
    "entities",
    "quests",
    "threads",
    "events",
    "decisions",
    "loot",
    "important_quotes",
    "combat_updates",
)

_REQUIRED_CREATE_FIELDS_BY_TABLE: dict[str, tuple[str, ...]] = {
    "entities": ("name", "entity_type", "description"),
    "quests": ("name", "description"),
    "threads": ("text",),
    "events": ("text",),
    "decisions": ("decision", "made_by"),
    "loot": ("item_name", "acquired_by"),
    "important_quotes": ("text",),
    "combat_updates": ("encounter", "outcome"),
}


def _is_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


# -- Output schema -------------------------------------------------------------

class CreateOp(BaseModel):
    confidence: Literal["low", "medium", "high"]
    description: str
    data: dict[str, Any] = Field(default_factory=dict)


class UpdateOp(BaseModel):
    id: int
    confidence: Literal["low", "medium", "high"]
    description: str
    changes: dict[str, Any] = Field(default_factory=dict)


class DeleteOp(BaseModel):
    id: int
    confidence: Literal["low", "medium", "high"]
    description: str


class MergeOp(BaseModel):
    canonical_id: int
    duplicate_id: int
    confidence: Literal["low", "medium", "high"]
    description: str


class TableChangeset(BaseModel):
    creates: list[CreateOp] = Field(default_factory=list)
    updates: list[UpdateOp] = Field(default_factory=list)
    deletes: list[DeleteOp] = Field(default_factory=list)
    merges: list[MergeOp] = Field(default_factory=list)


class AuditOutput(BaseModel):
    entities: TableChangeset = Field(default_factory=TableChangeset)
    quests: TableChangeset = Field(default_factory=TableChangeset)
    threads: TableChangeset = Field(default_factory=TableChangeset)
    events: TableChangeset = Field(default_factory=TableChangeset)
    decisions: TableChangeset = Field(default_factory=TableChangeset)
    loot: TableChangeset = Field(default_factory=TableChangeset)
    important_quotes: TableChangeset = Field(default_factory=TableChangeset)
    combat_updates: TableChangeset = Field(default_factory=TableChangeset)

    # TEMPORARY: Legacy compatibility bridge for pre-Chunk-3 call sites.
    # Remove these fields once the DB writer and callers are migrated.
    entity_description_updates: list[dict[str, Any]] = Field(default_factory=list)
    quest_description_updates: list[dict[str, Any]] = Field(default_factory=list)
    quest_status_updates: list[dict[str, Any]] = Field(default_factory=list)
    thread_resolutions: list[dict[str, Any]] = Field(default_factory=list)
    new_entities: list[dict[str, Any]] = Field(default_factory=list)
    new_events: list[dict[str, Any]] = Field(default_factory=list)
    new_decisions: list[dict[str, Any]] = Field(default_factory=list)
    new_loot: list[dict[str, Any]] = Field(default_factory=list)
    new_quests: list[dict[str, Any]] = Field(default_factory=list)
    new_threads: list[dict[str, Any]] = Field(default_factory=list)
    new_quotes: list[dict[str, Any]] = Field(default_factory=list)
    new_combat: list[dict[str, Any]] = Field(default_factory=list)
    thread_text_updates: list[dict[str, Any]] = Field(default_factory=list)
    event_text_updates: list[dict[str, Any]] = Field(default_factory=list)
    decision_corrections: list[dict[str, Any]] = Field(default_factory=list)
    loot_corrections: list[dict[str, Any]] = Field(default_factory=list)
    quote_corrections: list[dict[str, Any]] = Field(default_factory=list)
    audit_flags: list[dict[str, Any]] = Field(default_factory=list)


def _validate_create_data(table_name: str, data: Any) -> Optional[dict[str, Any]]:
    if not isinstance(data, dict):
        return None

    normalized: dict[str, Any] = dict(data)
    for field_name in _REQUIRED_CREATE_FIELDS_BY_TABLE[table_name]:
        if not _is_str(normalized.get(field_name)):
            return None

    if table_name == "entities":
        raw_entity_type = normalized.get("entity_type")
        if not isinstance(raw_entity_type, str):
            return None
        entity_type = raw_entity_type.strip().lower()
        if entity_type not in _ALLOWED_CREATE_ENTITY_TYPES:
            return None
        normalized["entity_type"] = entity_type

    if table_name == "quests":
        status = normalized.get("status", "active")
        if not isinstance(status, str) or status.strip().lower() not in {"active", "completed"}:
            return None
        normalized["status"] = status.strip().lower()

    if table_name == "threads" and "quest_id" in normalized and normalized["quest_id"] is not None:
        if not _is_int(normalized["quest_id"]):
            return None

    if table_name == "loot" and "quest_id" in normalized and normalized["quest_id"] is not None:
        if not _is_int(normalized["quest_id"]):
            return None

    if table_name == "important_quotes" and "transcript_id" in normalized and normalized["transcript_id"] is not None:
        if not _is_int(normalized["transcript_id"]):
            return None

    return normalized


def _validate_audit_output(output: AuditOutput, *, game_id: int) -> AuditOutput:
    dropped = 0
    dropped_empty_update = 0

    for table_name in _AUDIT_TABLES:
        changeset = getattr(output, table_name)

        valid_creates: list[CreateOp] = []
        for op in changeset.creates:
            if op.confidence not in _ALLOWED_CONFIDENCE or not _is_str(op.description):
                dropped += 1
                continue
            validated_data = _validate_create_data(table_name, op.data)
            if validated_data is None:
                dropped += 1
                continue
            op.data = validated_data
            valid_creates.append(op)

        valid_updates: list[UpdateOp] = []
        for op in changeset.updates:
            if not _is_int(op.id) or op.confidence not in _ALLOWED_CONFIDENCE or not _is_str(op.description):
                dropped += 1
                continue
            if not isinstance(op.changes, dict):
                dropped += 1
                continue
            if not op.changes:
                dropped_empty_update += 1
                continue
            valid_updates.append(op)

        valid_deletes: list[DeleteOp] = []
        for op in changeset.deletes:
            if not _is_int(op.id) or op.confidence not in _ALLOWED_CONFIDENCE or not _is_str(op.description):
                dropped += 1
                continue
            valid_deletes.append(op)

        valid_merges: list[MergeOp] = []
        for op in changeset.merges:
            if (
                not _is_int(op.canonical_id)
                or not _is_int(op.duplicate_id)
                or op.confidence not in _ALLOWED_CONFIDENCE
                or not _is_str(op.description)
            ):
                dropped += 1
                continue
            valid_merges.append(op)

        changeset.creates = valid_creates
        changeset.updates = valid_updates
        changeset.deletes = valid_deletes
        changeset.merges = valid_merges

    if dropped_empty_update:
        logger.warning(
            "Dropped %d audit update operations with empty changes dict (game_id=%d)",
            dropped_empty_update,
            game_id,
        )
    if dropped:
        logger.warning(
            "Dropped %d invalid audit operations from generator output (game_id=%d)",
            dropped,
            game_id,
        )

    return output


def _append_compat_audit_flag(
    audit_flags: list[dict[str, Any]],
    *,
    operation: str,
    table_name: str,
    confidence: str,
    description: str,
    target_id: Optional[int],
    suggested_change: Optional[dict[str, Any]] = None,
) -> None:
    audit_flags.append(
        {
            "operation": operation,
            "table_name": table_name,
            "confidence": confidence,
            "target_id": target_id,
            "description": description,
            "suggested_change": suggested_change or {},
        }
    )


def _apply_legacy_compat_bridge(output: AuditOutput) -> None:
    """TEMPORARY: Backfill legacy fields until Chunk 3 migrates downstream consumers."""
    output.entity_description_updates = []
    output.quest_description_updates = []
    output.quest_status_updates = []
    output.thread_resolutions = []
    output.new_entities = []
    output.new_events = []
    output.new_decisions = []
    output.new_loot = []
    output.new_quests = []
    output.new_threads = []
    output.new_quotes = []
    output.new_combat = []
    output.thread_text_updates = []
    output.event_text_updates = []
    output.decision_corrections = []
    output.loot_corrections = []
    output.quote_corrections = []
    output.audit_flags = []

    create_targets: dict[str, list[dict[str, Any]]] = {
        "entities": output.new_entities,
        "quests": output.new_quests,
        "threads": output.new_threads,
        "events": output.new_events,
        "decisions": output.new_decisions,
        "loot": output.new_loot,
        "important_quotes": output.new_quotes,
        "combat_updates": output.new_combat,
    }

    for table_name in _AUDIT_TABLES:
        changeset = getattr(output, table_name)

        for op in changeset.creates:
            if op.confidence == "high":
                create_targets[table_name].append(op.data)
                continue
            _append_compat_audit_flag(
                output.audit_flags,
                operation="create",
                table_name=table_name,
                confidence=op.confidence,
                description=op.description,
                target_id=None,
                suggested_change=op.data,
            )

        for op in changeset.updates:
            if op.confidence == "high":
                if table_name == "entities" and _is_str(op.changes.get("description")):
                    output.entity_description_updates.append(
                        {"entity_id": op.id, "description": op.changes["description"]}
                    )
                    continue
                if table_name == "quests":
                    if _is_str(op.changes.get("description")):
                        output.quest_description_updates.append(
                            {"quest_id": op.id, "description": op.changes["description"]}
                        )
                    status_value = op.changes.get("status")
                    if isinstance(status_value, str) and status_value in {"active", "completed"}:
                        output.quest_status_updates.append({"quest_id": op.id, "status": status_value})
                    if (
                        _is_str(op.changes.get("description"))
                        or isinstance(status_value, str) and status_value in {"active", "completed"}
                    ):
                        continue
                if table_name == "threads":
                    if _is_str(op.changes.get("resolution")):
                        output.thread_resolutions.append(
                            {"thread_id": op.id, "resolution": op.changes["resolution"]}
                        )
                    if _is_str(op.changes.get("text")):
                        output.thread_text_updates.append({"thread_id": op.id, "text": op.changes["text"]})
                    if _is_str(op.changes.get("resolution")) or _is_str(op.changes.get("text")):
                        continue
                if table_name == "events" and _is_str(op.changes.get("text")):
                    output.event_text_updates.append({"event_id": op.id, "text": op.changes["text"]})
                    continue
                if table_name == "decisions" and _is_str(op.changes.get("decision")):
                    correction: dict[str, Any] = {"decision_id": op.id, "decision": op.changes["decision"]}
                    if _is_str(op.changes.get("made_by")):
                        correction["made_by"] = op.changes["made_by"]
                    output.decision_corrections.append(correction)
                    continue
                if table_name == "loot":
                    correction = {"loot_id": op.id}
                    if _is_str(op.changes.get("item_name")):
                        correction["item_name"] = op.changes["item_name"]
                    if _is_str(op.changes.get("acquired_by")):
                        correction["acquired_by"] = op.changes["acquired_by"]
                    if _is_int(op.changes.get("quest_id")):
                        correction["quest_id"] = op.changes["quest_id"]
                    if len(correction) > 1:
                        output.loot_corrections.append(correction)
                        continue
                if table_name == "important_quotes":
                    correction = {"quote_id": op.id}
                    if _is_str(op.changes.get("text")):
                        correction["text"] = op.changes["text"]
                    if op.changes.get("speaker") is None or _is_str(op.changes.get("speaker")):
                        correction["speaker"] = op.changes.get("speaker")
                    if _is_int(op.changes.get("transcript_id")) or op.changes.get("transcript_id") is None:
                        correction["transcript_id"] = op.changes.get("transcript_id")
                    if len(correction) > 1:
                        output.quote_corrections.append(correction)
                        continue

            _append_compat_audit_flag(
                output.audit_flags,
                operation="update",
                table_name=table_name,
                confidence=op.confidence,
                description=op.description,
                target_id=op.id,
                suggested_change={"changes": op.changes},
            )

        for op in changeset.deletes:
            _append_compat_audit_flag(
                output.audit_flags,
                operation="delete",
                table_name=table_name,
                confidence=op.confidence,
                description=op.description,
                target_id=op.id,
                suggested_change={"id": op.id},
            )

        for op in changeset.merges:
            _append_compat_audit_flag(
                output.audit_flags,
                operation="merge",
                table_name=table_name,
                confidence=op.confidence,
                description=op.description,
                target_id=op.duplicate_id,
                suggested_change={"canonical_id": op.canonical_id, "duplicate_id": op.duplicate_id},
            )


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
    audit_output = _validate_audit_output(audit_output, game_id=game_id)
    _apply_legacy_compat_bridge(audit_output)
    logger.info(
        "Audit LLM returned CRUD changes: "
        "entities(c/u/d/m)=%d/%d/%d/%d quests=%d/%d/%d/%d threads=%d/%d/%d/%d "
        "events=%d/%d/%d/%d decisions=%d/%d/%d/%d loot=%d/%d/%d/%d quotes=%d/%d/%d/%d "
        "combat=%d/%d/%d/%d | legacy(new_entities=%d new_events=%d new_decisions=%d new_loot=%d "
        "new_quests=%d new_threads=%d new_quotes=%d new_combat=%d entity_updates=%d "
        "quest_desc_updates=%d quest_status_updates=%d thread_resolutions=%d thread_text_updates=%d "
        "event_text_updates=%d decision_corrections=%d loot_corrections=%d quote_corrections=%d audit_flags=%d)",
        len(audit_output.entities.creates),
        len(audit_output.entities.updates),
        len(audit_output.entities.deletes),
        len(audit_output.entities.merges),
        len(audit_output.quests.creates),
        len(audit_output.quests.updates),
        len(audit_output.quests.deletes),
        len(audit_output.quests.merges),
        len(audit_output.threads.creates),
        len(audit_output.threads.updates),
        len(audit_output.threads.deletes),
        len(audit_output.threads.merges),
        len(audit_output.events.creates),
        len(audit_output.events.updates),
        len(audit_output.events.deletes),
        len(audit_output.events.merges),
        len(audit_output.decisions.creates),
        len(audit_output.decisions.updates),
        len(audit_output.decisions.deletes),
        len(audit_output.decisions.merges),
        len(audit_output.loot.creates),
        len(audit_output.loot.updates),
        len(audit_output.loot.deletes),
        len(audit_output.loot.merges),
        len(audit_output.important_quotes.creates),
        len(audit_output.important_quotes.updates),
        len(audit_output.important_quotes.deletes),
        len(audit_output.important_quotes.merges),
        len(audit_output.combat_updates.creates),
        len(audit_output.combat_updates.updates),
        len(audit_output.combat_updates.deletes),
        len(audit_output.combat_updates.merges),
        len(audit_output.new_entities),
        len(audit_output.new_events),
        len(audit_output.new_decisions),
        len(audit_output.new_loot),
        len(audit_output.new_quests),
        len(audit_output.new_threads),
        len(audit_output.new_quotes),
        len(audit_output.new_combat),
        len(audit_output.entity_description_updates),
        len(audit_output.quest_description_updates),
        len(audit_output.quest_status_updates),
        len(audit_output.thread_resolutions),
        len(audit_output.thread_text_updates),
        len(audit_output.event_text_updates),
        len(audit_output.decision_corrections),
        len(audit_output.loot_corrections),
        len(audit_output.quote_corrections),
        len(audit_output.audit_flags),
    )
    return audit_output
