-- =============================================================================
-- Scenario 1: First Session — "The Tavern Encounter"
-- =============================================================================
-- A brand-new campaign with no prior notes, entities, or threads.
-- The party arrives at the Rusty Flagon Inn in Millhaven, meets the NPC
-- barkeep Moran, hears about a missing merchant caravan, and agrees to
-- investigate. Pip secretly pockets a mysterious iron key.
--
-- Expected note taker output (verify after running the pipeline):
--   summary   : party arrives in Millhaven, learns of the missing Hartwell
--               caravan from barkeep Moran, and agrees to investigate
--   entities  : NPC "Moran" (dwarf barkeep at the Rusty Flagon)
--               Location "Rusty Flagon Inn" (tavern in Millhaven)
--               Location "Millhaven" (town)
--               Quest/other "Missing Hartwell Caravan"
--   threads   : "What happened to the Hartwell merchant caravan?"
--   loot      : mysterious iron key → Pip
--   decisions : investigate the missing caravan → the party
-- =============================================================================

-- ─── Cleanup (idempotent re-run) ────────────────────────────────────────────
DO $$
DECLARE _gid BIGINT;
BEGIN
    SELECT id INTO _gid FROM games
    WHERE hostname = 'foundry.local' AND world_id = 'world-first-session';

    IF _gid IS NOT NULL THEN
        DELETE FROM notes_events      WHERE note_id IN (SELECT id FROM notes WHERE game_id = _gid);
        DELETE FROM notes_loot        WHERE note_id IN (SELECT id FROM notes WHERE game_id = _gid);
        DELETE FROM important_quotes  WHERE game_id = _gid;
        DELETE FROM combat_updates    WHERE game_id = _gid;
        DELETE FROM decisions         WHERE game_id = _gid;
        UPDATE threads SET resolved_by_note_id = NULL WHERE game_id = _gid;
        DELETE FROM notes             WHERE game_id = _gid;
        DELETE FROM events            WHERE game_id = _gid;
        DELETE FROM loot              WHERE game_id = _gid;
        DELETE FROM entities          WHERE game_id = _gid;
        DELETE FROM threads           WHERE game_id = _gid;
        DELETE FROM player_characters WHERE game_id = _gid;
        DELETE FROM transcripts       WHERE game_id = _gid;
        DELETE FROM games             WHERE id      = _gid;
    END IF;
END;
$$;

-- ─── Seed ───────────────────────────────────────────────────────────────────
DO $$
DECLARE
    _gid BIGINT;
BEGIN
    -- Game
    INSERT INTO games (hostname, world_id, name)
    VALUES ('foundry.local', 'world-first-session', 'The Rusted Flagon Campaign')
    RETURNING id INTO _gid;

    -- Player characters
    INSERT INTO player_characters (game_id, character_name)
    VALUES
        (_gid, 'Aldric'),
        (_gid, 'Zara'),
        (_gid, 'Pip');

    -- 14 unprocessed transcripts — the note taker processes all of these
    INSERT INTO transcripts
        (game_id, participant_id, character_name, turn_index, text,
         audio_window_start, audio_window_end, end_of_turn_confidence, note_taker_processed)
    VALUES
      (_gid, 'sess-dm-001',     'DM',     1,
       'You arrive at the Rusty Flagon Inn as the sun sets over the town of Millhaven. The common room is warm and smells of stew and sawdust.',
       0.0,   8.4, 0.98, false),

      (_gid, 'sess-aldric-001', 'Aldric', 2,
       'I push open the heavy oak door and take a moment to scan the room for threats before stepping inside.',
       8.5,  13.1, 0.95, false),

      (_gid, 'sess-zara-001',   'Zara',   3,
       'Keep it casual, Aldric. We are travelers, not soldiers. I walk to the bar and take a seat.',
       13.2, 18.7, 0.97, false),

      (_gid, 'sess-dm-001',     'DM',     4,
       'Behind the bar stands a stout dwarf with a grey beard and sharp eyes. He eyes the three of you with cautious warmth.',
       18.8, 25.0, 0.99, false),

      (_gid, 'sess-pip-001',    'Pip',    5,
       'I sidle up to the bar beside Zara. To the barkeep — what is the word around here, friend? Anything interesting happening in Millhaven?',
       25.1, 31.4, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     6,
       'The dwarf leans forward and lowers his voice. Name is Moran. And the word is trouble. A merchant family — the Hartwells — their caravan went missing three days ago on the eastern road. No ransom note. No bodies. Their wagon tracks just end at the old millstone marker.',
       31.5, 44.2, 0.99, false),

      (_gid, 'sess-aldric-001', 'Aldric', 7,
       'Missing? What kind of trouble? Bandits? Monsters?',
       44.3, 49.1, 0.94, false),

      (_gid, 'sess-dm-001',     'DM',     8,
       'Moran shakes his head. If it were bandits there would be a ransom demand by now. If monsters, we would have found remains. It is the not-knowing that has everyone spooked.',
       49.2, 58.6, 0.98, false),

      (_gid, 'sess-zara-001',   'Zara',   9,
       'I quietly cast Detect Magic while pretending to study the drink menu. Are there any magical auras in this room?',
       58.7, 64.5, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     10,
       'Zara, you sense a faint transmutation aura coming from a small iron key hanging on a nail behind the bar. Nothing else registers.',
       64.6, 72.1, 0.99, false),

      (_gid, 'sess-pip-001',    'Pip',    11,
       'While Moran is distracted chatting with Aldric, I reach over the bar and pocket the key. Sleight of Hand.',
       72.2, 78.3, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     12,
       'Roll it. Seventeen. The key disappears into your vest. Moran notices nothing.',
       78.4, 84.0, 0.97, false),

      (_gid, 'sess-zara-001',   'Zara',   13,
       'The Hartwell disappearance could be connected to something much larger. I think we should investigate — we owe it to this town.',
       84.1, 90.8, 0.97, false),

      (_gid, 'sess-aldric-001', 'Aldric', 14,
       'Agreed. I will ask Moran for lodging tonight and everything he knows about the eastern road and the millstone marker.',
       90.9, 98.2, 0.95, false);
END;
$$;
