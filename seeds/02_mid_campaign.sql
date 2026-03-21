-- =============================================================================
-- Scenario 2: Mid-Campaign — "Return to Thornwood"
-- =============================================================================
-- Session 4 of an ongoing campaign. The note taker already has prior context:
-- a session-3 summary note, two known entities, and two open threads.
--
-- The party rides into Thornwood Forest, fights mind-controlled wolves bearing
-- Lady Morvaine's insignia, discovers her personal journal and a letter that
-- reveals her true goal, and resolves both open threads while opening a new one.
--
-- Prior state (exercises context injection into the LLM prompt):
--   notes     : 1 session-3 summary
--   entities  : NPC "Lady Morvaine" (villain), Location "Thornwood Forest"
--   threads   : "Who is controlling the wolves in Thornwood Forest?" (open)
--               "What is Lady Morvaine's true goal?" (open)
--
-- Expected note taker output (verify after running the pipeline):
--   summary   : party defeats rune-collared dire wolves, finds Morvaine's
--               letter revealing her plan to bind an archfey at Thornwood Hollow
--   entities  : "Lady Morvaine" description UPDATED (new detail appended)
--               Location "Thornwood Hollow" (new)
--               Item "Wolf Collar with Runes" (new)
--   threads   : "Who is controlling the wolves?" → RESOLVED
--               "What is Lady Morvaine's true goal?" → RESOLVED
--               "Find Thornwood Hollow before Lady Morvaine" (new, open)
--   loot      : Lady Morvaine's Journal → the party
--               50 gold pieces → Pip
--               intact wolf collar → the party
--   combat    : Three rune-collared dire wolves in Thornwood Forest → all defeated
--   decisions : advance to Thornwood Hollow before Morvaine → the party
--   quotes    : Pip reading Morvaine's letter aloud (turn 11)
-- =============================================================================

-- ─── Cleanup (idempotent re-run) ────────────────────────────────────────────
DO $$
DECLARE _gid BIGINT;
BEGIN
    SELECT id INTO _gid FROM games
    WHERE hostname = 'foundry.local' AND world_id = 'world-mid-campaign';

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
    VALUES ('foundry.local', 'world-mid-campaign', 'The Thornwood Campaign — Session 4')
    RETURNING id INTO _gid;

    -- Player characters (established in prior sessions)
    INSERT INTO player_characters (game_id, character_name)
    VALUES
        (_gid, 'Aldric'),
        (_gid, 'Zara'),
        (_gid, 'Pip');

    -- Prior context: session 3 note
    -- The note taker loads up to 3 recent notes to inject into the LLM prompt.
    INSERT INTO notes (game_id, summary, source_transcript_ids)
    VALUES (
        _gid,
        'The party investigated the border village of Millhaven after reports of unnaturally aggressive wolf attacks. They spoke to the villagers, examined claw marks on collapsed fences, and found a scorched iron collar fragment near the treeline. A travelling herbalist named Sera warned them that the wolves seemed organised — driven by something beyond instinct. The party agreed to enter Thornwood Forest to find the source.',
        ARRAY[]::BIGINT[]
    );

    -- Prior context: known entities
    INSERT INTO entities (game_id, entity_type, name, description)
    VALUES
        (_gid, 'npc', 'Lady Morvaine',
         'A powerful and enigmatic mage linked to strange events in the Thornwood region. Her true motives and base of operations remain unknown. Villagers whisper that she commands the wolves.'),
        (_gid, 'location', 'Thornwood Forest',
         'A vast, ancient forest bordering Millhaven. The trees grow unnaturally dark even at midday. Wolf attacks in the region have intensified sharply over the past month.');

    -- Prior context: two open threads
    INSERT INTO threads (game_id, text, is_resolved)
    VALUES
        (_gid, 'Who is controlling the wolves in Thornwood Forest?', false),
        (_gid, 'What is Lady Morvaine''s true goal?',               false);

    -- 13 unprocessed transcripts — the note taker processes all of these
    INSERT INTO transcripts
        (game_id, participant_id, character_name, turn_index, text,
         audio_window_start, audio_window_end, end_of_turn_confidence, note_taker_processed)
    VALUES
      (_gid, 'sess-dm-001',     'DM',     1,
       'You ride into the outskirts of Thornwood Forest. The trees close overhead and the birdsong dies. Even at noon the light here is dim and greenish.',
       0.0,   8.3, 0.98, false),

      (_gid, 'sess-aldric-001', 'Aldric', 2,
       'I draw my sword. Last time we were here the wolves attacked without any warning.',
       8.4,  12.6, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     3,
       'Good instinct. Three dire wolves emerge from the undergrowth directly ahead — but they are wearing iron collars etched with faintly glowing runes.',
       12.7, 20.2, 0.99, false),

      (_gid, 'sess-pip-001',    'Pip',    4,
       'Controlled wolves — exactly what Sera warned us about. I draw both shortswords.',
       20.3, 24.5, 0.95, false),

      (_gid, 'sess-zara-001',   'Zara',   5,
       'I cast Thunderwave to push them back and break their formation before they can close the distance.',
       24.6, 29.9, 0.97, false),

      (_gid, 'sess-dm-001',     'DM',     6,
       'Thunderwave erupts. Two wolves are hurled prone into the undergrowth. The third charges Aldric. Roll initiative. — After six hard rounds, all three wolves are defeated. One collar remains intact.',
       30.0, 48.1, 0.99, false),

      (_gid, 'sess-aldric-001', 'Aldric', 7,
       'I pick up the intact collar and examine it closely. Any markings beyond the runes?',
       48.2, 52.9, 0.94, false),

      (_gid, 'sess-dm-001',     'DM',     8,
       'Yes. A crest — a moth over a crescent moon — and scratched below it in small letters: For M.V. Her initials. Lady Morvaine made these collars.',
       53.0, 62.2, 0.99, false),

      (_gid, 'sess-zara-001',   'Zara',   9,
       'The wolves were hers all along. That answers both questions we have been carrying.',
       62.3, 67.5, 0.97, false),

      (_gid, 'sess-dm-001',     'DM',     10,
       'Searching the den nearby, Pip finds a weathered satchel. Inside: Lady Morvaine''s personal journal, a pouch containing fifty gold pieces, and a sealed letter.',
       67.6, 76.7, 0.98, false),

      (_gid, 'sess-pip-001',    'Pip',    11,
       'I break the seal and read the letter aloud. It says: My goal is not conquest — it is to tear open the veil between worlds at Thornwood Hollow and bind an archfey to my will. The wolves are merely guardians to keep the uninitiated away.',
       76.8, 90.4, 0.96, false),

      (_gid, 'sess-zara-001',   'Zara',   12,
       'Binding an archfey — that is catastrophic. If she succeeds she would wield power over the entire fey realm. We have to reach Thornwood Hollow before she does.',
       90.5, 99.2, 0.97, false),

      (_gid, 'sess-aldric-001', 'Aldric', 13,
       'Agreed. We press forward now. Pip, keep the gold. Everyone move.',
       99.3, 103.6, 0.95, false);
END;
$$;
