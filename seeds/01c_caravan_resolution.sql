-- =============================================================================
-- Scenario 2: Caravan Resolution — "The Hartwell Discovery"
-- =============================================================================
-- Concluded from Scenario 1b: the party discovers the fate of the missing
-- Hartwell merchant caravan and resolves the mystery. Includes additional
-- transcripts that describe finding and rescuing the caravan (or at minimum,
-- discovering its ultimate fate).
--
-- This script assumes 01_first_session.sql and 01b_first_session_extended.sql
-- have been run. It adds 14 additional transcripts (turns 27-40) to the game.
--
-- IMPORTANT: This file does NOT directly insert any thread records. Instead,
-- it provides transcripts that contain the story resolution, relying on the
-- note taker to recognize and close the "What happened to the Hartwell caravan?"
-- thread through its natural language processing.
-- =============================================================================

DO $$
DECLARE
    _gid BIGINT;
BEGIN
    -- Fetch the existing game
    SELECT id INTO _gid FROM games
    WHERE hostname = 'foundry.local' AND world_id = 'world-first-session';

    IF _gid IS NULL THEN
        RAISE EXCEPTION 'Game not found. Please run 01_first_session.sql and 01b_first_session_extended.sql first.';
    END IF;

    -- ─── Transcripts (turns 27-40): Following the Teleportation ──────────────
    INSERT INTO transcripts
        (game_id, participant_id, character_name, turn_index, text,
         audio_window_start, audio_window_end, end_of_turn_confidence, note_taker_processed)
    VALUES
      (_gid, 'sess-aldric-001', 'Aldric', 27,
       'The symbol troubles me. We should return to town and consult with Moran and the Hartwell family. They may recognize this sigil and help us understand what we are facing.',
       237.0, 244.2, 0.96, false),

      (_gid, 'sess-zara-001',   'Zara',   28,
       'Agreed. But before we leave, I will make a note of the exact location and the symbol. If we ever encounter it again, we need to be able to match it.',
       244.3, 252.5, 0.97, false),

      (_gid, 'sess-dm-001',     'DM',     29,
       'You return to Millhaven by late afternoon. Moran welcomes you back to the Rusty Flagon and immediately asks if you found anything. When you describe the scorch marks, the symbol, and the magical components, his weathered face grows pale.',
       252.6, 270.1, 0.98, false),

      (_gid, 'sess-dm-001',     'DM',     30,
       'Moran says: "That symbol — the crescent moons and star — that belongs to the Cult of the Moonlit Gate. They have plagued this region for years with kidnappings and disappearances. Many blame them for the vanishings in nearby settlements, but we have never had proof here in Millhaven until now." He invites you to meet with the Hartwell family at sunrise.',
       270.2, 289.8, 0.99, false),

      (_gid, 'sess-pip-001',    'Pip',    31,
       'I pull out the mysterious key we found and ask Moran if he has ever seen anything like it. Does it match the symbol? Could it be connected to the cult?',
       289.9, 298.4, 0.94, false),

      (_gid, 'sess-dm-001',     'DM',     32,
       'Moran examines the key closely. His eyes widen. He says he has never seen the like, but the craftsmanship is exquisite — dwarvish style, but corrupted. The silvery transmutation aura Zara sensed suggests it might unlock something magical or protected.',
       298.5, 313.7, 0.99, false),

      (_gid, 'sess-zara-001',   'Zara',   33,
       'The key is a mystery unto itself. But if this cult has taken the Hartwells, we need to find their stronghold and mount a rescue. Do we have any leads? Any safe places the cult might hide?',
       313.8, 322.4, 0.97, false),

      (_gid, 'sess-dm-001',     'DM',     34,
       'At your meeting with the Hartwell family the next morning, the merchant patriarch tells you of an old ruin deep in the Blackwood Forest — about two days travel north through difficult terrain. Local legends speak of a hidden temple dedicated to lunar worship. Many suspect the cult operates from there.',
       322.5, 340.8, 0.99, false),

      (_gid, 'sess-aldric-001', 'Aldric', 35,
       'Two days in difficult terrain to find a hidden temple occupied by cultists. We will need supplies, rest, and a solid plan. I suggest we prepare and set out tomorrow morning at first light.',
       340.9, 349.6, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     36,
       'You spend the day gathering supplies and resting. As the sun sets over Millhaven, you notice a figure in a dark cloak watching you from across the market square before they disappear into an alley. Someone is watching your movements. That night, you make camp on the outskirts of town.',
       349.7, 366.2, 0.98, false),

      (_gid, 'sess-pip-001',    'Pip',    37,
       'I keep the mysterious key close and post watch through the night. If that cloaked figure comes for us, they will find us ready.',
       366.3, 373.5, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     38,
       'Your watch is uneventful. You set out northward at dawn, pushing through increasingly dense forest. By midday, you spot the first signs of the ruin — crumbling stone walls overgrown with moss and vines. As you approach the main temple entrance, you hear chanting coming from deep within. It is a place of ritual and dark power.',
       373.6, 395.1, 0.99, false),

      (_gid, 'sess-aldric-001', 'Aldric', 39,
       'I draw my weapon and signal for silence. We go in carefully. Zara, stay ready with your magic. Pip, watch for traps. The Hartwells may still be alive somewhere in this place, and we are their only hope.',
       395.2, 407.8, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     40,
       'You descend the temple stairs. The air grows cold and thin. In a grand underground chamber, you discover the Hartwell caravan — but something is terribly wrong. The wagon is there, the cargo intact, but the family and their guards stand motionless, bound by magical chains of light that hover in the air. They are alive, but they are being kept frozen by a powerful enchantment. At the chamber''s center stands a tall figure in moonlit robes, hands raised in ritual. The figure''s face is obscured by shadow and hood. Zara, your Detect Magic screams of powerful conjuration magic. The figure speaks: "So, adventurers finally arrive. How... predictable."',
       407.9, 438.6, 0.99, false);

END;
$$;
