-- =============================================================================
-- Scenario 1d: Combat Encounter — "The Cultist Ambush"
-- =============================================================================
-- The party, now investigating the mysterious silver sigil, encounters cultists
-- performing a ritual in the forest. A tense investigation quickly escalates
-- into combat. This session includes extensive rolls, initiative, attacks,
-- spell casting, and tactical maneuvering across multiple rounds of combat.
--
-- This script assumes 01_first_session.sql has been run and the game exists.
-- It adds 120+ transcripts documenting a complete combat encounter.
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

    -- ─── Additional Transcripts (turns 27-149) ────────────────────────────────
    INSERT INTO transcripts
        (game_id, participant_id, character_name, turn_index, text,
         audio_window_start, audio_window_end, end_of_turn_confidence, note_taker_processed)
    VALUES
      (_gid, 'sess-dm-001',     'DM',     27,
       'As you move to leave the area, a low chanting echoes through the trees to the north. It sounds rhythmic, deliberate, and accompanied by what might be the flickering of firelight through the trees.',
       237.0, 247.3, 0.99, false),

      (_gid, 'sess-aldric-001', 'Aldric', 28,
       'That chanting. It is happening right now. We need to investigate quietly. I motion for Zara and Pip to crouch low and follow me toward the sound.',
       247.4, 256.8, 0.96, false),

      (_gid, 'sess-zara-001',   'Zara',   29,
       'Stealth check? I move carefully, staying behind Aldric and using the trees for cover.',
       256.9, 262.4, 0.94, false),

      (_gid, 'sess-dm-001',     'DM',     30,
       'All three of you make Stealth checks. Aldric rolls a 19, Zara rolls a 21, and Pip rolls a 16. As you advance through the underbrush, the chanting grows louder. You emerge into a small clearing where seven robed figures form a circle around three bound prisoners — clearly the Hartwell family.',
       262.5, 282.6, 0.98, false),

      (_gid, 'sess-pip-001',    'Pip',    31,
       'The Hartwells are alive. We need to get them out of here. Can I see what is happening in the circle? Are they about to do something terrible to those people?',
       282.7, 290.3, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     32,
       'At the center of the circle stands an altar. A robed figure raises a dagger high and begins chanting in a language you do not recognize. The silver sigil you found earlier is carved into the ground beneath the prisoners. The robed figures are holding hands and their eyes are black — completely black, no iris or pupil. The ritual appears to be reaching its climax.',
       290.4, 312.8, 0.99, false),

      (_gid, 'sess-aldric-001', 'Aldric', 33,
       'We do not have time to plan. Those people are about to die. I am charging in. Everyone who can cast a spell, prepare to attack. I draw my sword and move into the clearing.',
       312.9, 324.1, 0.97, false),

      (_gid, 'sess-dm-001',     'DM',     34,
       'Combat has begun. Everyone roll initiative.',
       324.2, 327.5, 0.96, false),

      (_gid, 'sess-aldric-001', 'Aldric', 35,
       'I rolled an 18.',
       327.6, 329.2, 0.93, false),

      (_gid, 'sess-zara-001',   'Zara',   36,
       'I got a 22. I am going early.',
       329.3, 331.8, 0.92, false),

      (_gid, 'sess-pip-001',    'Pip',    37,
       'I rolled a 14. Not great.',
       331.9, 333.4, 0.91, false),

      (_gid, 'sess-dm-001',     'DM',     38,
       'The cultists are rolling. The high priest — the one with the dagger — rolled a 20. The six supporting cultists roll: 19, 17, 16, 15, 13, and 11. So initiative order is: High Priest at 20, Zara at 22, wait, Zara is at 22, so Zara goes first. Then High Priest at 20, Aldric at 18, then the cultists.',
       333.5, 356.9, 0.99, false),

      (_gid, 'sess-zara-001',   'Zara',   39,
       'I am first. I cast Fireball. I am aiming at the cluster of cultists. I want to catch as many as possible without hitting the prisoners. My spell attack roll...',
       357.0, 367.2, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     40,
       'You do not need to hit them with a spell attack for Fireball — it is an area spell. You choose the center point and all creatures in a 20-foot radius must make a Dexterity saving throw. Go ahead and tell me where you place it.',
       367.3, 378.1, 0.97, false),

      (_gid, 'sess-zara-001',   'Zara',   41,
       'I place the center of the blast right in the middle of the six supporting cultists, away from the High Priest and the prisoners.',
       378.2, 386.4, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     42,
       'Excellent positioning. The six cultists in the blast radius catch fire. All six of them make Dexterity saving throws. Five of them fail. Only one cultist, a lean figure on the eastern side of the circle, succeeds on the save. That cultist takes half damage. Everyone else takes 28 fire damage. Five of them are immediately reduced to cinders and collapse. The one who made the save screams in pain, burned but alive.',
       386.5, 409.7, 0.99, false),

      (_gid, 'sess-aldric-001', 'Aldric', 43,
       'Wow. Zara just took out five of them in one spell. That evened the odds considerably.',
       409.8, 416.2, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     43,
       'Now it is the High Priest turn. He sees five of his compatriots turned to ash and he lets out a shriek of rage. He raises his dagger toward the sky and speaks a command word. Suddenly, the silver sigil beneath the prisoners begins to glow with eldritch light. The prisoners scream as shadows seem to pull at their forms.',
       416.3, 434.1, 0.98, false),

      (_gid, 'sess-pip-001',    'Pip',    44,
       'What is he doing? Is he trying to extract something from them? Can I use Counterspell to stop whatever spell that is?',
       434.2, 442.6, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     45,
       'You do not have Counterspell prepared, but Zara could attempt it if she has it. Pip, you are not up yet in initiative order. The High Priest casts a spell — it looks like some kind of soul extraction or life drain. Zara, you already took your turn, so you will act next round. Aldric is up now.',
       442.7, 456.8, 0.97, false),

      (_gid, 'sess-aldric-001', 'Aldric', 46,
       'Okay, I move forward 30 feet toward the High Priest. I want to close the distance and protect the prisoners. I will use my full movement to advance.',
       456.9, 464.7, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     47,
       'You sprint across the clearing. The burned cultist tries to grab you as you pass, but you easily evade. You come to stop 15 feet from the High Priest, sword at the ready. You have one attack action left this turn.',
       464.8, 476.3, 0.98, false),

      (_gid, 'sess-aldric-001', 'Aldric', 48,
       'I attack the High Priest. I am using my greatsword. My attack roll is 19.',
       476.4, 481.8, 0.94, false),

      (_gid, 'sess-dm-001',     'DM',     49,
       'That hits. Roll damage.',
       481.9, 483.4, 0.90, false),

      (_gid, 'sess-aldric-001', 'Aldric', 50,
       'I rolled a 14 on the d8... wait, it is a d10, right?',
       483.5, 487.3, 0.92, false),

      (_gid, 'sess-dm-001',     'DM',     51,
       'Greatsword is 2d6. So your damage roll?',
       487.4, 489.5, 0.89, false),

      (_gid, 'sess-aldric-001', 'Aldric', 52,
       'Right, I got a 5 and a 4 on the 2d6, plus my Strength modifier of 3, so that is 12 damage total to the High Priest.',
       489.6, 497.4, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     53,
       'Your greatsword slashes across the High Priest chest and he staggers back, blood soaking through his robes. He has taken 12 damage and is visibly wounded but still standing. The burned cultist now acts. He scrambles backward away from Aldric and raises his hands. Black smoke spirals from his palms and he casts a spell at the prisoners.',
       497.5, 516.3, 0.99, false),

      (_gid, 'sess-zara-001',   'Zara',   54,
       'Wait, I want to try to Counterspell that if I can. Do I have Counterspell?',
       516.4, 520.8, 0.93, false),

      (_gid, 'sess-dm-001',     'DM',     55,
       'Yes, you have Counterspell prepared. Make an ability check. Your spell save DC is 15, and I rolled a 16 for his casting. You can try to counter it.',
       520.9, 531.1, 0.97, false),

      (_gid, 'sess-zara-001',   'Zara',   56,
       'I cast Counterspell. I roll... 18. Does that counter it?',
       531.2, 536.4, 0.93, false),

      (_gid, 'sess-dm-001',     'DM',     57,
       'Yes, your Counterspell succeeds. An invisible force blocks the burned cultist spell before it can take effect. The shadows around the prisoners dissipate. The prisoners are still bound to the altar but the immediate danger is averted.',
       536.5, 549.2, 0.98, false),

      (_gid, 'sess-pip-001',    'Pip',    58,
       'It is my turn now, right? I want to move up and try to help free the prisoners. I move 30 feet toward the altar.',
       549.3, 556.8, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     59,
       'You advance toward the altar. The prisoners are still bound by mystical chains made of shadow and light. When you touch one of the chains, you feel searing cold. You will need to make a check to break or dispel the chains — they are magical. What do you do?',
       556.9, 569.8, 0.97, false),

      (_gid, 'sess-pip-001',    'Pip',    60,
       'I use Dispel Magic to try to dispel the binding chains.',
       569.9, 573.4, 0.92, false),

      (_gid, 'sess-dm-001',     'DM',     61,
       'Make a Dispel Magic check. You are trying to dispel a high-level magical binding. This is a spell level check against a DC of 17.',
       573.5, 581.3, 0.96, false),

      (_gid, 'sess-pip-001',    'Pip',    62,
       'I rolled a 19. That beats 17.',
       581.4, 584.2, 0.91, false),

      (_gid, 'sess-dm-001',     'DM',     63,
       'The chains shatter. The first prisoner — a middle-aged merchant — gasps and collapses to his knees, free. The other two prisoners remain bound. Round 2 now begins. Zara, you are up first again.',
       584.3, 595.6, 0.98, false),

      (_gid, 'sess-zara-001',   'Zara',   64,
       'I move 30 feet toward the High Priest and cast Ray of Enfeeblement on him. My spell attack roll is 17.',
       595.7, 603.2, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     65,
       'That hits. The High Priest is weakened. He becomes vulnerable and his attacks will be less effective. He looks visibly weaker, though his eyes remain completely black.',
       603.3, 614.6, 0.97, false),

      (_gid, 'sess-aldric-001', 'Aldric', 66,
       'I attack the High Priest again. My attack roll is 20. That is a critical hit.',
       614.7, 620.8, 0.94, false),

      (_gid, 'sess-dm-001',     'DM',     67,
       'Critical! Roll damage and double the dice.',
       620.9, 623.1, 0.91, false),

      (_gid, 'sess-aldric-001', 'Aldric', 68,
       'Okay, so I roll 4d6 instead of 2d6. I got a 4, 5, 3, and 6. Plus my Strength modifier of 3, so that is 21 damage.',
       623.2, 632.7, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     69,
       'Your greatsword comes down with tremendous force, cleaving deep into the High Priest shoulder. He screams and drops to one knee. Blood pours from the wound. He is severely wounded now. The burned cultist acts again.',
       632.8, 646.0, 0.98, false),

      (_gid, 'sess-dm-001',     'DM',     70,
       'The burned cultist attempts to cast another spell, but his hands are shaking from pain and burns. He tries to summon shadows from the ground to entangle Aldric. Zara, can you try to counter?',
       646.1, 658.6, 0.97, false),

      (_gid, 'sess-zara-001',   'Zara',   71,
       'I will Counterspell again. My roll is 19.',
       658.7, 662.4, 0.93, false),

      (_gid, 'sess-dm-001',     'DM',     72,
       'Counterspell succeeds again. The shadows fizzle and dissipate. The cultist is running out of options.',
       662.5, 668.9, 0.96, false),

      (_gid, 'sess-pip-001',    'Pip',    73,
       'I want to move to the next prisoner and use Dispel Magic on their chains as well.',
       669.0, 675.2, 0.94, false),

      (_gid, 'sess-dm-001',     'DM',     74,
       'Make another spell level check, DC is 17 again.',
       675.3, 678.5, 0.92, false),

      (_gid, 'sess-pip-001',    'Pip',    75,
       'I rolled a 16. That is one short.',
       678.6, 681.3, 0.90, false),

      (_gid, 'sess-dm-001',     'DM',     75,
       'The chains hold. The prisoner screams and struggles but the magical bonds do not budge. You need a stronger spell or a higher check.',
       681.4, 690.6, 0.96, false),

      (_gid, 'sess-aldric-001', 'Aldric', 76,
       'I move around and take another attack at the High Priest. I want to end this fight. My attack is... 18.',
       690.7, 697.6, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     77,
       'That hits. Roll damage.',
       697.7, 699.2, 0.89, false),

      (_gid, 'sess-aldric-001', 'Aldric', 78,
       'I rolled a 6 and a 5 on the 2d6, plus 3 for Strength, so 14 damage.',
       699.3, 705.2, 0.94, false),

      (_gid, 'sess-dm-001',     'DM',     79,
       'Your blade slams into the High Priest again. He collapses, blood pooling beneath him. He is barely clinging to life but still conscious, barely. The burned cultist makes a desperate dash toward the forest, away from the clearing. He is attempting to flee.',
       705.3, 719.6, 0.98, false),

      (_gid, 'sess-pip-001',    'Pip',    80,
       'Can I use my reaction to do anything? Can I take a shot with a ranged attack?',
       719.7, 725.2, 0.94, false),

      (_gid, 'sess-dm-001',     'DM',     81,
       'You have your reaction available. If you have a ranged weapon, you can take an opportunity attack as he flees.',
       725.3, 733.5, 0.96, false),

      (_gid, 'sess-pip-001',    'Pip',    82,
       'I have a shortbow. I take a shot at his back. My attack roll is 15.',
       733.6, 740.2, 0.93, false),

      (_gid, 'sess-dm-001',     'DM',     83,
       'The arrow flies but the cultist ducks. It whistles past him and he disappears into the tree line, badly wounded but alive.',
       740.3, 749.1, 0.96, false),

      (_gid, 'sess-zara-001',   'Zara',   84,
       'The High Priest — he is still alive but barely. I approach him cautiously. Before we kill him, I want to try to get information. Why are you doing this? What do you want with the Hartwell family?',
       749.2, 761.4, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     85,
       'The High Priest coughs blood and laughs a horrible, rasping laugh. His black eyes fixed on you. The Hartwells... are merely the beginning. The ritual would have opened the way... for Him. The one who dwells beyond the veil. The shadow sigil... is a gateway. We are seeds... and soon... the harvest begins.',
       761.5, 786.1, 0.99, false),

      (_gid, 'sess-aldric-001', 'Aldric', 86,
       'Him? Who is he talking about? Zara, does this mean there is a greater threat?',
       786.2, 793.1, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     87,
       'The High Priest eyes close. He exhales one final breath and goes still. He is dead. Around you is the clearing — five cultists reduced to ash, one fled into the darkness, and one dead before you. The Hartwell merchant is semi-conscious from the encounter, and two are still bound by the magical chains.',
       793.2, 811.1, 0.98, false),

      (_gid, 'sess-pip-001',    'Pip',    88,
       'I immediately move to help the merchant who is still conscious. Is he injured? Can I give him water or help him understand what is happening?',
       811.2, 820.4, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     89,
       'The merchant, who introduces himself as Thomas Hartwell, is in shock but unharmed by weapons. He is mentally traumatized. He tells you that he and his family were selling goods when the cultists ambushed them three days ago. He does not know their purpose until he heard the chanting. He asks you to please free his wife and daughter who are still bound.',
       820.5, 841.2, 0.99, false),

      (_gid, 'sess-zara-001',   'Zara',   90,
       'Pip, we need to free the other two. Your Dispel Magic did not work last time. Let me try with a higher-level slot. I will cast Dispel Magic using a 3rd level spell slot.',
       841.3, 852.1, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     91,
       'Make a spell level check again. Using a 3rd level slot gives you advantage, so roll twice.',
       852.2, 859.1, 0.97, false),

      (_gid, 'sess-zara-001',   'Zara',   92,
       'I rolled an 18 and a 19. I will use the 19.',
       859.2, 863.4, 0.93, false),

      (_gid, 'sess-dm-001',     'DM',     93,
       'With the higher level spell, you dispel the chains on both remaining prisoners. They collapse to the ground, weeping and gasping. Both are physically unharmed but emotionally devastated. Thomas embraces his wife and daughter, tears streaming down his face.',
       863.5, 878.9, 0.99, false),

      (_gid, 'sess-aldric-001', 'Aldric', 94,
       'We need to search this place. The cultists had a purpose — they left clues. I want to examine the altar, the silver sigil, and the High Priest body for anything that might tell us more about their organization.',
       879.0, 891.1, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     95,
       'You spend the next hour carefully searching the clearing. On the body of the High Priest, you find: a leather journal filled with cryptic notes and symbols, a ring bearing the same silver sigil, and a vial of black oil that smells of sulfur and copper. The altar itself appears to be a temporary structure carved from wood, but beneath it you find a leather satchel containing maps.',
       891.2, 911.5, 0.98, false),

      (_gid, 'sess-pip-001',    'Pip',    96,
       'The maps? What do they show? Are there other locations marked?',
       911.6, 917.8, 0.94, false),

      (_gid, 'sess-dm-001',     'DM',     97,
       'The maps show the region around Millhaven and several other towns. Three locations are marked with the silver sigil: the clearing where you are now, a location in the Blackwood Forest to the north, and a settlement called Grayholm to the east, three day ride away.',
       917.9, 934.2, 0.98, false),

      (_gid, 'sess-zara-001',   'Zara',   98,
       'Three locations. Three ritual sites. If the High Priest spoke truth, they are preparing for something... He mentioned a gateway and someone who dwells beyond the veil. This is a larger conspiracy than just kidnapping.',
       934.3, 948.5, 0.96, false),

      (_gid, 'sess-aldric-001', 'Aldric', 99,
       'We should return to Millhaven. We need to tell the town guard what happened, ensure the Hartwells are safe, and then decide our next move. These cultists have plans for three locations. If we do not stop them, there will be more kidnappings, more rituals.',
       948.6, 963.1, 0.97, false),

      (_gid, 'sess-dm-001',     'DM',     100,
       'You help the Hartwell family onto horses. The journey back to Millhaven takes about three hours. When you arrive, word spread quickly of your success — the family some thought lost is alive. The town celebrates but confusion remains about the cultists and their purpose. Moran is relieved and grateful, but his expression grows grave when you tell him about the sigil and the other ritual sites planned across the region.',
       963.2, 985.6, 0.99, false),

      (_gid, 'sess-pip-001',    'Pip',    101,
       'I show Moran the journal and the maps. Some of the notes in the journal are in a language I do not recognize, but much of it seems to be about preparing the world for some kind of arrival. It is very ominous.',
       985.7, 999.3, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     102,
       'Moran takes the journal carefully. He studies it for a long moment. He tells you that he recognizes the symbol — the double crescent with a star. He has seen it before, years ago, when a traveling scholar came through town warning of a cult attempting to summon something ancient and powerful. The scholar called it the Cult of the Veil-Walker. They believe an entity exists on the other side of reality, and they perform rituals to create gateways. If even one of these rituals succeeds, the Veil-Walker could break through into our world.',
       999.4, 1030.1, 0.99, false),

      (_gid, 'sess-zara-001',   'Zara',   103,
       'The Veil-Walker? An entity from beyond our reality? This is far worse than bandits or even necromancers. If this thing has the power to break through reality, we are talking about an existential threat. We need allies, we need to gather information, and we need to stop the remaining rituals.',
       1030.2, 1047.3, 0.97, false),

      (_gid, 'sess-aldric-001', 'Aldric', 104,
       'The Blackwood Forest is closer than Grayholm. I say we go north and stop the next ritual before it can begin. We know the location. We can move fast.',
       1047.4, 1057.2, 0.95, false),

      (_gid, 'sess-pip-001',    'Pip',    105,
       'We should rest tonight and leave at dawn. We are exhausted from the combat, and traveling at night into an unknown forest would be foolish. Plus, Moran might have more information if we ask him properly.',
       1057.3, 1070.1, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     106,
       'You spend the evening at the Rusty Flagon, recovering and questioning Moran further. He provides what knowledge he has of the Blackwood Forest — it is ancient, stands at least forty miles north of Millhaven, and is known for strange occurrences and missing travelers. Local woodcutters avoid it except on the edges. Moran believes the ritual site is likely deep in the forest, the exact location uncertain but based on the map presumably within the oldest, most corrupted part of the woods.',
       1070.2, 1098.8, 0.99, false),

      (_gid, 'sess-zara-001',   'Zara',   107,
       'I want to spend some time examining the journal more carefully. There might be clues about when the ritual was planned to happen, or about the cult structure.',
       1098.9, 1108.2, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     108,
       'As you examine the journal, you piece together a timeline. The next ritual was planned for three days from now. You have three days to reach the Blackwood Forest and stop it. If you leave at dawn tomorrow, you can reach the forest by the afternoon of day two. That gives you one day to locate and infiltrate the ritual site before the cultists begin their ceremony. It will be a tight timeline.',
       1108.3, 1128.7, 0.99, false),

      (_gid, 'sess-aldric-001', 'Aldric', 109,
       'Then we leave at first light. We will ride hard, rest only when necessary, and trust our preparation and skills to see us through the ritual site. I move to prepare our equipment for the long journey.',
       1128.8, 1140.5, 0.96, false),

      (_gid, 'sess-pip-001',    'Pip',    110,
       'Before we leave, I want to hide the mysterious iron key I took from Moran somewhere very secure and keep a copy of that map. If something happens to us, someone needs to know about the third ritual site at Grayholm.',
       1140.6, 1154.2, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     111,
       'You make arrangements with Moran to keep copies of the documents. You hide your iron key in a safe place at the inn. Moran agrees that if you do not return within ten days, he will send word to the regional lords about the cult and the ritual sites. You rest that night with purpose — tomorrow begins the real fight against the Veil-Walker cult. As sleep takes you, each of you wonders what horrors await in the Blackwood Forest.',
       1154.3, 1173.4, 0.99, false),

      (_gid, 'sess-aldric-001', 'Aldric', 112,
       'The next morning at dawn, we gather our supplies and horses. Before we ride out, I want to check with the Hartwells. Are they safe? Is there anything they can tell us about the cultists intentions?',
       1173.5, 1183.8, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     113,
       'Thomas Hartwell meets with you at the inn. He is grateful but haunted by the experience. He tells you that the High Priest spoke of three pillars — three rituals that must be completed to open the gateway. He heard fragments of conversation mentioning something called the Eclipse Convergence. In three nights, there will be a lunar eclipse. The High Priest mentioned it was significant, a time of weakened barriers between worlds.',
       1183.9, 1207.3, 0.99, false),

      (_gid, 'sess-zara-001',   'Zara',   114,
       'Three nights. That matches the timeline in the journal. We have three nights before the eclipse and they need all three rituals completed. We need to stop at least two of them to prevent the gateway from opening.',
       1207.4, 1219.6, 0.97, false),

      (_gid, 'sess-pip-001',    'Pip',    115,
       'We head north toward Blackwood Forest as planned. As we ride, I keep the maps close and study the route to the ritual site marked on them. I want to arrive with maximum daylight remaining so we can scout the location before nightfall.',
       1219.7, 1232.1, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     116,
       'You ride hard through the day. The landscape transitions from cultivated farmland to wild forest. By afternoon, the trees grow denser and taller. The sky darkens beneath the thick canopy. Strange sounds echo through the forest — not quite animal, not quite wind. The air feels wrong, charged with magical energy. You sense you are getting close to the ritual site.',
       1232.2, 1255.1, 0.99, false),

      (_gid, 'sess-aldric-001', 'Aldric', 117,
       'We move more cautiously now. I suggest we leave the horses hidden and proceed on foot. Combat in a forest on horseback is ineffective. We need mobility and stealth.',
       1255.2, 1264.8, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     118,
       'You secure the horses in a dense thicket and proceed on foot. After about an hour of careful movement through the forest, you notice the trees ahead are dying. Their bark is black and rotted. The earth beneath them is barren. You smell sulfur and decay. Ahead, the forest opens into a clearing where massive stones form a circle. At the center is another silver sigil carved gigantically into the earth.',
       1264.9, 1287.4, 0.99, false),

      (_gid, 'sess-zara-001',   'Zara',   119,
       'The megaliths, the dying trees, this place is a nexus of dark power. I cast Detect Magic to see what we are dealing with.',
       1287.5, 1296.2, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     120,
       'Zara, the magical aura here is almost overwhelming. Multiple overlapping auras — necromancy, conjuration, transmutation, and something else you have never encountered before. Evocation perhaps, but twisted. Ancient. The ritual site is radiating power in preparation for the ceremony. And you sense life — cultists in the shadows between the stones. At least a dozen. They are waiting.',
       1296.3, 1318.7, 0.99, false),

      (_gid, 'sess-pip-001',    'Pip',    121,
       'A dozen? We are outnumbered three to one. We need a strategy. Can we stealth in closer? Can we disrupt the ritual without engaging in full combat?',
       1318.8, 1328.4, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     122,
       'That is a good question. You have some options. You could attempt to infiltrate the ritual site, find the ritual components, and destroy them before the cultists fully mobilize. You could attempt a direct assault. You could try to disrupt the ritual magic itself if you have access to such spells. Or you could set up an ambush — let the cultists see you and draw them into a trap. What do you want to do?',
       1328.5, 1349.1, 0.98, false),

      (_gid, 'sess-aldric-001', 'Aldric', 123,
       'I prefer direct confrontation, but I am not suicidal. Let us get closer and assess. Maybe we can identify a leader, someone important, and focus on eliminating them quickly. Zara, can you use your magic to thin out their numbers before combat starts?',
       1349.2, 1361.6, 0.96, false),

      (_gid, 'sess-zara-001',   'Zara',   124,
       'If we can get close enough without being seen, I can prepare a spell — Fireball again, or maybe something with more control. Chain Lightning might work in a cluster of enemies.',
       1361.7, 1372.9, 0.95, false),

      (_gid, 'sess-pip-001',    'Pip',    126,
       'I suggest we move around the clearing edge, staying in shadow and behind trees. I will scout ahead and see if I can find a good vantage point.',
       1372.10, 1382.5, 0.94, false),

      (_gid, 'sess-dm-001',     'DM',     125,
       'You move cautiously around the perimeter of the clearing. Make Stealth checks.',
       1372.6, 1376.0, 0.93, false),

      (_gid, 'sess-aldric-001', 'Aldric', 127,
       'I rolled a 16.',
       1382.6, 1384.2, 0.91, false),

      (_gid, 'sess-zara-001',   'Zara',   128,
       'I got a 19.',
       1384.3, 1385.8, 0.90, false),

      (_gid, 'sess-pip-001',    'Pip',    129,
       'I rolled a 22. I am sneaking better than both of you.',
       1385.9, 1388.7, 0.92, false),

      (_gid, 'sess-dm-001',     'DM',     130,
       'Pip, you move like a shadow, completely undetected. Zara, you avoid direct sight lines, hidden behind trees. Aldric, one cultist glimpses movement from the corner of his eye but is uncertain. You reach a ridge overlooking the ritual site. Below, you see the cultists more clearly — a dozen robed figures, and at the center, a woman in crimson robes. She radiates power. This must be the High Priestess.',
       1388.8, 1409.1, 0.99, false),

      (_gid, 'sess-zara-001',   'Zara',   131,
       'The woman in crimson has powerful auras surrounding her. She is clearly the leader and likely more dangerous than the High Priest we fought before. We need to focus on her.',
       1409.2, 1420.4, 0.96, false),

      (_gid, 'sess-aldric-001', 'Aldric', 132,
       'When we attack, we attack her directly and decisively. The followers will be easier to manage once their leader falls. I am ready to charge when you give the signal.',
       1420.5, 1431.2, 0.95, false),

      (_gid, 'sess-pip-001',    'Pip',    133,
       'Wait. I want to check if there are any other exits from this clearing or escape routes the cultists might use. Let me scout the far side.',
       1431.3, 1440.8, 0.94, false),

      (_gid, 'sess-dm-001',     'DM',     134,
       'You move further around the clearing, staying hidden. You spot another path — an ancient overgrown road that leads into deeper forest. It is carved into the earth, suggesting it has been used for centuries. This could be where the cultists came from and where they might flee.',
       1440.9, 1456.3, 0.97, false),

      (_gid, 'sess-pip-001',    'Pip',    135,
       'There is an escape route to the north through that old road. We should position someone to guard it when combat starts. Otherwise, they will flee and we will not stop all the rituals.',
       1456.4, 1467.2, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     136,
       'You are thinking strategically. You have identified a critical point. If you want to capture or eliminate the cultists, you need to block their escape. This presents a problem — you are three people trying to divide your forces.',
       1467.3, 1479.8, 0.98, false),

      (_gid, 'sess-zara-001',   'Zara',   137,
       'We cannot split up equally. But we might be able to use magic to our advantage. I can cast Hold Person or similar spells to trap cultists. Aldric is our strongest combatant. Pip, can you use your stealth to get behind them and block that road?',
       1479.9, 1494.1, 0.96, false),

      (_gid, 'sess-pip-001',    'Pip',    138,
       'I can try, but alone I cannot stop a dozen cultists if they all flee toward me at once. I would rely on traps or obstacles. Even with my skills, odds are not in my favor.',
       1494.2, 1505.4, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     139,
       'Fair assessment. What you could do is place caltrops or spikes on the road to slow their escape. You could also stay hidden and pick off stragglers as they flee. But you would not be able to hold a full retreat by yourself.',
       1505.5, 1520.1, 0.97, false),

      (_gid, 'sess-aldric-001', 'Aldric', 140,
       'Then our priority is to incapacitate the High Priestess and create chaos among the cultists. If their leader falls, morale breaks. Zara unleashes magic, I charge the leader, and Pip flanks them to disrupt their formation. In the resulting chaos, we can pick apart the rest.',
       1520.2, 1537.6, 0.96, false),

      (_gid, 'sess-zara-001',   'Zara',   141,
       'Agreed. I position myself on this rise for maximum spell coverage. When you are in position, Aldric, I will open with Chain Lightning to strike multiple cultists. That should catch their attention and start the combat.',
       1537.7, 1550.8, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     142,
       'You spend the next ten minutes preparing. Aldric and Pip move into positions — Aldric to rush the High Priestess, Pip to flank from the side. Zara readies her spell. As the sun dips lower toward the horizon, the cultists begin a low chanting. Their ceremony is starting. This is your moment.',
       1550.9, 1570.8, 0.99, false),

      (_gid, 'sess-zara-001',   'Zara',   143,
       'I cast Chain Lightning, targeting the High Priestess first, then letting it arc to nearby cultists. Attack roll... 20 to hit the High Priestess.',
       1570.9, 1580.1, 0.95, false),

      (_gid, 'sess-dm-001',     'DM',     144,
       'Yes, you hit her. The lightning courses through her body and she screams. The electricity arcs to two cultists near her and they fall convulsing. Three cultists down before melee even begins. Combat starts. Roll initiative, everyone.',
       1580.2, 1591.5, 0.98, false),

      (_gid, 'sess-aldric-001', 'Aldric', 145,
       'I rolled a 17.',
       1591.6, 1593.1, 0.91, false),

      (_gid, 'sess-zara-001',   'Zara',   146,
       'I got a 20.',
       1593.2, 1594.6, 0.90, false),

      (_gid, 'sess-pip-001',    'Pip',    147,
       'I rolled an 18.',
       1594.7, 1596.1, 0.89, false),

      (_gid, 'sess-dm-001',     'DM',     148,
       'The High Priestess rolled an 19. Initiative order: Zara, then the High Priestess, then Pip, then Aldric. Then the remaining cultists act. This will be a challenging fight. You are facing nine cultists and a powerful High Priestess in a ritual location of immense magical power. Your success or failure here determines whether the eclipse convergence proceeds. The stakes have never been higher. What do you do, Zara, on your first turn?',
       1596.2, 1621.0, 0.99, false),

      (_gid, 'sess-zara-001',   'Zara',   149,
       'I take my turn. I move 30 feet closer to the High Priestess and cast Counterspell-ready. Focusing, waiting to see what she does, what magic she might attempt to cast.',
       1621.1, 1633.2, 0.96, false),

      (_gid, 'sess-dm-001',     'DM',     150,
       'As your second turn begins — we will return to Zara when her next turn comes up. You have prepared Counterspell. Now the High Priestess acts. She rises to her feet despite the lingering scorch marks from the Chain Lightning. Her eyes begin to glow with that same black void-like darkness you saw in the first High Priest. She raises her hands and begins a ritual incantation. Dark energy pools around her. She is casting something powerful, something that threatens the whole battlefield. Zara, this is your moment. Counterspell or let it happen?',
       1633.3, 1660.3, 0.99, false);

END;
$$;
