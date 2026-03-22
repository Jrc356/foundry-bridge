-- =============================================================================
-- Scenario 1e: Combat Continuation — "The High Priestess's Wrath"
-- =============================================================================
-- Continuation of the Blackwood Forest combat encounter. The party faces the
-- full fury of the High Priestess and her remaining cultists in an epic battle
-- that spans multiple rounds and tests their survival. Includes spell duels,
-- tactical repositioning, mounting casualties, special abilities, and the
-- climactic confrontation with powerful ritual magic.
--
-- This script assumes 01_first_session.sql has been run and the game exists.
-- It adds 125+ transcripts continuing from turn 151 onwards.
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

    -- ─── Additional Transcripts (turns 151-275) ────────────────────────────────
    INSERT INTO transcripts
        (game_id, participant_id, character_name, turn_index, text,
         audio_window_start, audio_window_end, end_of_turn_confidence, note_taker_processed)
    VALUES
      (_gid, 'sess-zara-001',   'Zara',   151,
       'I cast Counterspell. I will not let her complete whatever dark incantation she is attempting. My spell level check is 21.',
       1660.4, 1668.1, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     152,
       'Your Counterspell meets her dark magic and the two forces collide in a explosion of violet and black energy. Her spell is disrupted but not without cost — the magical backlash hits you. Make a Constitution saving throw, DC 16.',
       1668.2, 1681.5, 0.99, false),

      (_gid, 'sess-zara-001',   'Zara',   153,
       'I rolled a 14. That does not beat 16.',
       1681.6, 1684.4, 0.92, false),

      (_gid, 'sess-dm-001',     'DM',     154,
       'The backlash hits you hard. You take 16 damage from eldritch force. Your health is severely reduced and you can taste blood. You are now down to about 12 hit points. The High Priestess laughs, a sound like shattering glass.',
       1684.5, 1698.1, 0.98, false),

      (_gid, 'sess-pip-001',    'Pip',    155,
       'I see Zara is badly hurt. It is my turn. I move 40 feet around the clearing to flank the High Priestess with Aldric. I am going to use my action to attack her with my rapier. Attack roll... 20.',
       1698.2, 1710.7, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     156,
       'That hits. Roll damage.',
       1710.8, 1712.5, 0.90, false),

      (_gid, 'sess-pip-001',    'Pip',    157,
       'I rolled a 7 on the damage die, plus my Dexterity modifier of 4, so 11 damage.',
       1712.6, 1718.6, 0.94, false),

      (_gid, 'sess-dm-001',     'DM',     158,
       'Your rapier finds a gap in her robes and draws blood. She hisses in pain but barely slows. Now Aldric charges. He has been waiting for this moment.',
       1718.7, 1727.8, 0.97, false),

      (_gid, 'sess-aldric-001', 'Aldric', 159,
       'I charge directly at the High Priestess. I use my full movement to close the distance and then I attack with my greatsword. Attack roll... 19.',
       1727.9, 1737.3, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     160,
       'That hits. You are flanking with Pip, so you have advantage on your next attack if you want to use it. Roll damage for this one.',
       1737.4, 1746.5, 0.97, false),

      (_gid, 'sess-aldric-001', 'Aldric', 161,
       'I rolled a 9 and a 7 on the 2d6, plus my Strength modifier of 3. That is 19 damage. I want to use my bonus action to make another attack. My second attack roll is 16.',
       1746.6, 1757.8, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     162,
       'The second attack hits as well. Roll damage again.',
       1757.9, 1760.4, 0.91, false),

      (_gid, 'sess-aldric-001', 'Aldric', 163,
       'I rolled a 6 on the 2d6, plus 3 for Strength, so 9 damage.',
       1760.5, 1764.8, 0.92, false),

      (_gid, 'sess-dm-001',     'DM',     164,
       'You land two devastating blows on the High Priestess. Blood soaks through her crimson robes. She staggers but remains standing. She is wounded. One of the nearby cultists starts casting a spell to defend her.',
       1764.9, 1777.2, 0.98, false),

      (_gid, 'sess-dm-001',     'DM',     165,
       'The cultist casts Fireball targeting your group. Zara, Pip, and Aldric — all three of you need to make Dexterity saving throws, DC 15.',
       1777.3, 1786.9, 0.97, false),

      (_gid, 'sess-aldric-001', 'Aldric', 166,
       'I rolled an 18. I should be fine.',
       1787.0, 1789.8, 0.91, false),

      (_gid, 'sess-zara-001',   'Zara',   167,
       'I got a 12. I fail.',
       1789.9, 1792.0, 0.89, false),

      (_gid, 'sess-pip-001',    'Pip',    168,
       'I rolled a 19. I made it.',
       1792.1, 1794.2, 0.90, false),

      (_gid, 'sess-dm-001',     'DM',     169,
       'Aldric and Pip take half damage — 14 fire damage each. Zara takes full — 28 fire damage.',
       1794.3, 1802.4, 0.96, false),

      (_gid, 'sess-zara-001',   'Zara',   170,
       'Oh no. That drops me below 0. I am down. I am making death saves.',
       1802.5, 1807.4, 0.94, false),

      (_gid, 'sess-dm-001',     'DM',     171,
       'Zara falls to the ground, life draining from her. She is unconscious and at risk of dying. The party is now reduced to two conscious members facing a wounded but powerful High Priestess and nine remaining cultists.',
       1807.5, 1821.8, 0.98, false),

      (_gid, 'sess-pip-001',    'Pip',    172,
       'No! Zara is down! I have to do something. I drop my weapon and move to her side. Can I use a healing potion to bring her back up?',
       1821.9, 1831.3, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     173,
       'Yes, you have a healing potion in your pack. It is a minor potion that restores 2d4 plus 2 hit points. You pour it down her throat and she coughs, gasping. Roll the healing.',
       1831.4, 1843.6, 0.97, false),

      (_gid, 'sess-pip-001',    'Pip',    174,
       'I rolled a 3 and a 2 on the 2d4, plus 2, so 7 hit points. She gets up with 7 hit points remaining.',
       1843.7, 1852.2, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     175,
       'Zara coughs and pulls herself up, barely able to stand. She is alive but barely. The High Priestess sees this and grins wickedly. She begins chanting again, casting another spell. This one seems different — darker.',
       1852.3, 1863.9, 0.97, false),

      (_gid, 'sess-aldric-001', 'Aldric', 176,
       'I cannot let her finish another spell. I attack again. Attack roll... 17.',
       1863.10, 1870.6, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     177,
       'That misses. She has begun moving, drifting backward, and your blade whistles through empty air. She continues casting. Zara, can you Counterspell again?',
       1870.7, 1880.3, 0.96, false),

      (_gid, 'sess-zara-001',   'Zara',   178,
       'I am barely standing and drained, but yes. I will use my reaction to Counterspell. My roll... 14. Does that work?',
       1880.4, 1889.8, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     179,
       'Her spell is powerful — DC 17. Your 14 does not overcome it. Her Counterspell fails. The spell completes. Shadow tentacles burst from the ground around Aldric and Pip. Tentacle attacks — Aldric and Pip, make Dexterity checks to avoid being restrained.',
       1889.9, 1905.3, 0.98, false),

      (_gid, 'sess-aldric-001', 'Aldric', 180,
       'I rolled a 16 for escape.',
       1905.4, 1907.8, 0.93, false),

      (_gid, 'sess-pip-001',    'Pip',    181,
       'I got a 12. I am restrained.',
       1907.9, 1910.4, 0.91, false),

      (_gid, 'sess-dm-001',     'DM',     182,
       'Aldric slips free of the shadows. Pip is ensnared by shadow tentacles, restrained and unable to move. He struggles but the tentacles dig in. Each round he is restrained, he takes 5 cold damage from the shadow magic.',
       1910.5, 1923.8, 0.97, false),

      (_gid, 'sess-pip-001',    'Pip',    183,
       'I am trapped! Aldric, I need your help! I use my action to try to escape the restraint. Strength check... 14.',
       1923.9, 1932.1, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     184,
       'The tentacles are too strong. DC 16 to escape. You remain trapped. Two of the cultists are moving to flank you, weapons drawn.',
       1932.2, 1942.0, 0.96, false),

      (_gid, 'sess-aldric-001', 'Aldric', 185,
       'I am not going to let them attack Pip. I charge at the cultists. I attack the one closest to Pip. Attack roll... 20. Critical hit.',
       1942.1, 1950.9, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     186,
       'Critical! Double the dice.',
       1950.10, 1952.6, 0.90, false),

      (_gid, 'sess-aldric-001', 'Aldric', 187,
       'I rolled 4d6 for damage. I got a 5, 6, 3, and 4, plus my Strength modifier of 3. That is 21 damage on the cultist.',
       1952.7, 1962.1, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     188,
       'The cultist explodes backward, blood pouring from a massive gash. He collapses, dead. Eight cultists remain alive. The High Priestess laughs again. She points at you, Aldric.',
       1962.2, 1972.6, 0.97, false),

      (_gid, 'sess-dm-001',     'DM',     189,
       'She casts Hold Person on you. Make a Wisdom saving throw, DC 17.',
       1972.7, 1977.5, 0.94, false),

      (_gid, 'sess-aldric-001', 'Aldric', 190,
       'I rolled a 14. I fail.',
       1977.6, 1979.6, 0.91, false),

      (_gid, 'sess-dm-001',     'DM',     191,
       'Your muscles lock. You are paralyzed by magical force, unable to move or act. You stand frozen in place, helpless. Both of your party members are now effectively incapacitated — Pip trapped by tentacles, Aldric held by magic. Only Zara remains free, standing barely conscious.',
       1979.7, 1996.2, 0.98, false),

      (_gid, 'sess-zara-001',   'Zara',   192,
       'No. No no no. This is bad. I am down to 7 hit points and both my allies are incapacitated. I have to do something decisive. I move away from the High Priestess to create distance and I cast Cone of Cold, a powerful blast of freezing magic right at her.',
       1996.3, 2010.7, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     193,
       'Dexterity saving throw, DC 16 for the High Priestess.',
       2010.8, 2015.4, 0.93, false),

      (_gid, 'sess-zara-001',   'Zara',   194,
       'Come on... I need her to fail.',
       2015.5, 2018.3, 0.91, false),

      (_gid, 'sess-dm-001',     'DM',     195,
       'She rolls... 11. She fails. Cone of Cold engulfs her. The intense cold freezes the moisture in the air around her. Ice forms on her robes. She takes 32 cold damage.',
       2018.4, 2029.8, 0.97, false),

      (_gid, 'sess-zara-001',   'Zara',   196,
       'She is covered in ice but still standing? How much damage has she taken total?',
       2029.9, 2035.8, 0.94, false),

      (_gid, 'sess-dm-001',     'DM',     197,
       'The High Priestess has taken damage from Pip\''s rapier strike (11), Aldric\''s two greatsword attacks (28), Chain Lightning (approximately 30), and now Cone of Cold (32). That is over 100 damage. She is visibly wounded, blood dripping from her robes, ice covering half her body. But she remains standing, still radiating power. She speaks, her voice echoing with otherworldly resonance.',
       2035.9, 2056.3, 0.99, false),

      (_gid, 'sess-dm-001',     'DM',     198,
       'High Priestess: You cannot stop this. The convergence is inevitable. My ritual is already half-complete. Even if you kill me, the gateway will open. The Veil-Walker has already begun to manifest.',
       2056.4, 2068.7, 0.97, false),

      (_gid, 'sess-zara-001',   'Zara',   199,
       'She is monologuing. Good. I need time. Hold. I want to cast Dispel Magic on the shadow tentacles holding Pip. I use a 3rd level spell slot.',
       2068.8, 2079.3, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     200,
       'Spell level check against DC 17 for the shadow tentacles. Using a 3rd level slot.',
       2079.4, 2086.0, 0.95, false),

      (_gid, 'sess-zara-001',   'Zara',   201,
       'I rolled a 19. That beats 17.',
       2086.1, 2089.1, 0.92, false),

      (_gid, 'sess-dm-001',     'DM',     202,
       'The shadow tentacles dissipate in a cloud of black mist. Pip is freed, gasping and shaking from the cold damage he took.',
       2089.2, 2098.8, 0.96, false),

      (_gid, 'sess-pip-001',    'Pip',    203,
       'I am free. Thank you, Zara. I immediately attack the High Priestess. She is wounded and I need to do everything I can. Attack roll... 18.',
       2098.9, 2107.9, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     203,
       'That hits. Roll damage.',
       2108.0, 2109.8, 0.90, false),

      (_gid, 'sess-pip-001',    'Pip',    204,
       'I rolled an 8 on the damage die, plus 4 for Dexterity, so 12 damage.',
       2109.9, 2115.8, 0.94, false),

      (_gid, 'sess-dm-001',     'DM',     205,
       'Pip rushes forward and drives his rapier deep into her arm. She howls but does not fall. The remaining seven cultists are moving now, forming a protective circle around her. They begin chanting in unison, a terrible sound that makes the earth shake.',
       2115.9, 2130.6, 0.98, false),

      (_gid, 'sess-aldric-001', 'Aldric', 206,
       'I am still paralyzed but I can speak. I shout as loud as I can: The ritual is failing! The gateway will collapse on all of you! Surrender and live, or die trapped between worlds!',
       2130.7, 2143.0, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     207,
       'Make an Intimidation check.',
       2143.1, 2145.9, 0.92, false),

      (_gid, 'sess-aldric-001', 'Aldric', 208,
       'I rolled a 22.',
       2145.10, 2147.5, 0.90, false),

      (_gid, 'sess-dm-001',     'DM',     209,
       'Two of the cultists hesitate. They look at each other, fear dancing in their eyes. One breaks rank and begins backing away. The High Priestess snarls at him but the damage is done — discipline is cracking. However, five cultists remain committed.',
       2147.6, 2161.3, 0.98, false),

      (_gid, 'sess-zara-001',   'Zara',   210,
       'I need Aldric free. I cast Dispel Magic on the Hold Person spell constraining him, using another 3rd level slot.',
       2161.4, 2170.7, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     211,
       'Spell level check against DC 14 for Hold Person.',
       2170.8, 2175.0, 0.93, false),

      (_gid, 'sess-zara-001',   'Zara',   212,
       'I rolled a 17. That beats 14.',
       2175.1, 2177.8, 0.91, false),

      (_gid, 'sess-dm-001',     'DM',     213,
       'The magical paralysis shatters. Aldric is freed, able to move again. He is angry and ready to fight.',
       2177.9, 2185.9, 0.96, false),

      (_gid, 'sess-aldric-001', 'Aldric', 214,
       'On my feet again. I charge straight at the High Priestess, full movement plus Attack. Attack roll... 21.',
       2186.0, 2194.1, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     215,
       'That hits. Roll damage.',
       2194.2, 2196.0, 0.91, false),

      (_gid, 'sess-aldric-001', 'Aldric', 216,
       'I rolled a 10 and an 8 on the 2d6, plus 3 for Strength, so 21 damage.',
       2196.1, 2203.4, 0.94, false),

      (_gid, 'sess-dm-001',     'DM',     217,
       'Your greatsword carves deep across the High Priestess chest. Blood sprays. She staggers and drops to one knee. She has taken catastrophic damage. She is still alive but barely holding on, perhaps 10 to 15 hit points remaining at most.',
       2203.5, 2220.3, 0.98, false),

      (_gid, 'sess-dm-001',     'DM',     218,
       'The five remaining cultists scream a single word in unison — a word in a language you do not know but understand instinctively means Gateway. The silver sigil at the center of the clearing begins to glow with sickly green light. The ritual is reaching its final stages.',
       2220.4, 2237.5, 0.99, false),

      (_gid, 'sess-zara-001',   'Zara',   219,
       'The ritual! They are completing the gateway ritual right now. I have to stop it. Can I destroy the sigil? Can I cast something to disrupt it?',
       2237.6, 2249.1, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     220,
       'The sigil is magical. You could attempt a Dispel Magic check, but it will be very difficult — DC 19. Or you could attack it physically, but it is protected by magical wards. Each attack against it requires a Wisdom saving throw or you take 10 force damage as backlash.',
       2249.2, 2264.7, 0.98, false),

      (_gid, 'sess-pip-001',    'Pip',    221,
       'I attack the sigil with my rapier. I will take the risk. Attack roll against the wards... 17. That should hit.',
       2264.8, 2273.8, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     222,
       'Your rapier strikes the sigil and it flares bright green. Make a Wisdom saving throw, DC 15.',
       2273.9, 2282.5, 0.96, false),

      (_gid, 'sess-pip-001',    'Pip',    223,
       'I rolled a 13. I fail.',
       2282.6, 2284.6, 0.91, false),

      (_gid, 'sess-dm-001',     'DM',     224,
       'The backlash hits you hard. 10 force damage. Pip, you valiantly tried to damage the sigil but your rapier did not penetrate its protective magic. The sigil continues to glow brighter.',
       2284.7, 2296.3, 0.97, false),

      (_gid, 'sess-zara-001',   'Zara',   225,
       'I am going to try Dispel Magic on the sigil. I use my 4th level spell slot for a higher chance. That is my only remaining high-level slot. My spell level check... I rolled a 20.',
       2296.4, 2308.2, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     226,
       'Your Dispel Magic with the 4th level slot meets DC 19. You succeed by one. The magical energy in the sigil destabilizes, flickering. The ritual pauses, disrupted.',
       2308.3, 2320.6, 0.98, false),

      (_gid, 'sess-dm-001',     'DM',     227,
       'The High Priestess screams in rage and despair. She stands, bloodied and beaten, but still defiant. She raises her hands and her eyes glow with that void-black light. She speaks a single word and the ground beneath her begins to glow. She is casting one final spell — a last desperate attempt to complete the gateway.',
       2320.7, 2340.4, 0.99, false),

      (_gid, 'sess-aldric-001', 'Aldric', 228,
       'Not on my watch. I charge directly at her. I want to physical interrupt her casting, driving my shoulder into her to break her concentration.',
       2340.5, 2350.1, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     229,
       'That is a contested Strength check. She is weakened and you are strong. Roll.',
       2350.2, 2356.4, 0.96, false),

      (_gid, 'sess-aldric-001', 'Aldric', 230,
       'I rolled a 21.',
       2356.5, 2358.3, 0.91, false),

      (_gid, 'sess-dm-001',     'DM',     231,
       'She rolled a 9. Your shoulder collides with her and she is driven backward hard, slamming into one of the standing stones. The impact breaks her concentration. Her spell fizzles and dies. Her final attempt has failed.',
       2358.4, 2372.9, 0.98, false),

      (_gid, 'sess-dm-001',     'DM',     232,
       'She collapses to the ground. She is dead or dying. The five remaining cultists look at each other, at their fallen priestess, and at you three standing defiantly. One drops his weapon and runs into the forest, screaming. Two others follow. Two remain.',
       2373.0, 2387.8, 0.99, false),

      (_gid, 'sess-pip-001',    'Pip',    233,
       'We let them run. We have won. The ritual has been stopped. Let those cultists flee — the important thing is the gateway has been disrupted.',
       2387.9, 2397.6, 0.95, false),

      (_gid, 'sess-aldric-001', 'Aldric', 234,
       'Pip is right. It is over. The High Priestess is defeated. The ritual site is ours.',
       2397.7, 2404.5, 0.94, false),

      (_gid, 'sess-dm-001',     'DM',     235,
       'The two remaining cultists see their cause is lost. They throw down their weapons and raise their hands in surrender. You have won the battle. The Blackwood Forest clearing is strewn with the bodies of fallen cultists. The High Priestess lies unmoving at the foot of the standing stones. The silver sigil, though disrupted, still glows faintly with residual power.',
       2404.6, 2426.0, 0.99, false),

      (_gid, 'sess-zara-001',   'Zara',   236,
       'We need to recover and assess the situation. Aldric, Pip — are you both okay? I am nearly drained. I have expended almost all my spell slots.',
       2426.1, 2436.1, 0.95, false),

      (_gid, 'sess-aldric-001', 'Aldric', 237,
       'I am battered but functional. Pip?',
       2436.2, 2438.7, 0.92, false),

      (_gid, 'sess-pip-001',    'Pip',    238,
       'I have some injuries and the cold damage from being restrained is excruciating, but I will live. We won. That is what matters.',
       2438.8, 2449.2, 0.94, false),

      (_gid, 'sess-dm-001',     'DM',     239,
       'You begin to search the High Priestess body. She contains several important items: a grimoire bound in black leather filled with ritual incantations, a vial of pure silver ink, a pendant made of silver and dark obsidian inscribed with the void-marking, and a sealed letter.',
       2449.3, 2469.1, 0.98, false),

      (_gid, 'sess-pip-001',    'Pip',    240,
       'The letter. I want to open and read it. What does it say?',
       2469.2, 2474.1, 0.94, false),

      (_gid, 'sess-dm-001',     'DM',     241,
       'The letter is addressed to To the Priestess of Grayholm. It is from someone called The Harbinger. It reads: The eclipse convergence approaches. When the moon is dark, three ritual sites must sing in harmony. Two gates open us to power. The third gate opens Him. Do not fail. The harvest is upon us. Signed, The Harbinger.',
       2474.2, 2502.5, 0.99, false),

      (_gid, 'sess-zara-001',   'Zara',   242,
       'The Harbinger. There is someone else — someone higher in the hierarchy than this High Priestess. And we stopped two of three rituals, but there is still Grayholm. We cannot rest yet.',
       2502.6, 2516.9, 0.96, false),

      (_gid, 'sess-aldric-001', 'Aldric', 243,
       'One crisis at a time. We need to bind the two surrendered cultists, recover our strength, and decide on our next move. We have disrupted the convergence but not stopped it entirely. The Harbinger and the Grayholm priestess still threaten the world.',
       2517.0, 2532.9, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     244,
       'You bind the two cultists securely and question them. They are terrified and willing to talk. They reveal that the Priestess of Grayholm is called Morrigan and she is far more mysterious and powerful than their High Priestess. The Harbinger remains unknown. They hear only whispers of his existence. They know very little more.',
       2533.0, 2556.3, 0.99, false),

      (_gid, 'sess-zara-001',   'Zara',   247,
       'The eclipse is in two nights. The letter mentioned it is the convergence time. We have stopped this ritual site, but if the Grayholm priestess completes her ritual, the gateway still opens. We have to get to Grayholm and stop it.',
       2556.4, 2571.0, 0.96, false),

      (_gid, 'sess-pip-001',    'Pip',    248,
       'But we are exhausted. Zara has no spell slots left. Aldric is bleeding. I am shaking from cold. We cannot ride for Grayholm in this condition. We need at least a night to rest and recover.',
       2571.1, 2582.5, 0.95, false),

      (_gid, 'sess-aldric-001', 'Aldric', 249,
       'Agreed. We will rest here at the ritual site tonight. We will set watches and guard the prisoners. Tomorrow we ride hard for Grayholm. We have one day to reach it before the eclipse. It will be cutting it close, but we will make it.',
       2582.6, 2597.1, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     250,
       'As night falls over Blackwood Forest, you establish camp at the ritual site. Paradoxically, the place of dark magic is now your sanctuary. The three of you tend to your wounds, recover from the battle, and prepare your weapons and spells. Around you, the forest is eerily quiet. Stars appear overhead and you notice something strange — the moon is noticeably dimmer than it should be. The eclipse is beginning. You have less time than you thought. Two nights until total darkness and the moment of convergence.',
       2597.2, 2625.8, 0.99, false),

      (_gid, 'sess-zara-001',   'Zara',   251,
       'The eclipse is already starting. We might have even less than two nights. Tomorrow we ride to Grayholm. It is our last hope to stop the Veil-Walker convergence. If we fail, the gateway will open and something ancient and terrible will enter our world.',
       2625.9, 2643.9, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     252,
       'You claim Zara takes first watch of the night. Aldric and Pip settle in to rest, their wounds and exhaustion taking their toll. As midnight approaches, a strange wind stirs through the forest — not from any natural source. The dying trees around the clearing seem to tremble. Something vast and distant calls out in the void. The sound makes your skin crawl. It is the voice of something immense, reaching across the barrier between worlds. It feels almost like hunger. The Veil-Walker is stirring. This is no longer merely about stopping cultists. This is about preventing an apocalypse.',
       2643.10, 2681.0, 0.99, false);

END;
$$;
