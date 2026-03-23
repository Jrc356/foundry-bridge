// All data types matching the FastAPI response schemas

export interface Game {
  id: number;
  hostname: string;
  world_id: string;
  name: string;
  created_at: string;
}

export interface Note {
  id: number;
  game_id: number;
  summary: string;
  source_transcript_ids: number[];
  created_at: string;
}

export interface Entity {
  id: number;
  game_id: number;
  entity_type: 'npc' | 'location' | 'item' | 'faction' | 'other';
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface Thread {
  id: number;
  game_id: number;
  text: string;
  is_resolved: boolean;
  resolved_at: string | null;
  resolution: string | null;
  resolved_by_note_id: number | null;
  quest_id: number | null;
  created_at: string;
}

export interface Transcript {
  id: number;
  game_id: number | null;
  participant_id: string;
  character_name: string;
  turn_index: number;
  text: string;
  audio_window_start: number;
  audio_window_end: number;
  end_of_turn_confidence: number;
  note_taker_processed: boolean;
  created_at: string;
}

export interface Loot {
  id: number;
  game_id: number;
  item_name: string;
  acquired_by: string;
  quest_id: number | null;
  created_at: string;
}

export interface Quest {
  id: number;
  game_id: number;
  name: string;
  description: string;
  status: 'active' | 'completed';
  quest_giver_entity_id: number | null;
  note_ids: number[];
  created_at: string;
  updated_at: string;
}

export interface QuestDescriptionHistory {
  id: number;
  quest_id: number;
  description: string;
  note_id: number | null;
  created_at: string;
}

export interface Decision {
  id: number;
  game_id: number;
  note_id: number;
  decision: string;
  made_by: string;
  created_at: string;
}

export interface Event {
  id: number;
  game_id: number;
  text: string;
  created_at: string;
}

export interface SearchResults {
  entities: Entity[];
  notes: Note[];
  threads: Thread[];
  events: Event[];
  decisions: Decision[];
  loot: Loot[];
  combat: CombatUpdate[];
  quests: Quest[];
}

export interface CombatUpdate {
  id: number;
  game_id: number;
  note_id: number;
  encounter: string;
  outcome: string;
  created_at: string;
}

export interface ImportantQuote {
  id: number;
  game_id: number;
  note_id: number;
  transcript_id: number | null;
  text: string;
  speaker: string | null;
  created_at: string;
}

export interface PlayerCharacter {
  id: number;
  game_id: number;
  character_name: string;
  created_at: string;
}
