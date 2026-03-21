-- =============================================================================
-- Scenario 3: Complex State — "The Dungeon Delve"
-- =============================================================================
-- Session 7. The note taker must ignore 5 already-processed transcripts from
-- the first half of the session and generate notes only from the 18 new
-- unprocessed turns. Those turns span two distinct combat encounters, multiple
-- loot pickups, and a dramatic speech from Zara that should surface as an
-- important quote.
--
-- Key inputs:
--   5  transcripts with note_taker_processed = true  → must be SKIPPED
--  18  transcripts with note_taker_processed = false → the note taker target
--   1  prior note (session context from earlier in session 7)
--   4  player characters (Aldric, Zara, Pip, Theron)
--
-- Expected note taker output (verify after running the pipeline):
--   summary   : party clears a goblin-held chamber, then defeats the
--               necromancer Xerith the Pale in his throne room; Zara is briefly
--               downed and revived by Theron
--   entities  : NPC "Xerith the Pale" (necromancer, defeated)
--               Location "Ironspire Dungeon — Throne Room"
--   combat    : Eight goblins in green-torchlit chamber → all defeated
--               Xerith the Pale + two skeleton guardians → Xerith defeated,
--               Zara downed and stabilised by Theron's revivify scroll
--   loot      : silver necklace with cracked emerald pendant → Pip
--               ring of keys → Pip
--               spellbook (three 5th-level spells) → Zara
--               amulet of protection → the party
--               wand of magic missiles → Pip
--               300 gold pieces → the party
--               sealed letter addressed to the Hollow King → the party
--   decisions : read the sealed letter to find the Hollow King → the party
--   threads   : "Who or what is the Hollow King?" (new, open)
--   quotes    : Zara's speech to Xerith before the boss fight (turn 16)
-- =============================================================================

