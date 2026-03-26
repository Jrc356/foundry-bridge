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
  is_audit: boolean;
}

export type FlagType =
  | 'entity_duplicate'
  | 'missing_entity'
  | 'missing_event'
  | 'missing_decision'
  | 'missing_loot'
  | 'loot_correction'
  | 'decision_correction'
  | 'deletion_candidate'
  | 'other';

export type FlagStatus = 'pending' | 'applied' | 'dismissed';

export type ReasonCode =
  | 'conflict_running'
  | 'noop_no_new_notes'
  | 'schedule_failed'
  | 'precreate_failed'
  | 'early_pipeline_failure'
  | 'scheduled'
  | 'noop_below_threshold'
  | 'not_found'
  | 'invalid_transition'
  | 'already_applied'
  | 'already_dismissed'
  | 'already_pending'
  | 'dismissed'
  | 'reopened'
  | 'applied'
  | 'invalid_shape'
  | 'cross_game'
  | 'noop_same_entity'
  | 'already_deleted'
  | 'unsupported_table'
  | 'unsupported_flag_type'
  | 'already_active'
  | 'restored'
  | 'conflict_audit_note';

export interface AuditRun {
  id: number;
  game_id: number;
  triggered_at: string;
  heartbeat_at: string | null;
  completed_at: string | null;
  status: 'running' | 'completed' | 'failed';
  trigger_source: 'auto' | 'manual';
  notes_audited: number[];
  notes_audited_count: number;
  min_note_id: number | null;
  max_note_id: number | null;
  audit_note_id: number | null;
}

export interface AuditFlag {
  id: number;
  game_id: number;
  audit_run_id: number;
  flag_type: FlagType;
  target_type: string | null;
  target_id: number | null;
  description: string;
  suggested_change: Record<string, unknown>;
  status: FlagStatus;
  created_at: string;
  resolved_at: string | null;
}

export interface AuditFlagMutation {
  flag_id: number;
  ok: boolean;
  noop: boolean;
  status: FlagStatus | null;
  reason_code: ReasonCode;
  message: string;
  details: Record<string, unknown>;
}

export interface AuditRunTrigger {
  ok: boolean;
  noop: boolean;
  reason_code: ReasonCode;
  message: string;
  run: AuditRun | null;
}

export interface RestoreMutation {
  ok: boolean;
  noop: boolean;
  reason_code: ReasonCode;
  message: string;
  quest_id: number | null;
  thread_id: number | null;
}

export interface Entity {
  id: number;
  game_id: number;
  entity_type: 'npc' | 'location' | 'item' | 'faction' | 'other';
  name: string;
  description: string;
  note_ids: number[];
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
  opened_by_note_id: number | null;
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
  note_ids: number[];
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
  note_ids: number[];
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
