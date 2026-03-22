-- =============================================================================
-- Scenario 1b: First Session Extended — "Investigation & Discoveries"
-- =============================================================================
-- Continues "The Tavern Encounter" with additional raw transcripts from the
-- party's investigation of the millstone marker on the eastern road, where they
-- discover signs of struggle and clues about the missing caravan.
--
-- This script assumes 01_first_session.sql has been run and the game exists.
-- It adds 12 additional transcripts (turns 15-26) to the first game session.
-- =============================================================================

DO $$
DECLARE
    _gid BIGINT;
BEGIN
    -- Fetch the existing game (should exist from 01_first_session.sql)
    SELECT id INTO _gid FROM games
    WHERE hostname = 'foundry.local' AND world_id = 'world-first-session';

    IF _gid IS NULL THEN
        RAISE EXCEPTION 'Game not found. Please run 01_first_session.sql first.';
    END IF;

    -- ─── Additional Transcripts (turns 15-26) ────────────────────────────────
    INSERT INTO transcripts
        (game_id, participant_id, character_name, turn_index, text,
         audio_window_start, audio_window_end, end_of_turn_confidence, note_taker_processed)
    VALUES
      (_gid, 'sess-dm-001',     'DM',     15,
       'The next morning, Moran provides you with a worn map of the eastern road and directions to the millstone marker. It is three hours ride from town.',
       98.3,  106.7, 0.97, false),

      (_gid, 'sess-pip-001',    'Pip',    16,
       'I check my pack, make sure the mysterious key is still secure in my vest, and suggest we head out immediately.',
       106.8, 112.5, 0.94, false),

      (_gid, 'sess-zara-001',   'Zara',   17,
       'We should rent horses from the stable keeper. It will be faster and we can cover more ground. Plus, we will not arrive exhausted.',
       112.6, 120.3, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     18,
       'You set out on horseback, taking the eastern road as it winds through farmland and then into sparse woodland. After about two hours, you notice the landscape becoming eerily quiet. No birds. No rustle of small animals.',
       120.4, 133.8, 0.98, false),

      (_gid, 'sess-aldric-001', 'Aldric', 19,
       'I draw my sword and signal for Zara and Pip to ready themselves. Something is wrong here.',
       133.9, 139.2, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     20,
       'As you round a bend in the road, you spot the stone millstone marker — a weathered cylindrical stone about five feet tall. Around it, the earth is disturbed. You see wagon ruts that lead off the main road to the north, and they end abruptly about fifty yards into the tree line. Near the ruts, you find fragments of broken pottery, a leather pouch containing dried herbs, and what appears to be scorch marks on several trees.',
       139.3, 164.9, 0.99, false),

      (_gid, 'sess-zara-001',   'Zara',   21,
       'Scorch marks? That suggests magic. And the dried herbs — this smells like someone was performing some kind of ritual. I use Detect Magic again to scan the area.',
       165.0, 173.2, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     22,
       'Your spell reveals lingering auras of conjuration and transmutation centered on the spot where the wagon ruts end. Whatever happened here involved powerful magic — perhaps a portal or teleportation. The auras are fading but still detectable.',
       173.3, 187.6, 0.99, false),

      (_gid, 'sess-aldric-001', 'Aldric', 23,
       'Teleportation. That is not bandits or monsters — this is organized and deliberate. We need to bring this information back to Moran and figure out who has the resources and knowledge to pull off something like this.',
       187.7, 199.1, 0.97, false),

      (_gid, 'sess-pip-001',    'Pip',    24,
       'Before we leave, I make a careful search of the area. I want to search the pouch more thoroughly and check for any other clues.',
       199.2, 206.8, 0.93, false),

      (_gid, 'sess-dm-001',     'DM',     25,
       'The pouch contains dried moonflower petals and ground silver dust — components for a high-level transmutation or conjuration spell. On the ground, you find a silver sigil carved into the bark of the largest scorched tree — two crescent moons flanking a central star. You have never seen this symbol before.',
       206.9, 228.4, 0.98, false),

      (_gid, 'sess-zara-001',   'Zara',   26,
       'That symbol — it looks deliberately placed. This is a calling card. Whoever took the Hartwell caravan wants people to know it was them.',
       228.5, 236.9, 0.97, false);

END;
$$;