-- ─── Cleanup (idempotent re-run) ────────────────────────────────────────────
DO $$
DECLARE _gid BIGINT;
BEGIN
    SELECT id INTO _gid FROM games
    WHERE hostname = 'foundry.local' AND world_id = 'world-dungeon-delve';

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
    VALUES ('foundry.local', 'world-dungeon-delve', 'Ironspire Dungeon — Session 7')
    RETURNING id INTO _gid;

    -- Player characters (4-person party)
    INSERT INTO player_characters (game_id, character_name)
    VALUES
        (_gid, 'Aldric'),
        (_gid, 'Zara'),
        (_gid, 'Pip'),
        (_gid, 'Theron');

    -- Prior context: note generated from the first half of session 7
    -- (those 5 processed transcripts were already handled by an earlier pipeline run)
    INSERT INTO notes (game_id, summary, source_transcript_ids)
    VALUES (
        _gid,
        'The party descended to the second level of Ironspire Dungeon. Pip disarmed two spike-trap pressure plates in a trapped corridor and Zara dispelled a magical alarm ward on a far door. Advancing carefully, the party heard goblin voices beyond the door and prepared to engage.',
        ARRAY[]::BIGINT[]
    );

    -- ── Already-processed transcripts (5 turns) ──────────────────────────────
    -- These represent the first half of session 7 that was already processed.
    -- note_taker_processed = true → the note taker must skip all of them.
    INSERT INTO transcripts
        (game_id, participant_id, character_name, turn_index, text,
         audio_window_start, audio_window_end, end_of_turn_confidence, note_taker_processed)
    VALUES
      (_gid, 'sess-dm-001',     'DM',    1,
       'Welcome back, everyone. You stand at the entrance to the second level of Ironspire Dungeon, torches lit, ready to push deeper.',
       0.0,   5.8, 0.98, true),

      (_gid, 'sess-pip-001',    'Pip',   2,
       'I check the floor ahead for pressure plates before anyone moves forward.',
       5.9,  10.1, 0.95, true),

      (_gid, 'sess-dm-001',     'DM',    3,
       'Good call. Pip, you spot two spike-trap pressure plates in the next ten feet. You disarm both cleanly.',
       10.2, 17.6, 0.99, true),

      (_gid, 'sess-zara-001',   'Zara',  4,
       'I cast Detect Magic on the corridor ahead. I am picking up a magical alarm ward on the iron door at the far end.',
       17.7, 23.0, 0.96, true),

      (_gid, 'sess-dm-001',     'DM',    5,
       'Zara dispels the ward. You advance quietly to the door. Beyond it you can hear voices — goblins, multiple, completely careless.',
       23.1, 32.4, 0.99, true);

    -- ── Unprocessed transcripts (18 turns) ───────────────────────────────────
    -- These are the note taker's actual target for this run.
    -- note_taker_processed = false → all 18 must be processed.
    INSERT INTO transcripts
        (game_id, participant_id, character_name, turn_index, text,
         audio_window_start, audio_window_end, end_of_turn_confidence, note_taker_processed)
    VALUES
      -- Combat 1: goblin chamber
      (_gid, 'sess-dm-001',     'DM',      6,
       'The door swings open. You enter a wide chamber lit by sickly green torchlight. Eight goblins squat around a fire pit gnawing on bones. They have not noticed you yet.',
       32.5,  41.2, 0.99, false),

      (_gid, 'sess-pip-001',    'Pip',     7,
       'I signal the others to fan out. On Aldric''s count we rush them before they can raise any alarm.',
       41.3,  46.7, 0.95, false),

      (_gid, 'sess-theron-001', 'Theron',  8,
       'I hold back at range and ready Spiritual Weapon in case any of them break and run.',
       46.8,  52.0, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',      9,
       'Combat. Six rounds. All eight goblins are defeated. Aldric takes twelve points of damage from a javelin. Theron, you heal him for eight with Cure Wounds.',
       52.1,  64.5, 0.99, false),

      (_gid, 'sess-aldric-001', 'Aldric', 10,
       'Search the room. Anything worth taking before we move on?',
       64.6,  67.9, 0.94, false),

      (_gid, 'sess-dm-001',     'DM',     11,
       'Pip finds: a silver necklace with a cracked emerald pendant, a ring of keys that likely opens several doors on this level, and a crude hand-drawn map marking a door to the east labelled Master''s Chamber.',
       68.0,  78.6, 0.98, false),

      (_gid, 'sess-pip-001',    'Pip',    12,
       'I pocket the necklace and the keys. Zara, this map is yours.',
       78.7,  82.9, 0.95, false),

      (_gid, 'sess-zara-001',   'Zara',   13,
       'Thank you, Pip.',
       83.0,  84.5, 0.97, false),

      -- Transition to boss room
      (_gid, 'sess-dm-001',     'DM',     14,
       'You follow the map east. The ring of keys opens the iron door on the first try. Beyond it: a cavernous throne room. Seated on a throne of bones is a figure robed in black — Xerith the Pale, a necromancer of considerable renown. He regards you without moving.',
       84.6, 100.1, 0.99, false),

      (_gid, 'sess-aldric-001', 'Aldric', 15,
       'Spread out. Do not let him focus fire on any one of us.',
       100.2, 103.8, 0.94, false),

      -- Zara's dramatic speech — should surface as an important quote
      (_gid, 'sess-zara-001',   'Zara',   16,
       'Xerith — this ends now. You have cursed the people of Thornwall, raised their dead against them, and stolen years of peace from the living. You will answer for every life you have taken.',
       103.9, 112.4, 0.97, false),

      -- Combat 2: boss fight
      (_gid, 'sess-dm-001',     'DM',     17,
       'Xerith rises slowly from the throne and smiles. Answer to whom, child? I have been perfecting the art of death for three hundred years. Two skeleton guardians rattle to their feet at his sides. Roll initiative.',
       112.5, 124.1, 0.99, false),

      (_gid, 'sess-dm-001',     'DM',     18,
       'Ten brutal rounds. In round four Zara is dropped to zero hit points by a necrotic bolt. Theron uses his revivify scroll to stabilise her immediately. Final blow: Aldric''s greataxe cleaves through Xerith''s chest. The necromancer crumbles to dust. The skeletal guardians collapse.',
       124.2, 140.4, 0.99, false),

      (_gid, 'sess-theron-001', 'Theron', 19,
       'I press the revivify scroll against Zara''s chest. Come on — stay with me.',
       140.5, 145.7, 0.96, false),

      (_gid, 'sess-zara-001',   'Zara',   20,
       'I gasp and sit up. Thank you, Theron. — What did Xerith leave behind?',
       145.8, 150.3, 0.97, false),

      (_gid, 'sess-dm-001',     'DM',     21,
       'On Xerith''s person: a spellbook containing three fifth-level spells, an amulet of protection, and a key of black iron. Behind the throne a hidden chest contains three hundred gold pieces, a wand of magic missiles, and a sealed letter addressed to someone called the Hollow King.',
       150.4, 166.1, 0.98, false),

      (_gid, 'sess-pip-001',    'Pip',    22,
       'I take the wand of magic missiles. Zara should have the spellbook — it is wasted on the rest of us.',
       166.2, 170.5, 0.95, false),

      (_gid, 'sess-zara-001',   'Zara',   23,
       'Agreed. And that sealed letter — we need to read it. It may be the only clue we have to who the Hollow King is and how to find them.',
       170.6, 177.9, 0.97, false);
END;
$$;
