import axios from 'axios';
import type {
  AuditFlag,
  AuditFlagMutation,
  AuditRun,
  AuditRunTrigger,
  CombatUpdate,
  Decision,
  Entity,
  Event,
  FlagStatus,
  Game,
  ImportantQuote,
  Loot,
  Note,
  PlayerCharacter,
  Quest,
  QuestDescriptionHistory,
  RestoreMutation,
  SearchResults,
  Thread,
  Transcript,
} from './types';

const api = axios.create({ baseURL: '/api' });

// ── Games ──────────────────────────────────────────────────────────────────
export const getGames = () => api.get<Game[]>('/games').then(r => r.data);
export const getGame = (id: number) => api.get<Game>(`/games/${id}`).then(r => r.data);
export const createGame = (data: Omit<Game, 'id' | 'created_at'>) =>
  api.post<Game>('/games', data).then(r => r.data);
export const updateGame = (id: number, data: Partial<Pick<Game, 'name' | 'hostname' | 'world_id'>>) =>
  api.patch<Game>(`/games/${id}`, data).then(r => r.data);
export const deleteGame = (id: number) => api.delete(`/games/${id}`);

// ── Notes ──────────────────────────────────────────────────────────────────
export const getNotes = (gameId: number) =>
  api.get<Note[]>(`/games/${gameId}/notes`).then(r => r.data);
export const deleteNote = (id: number) => api.delete(`/notes/${id}`);

// ── Audit ──────────────────────────────────────────────────────────────────
export const getAuditRuns = (gameId: number) =>
  api.get<AuditRun[]>(`/games/${gameId}/audit-runs`).then(r => r.data);
export const triggerAudit = (gameId: number, force = false) =>
  api.post<AuditRunTrigger>(`/games/${gameId}/audit-runs/trigger`, undefined, {
    params: { force },
  }).then(r => r.data);
export const getAuditFlags = (gameId: number, status?: FlagStatus, offset?: number, limit?: number) =>
  api.get<AuditFlag[]>(`/games/${gameId}/audit-flags`, {
    params: {
      ...(status ? { status } : {}),
      ...(offset !== undefined ? { offset } : {}),
      ...(limit !== undefined ? { limit } : {}),
    },
  }).then(r => r.data);
export const applyAuditFlag = (gameId: number, flagId: number) =>
  api.post<AuditFlagMutation>(`/games/${gameId}/audit-flags/${flagId}/apply`).then(r => r.data);
export const dismissAuditFlag = (gameId: number, flagId: number) =>
  api.post<AuditFlagMutation>(`/games/${gameId}/audit-flags/${flagId}/dismiss`).then(r => r.data);
export const reopenAuditFlag = (gameId: number, flagId: number) =>
  api.post<AuditFlagMutation>(`/games/${gameId}/audit-flags/${flagId}/reopen`).then(r => r.data);

// ── Entities ───────────────────────────────────────────────────────────────
export const getEntities = (gameId: number, entityType?: string) =>
  api.get<Entity[]>(`/games/${gameId}/entities`, { params: entityType ? { entity_type: entityType } : undefined })
    .then(r => r.data);
export const getEntity = (entityId: number) =>
  api.get<Entity>(`/entities/${entityId}`).then(r => r.data);
export const createEntity = (gameId: number, data: Pick<Entity, 'name' | 'description' | 'entity_type'>) =>
  api.post<Entity>(`/games/${gameId}/entities`, data).then(r => r.data);
export const updateEntity = (id: number, data: Partial<Pick<Entity, 'name' | 'description' | 'entity_type'>>) =>
  api.put<Entity>(`/entities/${id}`, data).then(r => r.data);
export const deleteEntity = (id: number) => api.delete(`/entities/${id}`);

// ── Threads ────────────────────────────────────────────────────────────────
export const getThreads = (gameId: number, resolved?: boolean) =>
  api.get<Thread[]>(`/games/${gameId}/threads`, { params: resolved !== undefined ? { resolved } : undefined })
    .then(r => r.data);
export const createThread = (gameId: number, text: string) =>
  api.post<Thread>(`/games/${gameId}/threads`, { text }).then(r => r.data);
export const updateThread = (id: number, data: Partial<Pick<Thread, 'text' | 'is_resolved' | 'resolution' | 'resolved_by_note_id' | 'quest_id'>>) =>
  api.put<Thread>(`/threads/${id}`, data).then(r => r.data);
export const deleteThread = (id: number) => api.delete(`/threads/${id}`);
export const restoreThread = (gameId: number, threadId: number) =>
  api.post<RestoreMutation>(`/games/${gameId}/threads/${threadId}/restore`).then(r => r.data);

// ── Transcripts ────────────────────────────────────────────────────────────
export const getTranscripts = (gameId: number, params?: { character_name?: string; limit?: number; offset?: number }) =>
  api.get<Transcript[]>(`/games/${gameId}/transcripts`, { params }).then(r => r.data);
export const deleteTranscript = (id: number) => api.delete(`/transcripts/${id}`);

// ── Loot ───────────────────────────────────────────────────────────────────
export const getLoot = (gameId: number) =>
  api.get<Loot[]>(`/games/${gameId}/loot`).then(r => r.data);
export const createLoot = (gameId: number, data: Pick<Loot, 'item_name' | 'acquired_by'>) =>
  api.post<Loot>(`/games/${gameId}/loot`, data).then(r => r.data);
export const updateLoot = (id: number, data: Partial<Pick<Loot, 'item_name' | 'acquired_by' | 'quest_id'>>) =>
  api.patch<Loot>(`/loot/${id}`, data).then(r => r.data);
export const deleteLoot = (id: number) => api.delete(`/loot/${id}`);

// ── Quests ─────────────────────────────────────────────────────────────────
export const getQuests = (gameId: number, status?: 'active' | 'completed') =>
  api.get<Quest[]>(`/games/${gameId}/quests`, { params: status ? { status } : undefined }).then(r => r.data);
export const createQuest = (gameId: number, data: Pick<Quest, 'name' | 'description'> & { quest_giver_entity_id?: number | null }) =>
  api.post<Quest>(`/games/${gameId}/quests`, data).then(r => r.data);
export const updateQuest = (id: number, data: Partial<Pick<Quest, 'name' | 'description' | 'status' | 'quest_giver_entity_id'>>) =>
  api.patch<Quest>(`/quests/${id}`, data).then(r => r.data);
export const deleteQuest = (id: number) => api.delete(`/quests/${id}`);
export const restoreQuest = (gameId: number, questId: number) =>
  api.post<RestoreMutation>(`/games/${gameId}/quests/${questId}/restore`).then(r => r.data);
export const getQuestHistory = (questId: number) =>
  api.get<QuestDescriptionHistory[]>(`/quests/${questId}/history`).then(r => r.data);

// ── Decisions ──────────────────────────────────────────────────────────────
export const getDecisions = (gameId: number) =>
  api.get<Decision[]>(`/games/${gameId}/decisions`).then(r => r.data);
export const createDecision = (gameId: number, data: Pick<Decision, 'note_id' | 'decision' | 'made_by'>) =>
  api.post<Decision>(`/games/${gameId}/decisions`, data).then(r => r.data);
export const deleteDecision = (id: number) => api.delete(`/decisions/${id}`);

// ── Events ─────────────────────────────────────────────────────────────────
export const getEvents = (gameId: number) =>
  api.get<Event[]>(`/games/${gameId}/events`).then(r => r.data);
export const createEvent = (gameId: number, text: string) =>
  api.post<Event>(`/games/${gameId}/events`, { text }).then(r => r.data);
export const deleteEvent = (id: number) => api.delete(`/events/${id}`);

// ── Combat ─────────────────────────────────────────────────────────────────
export const getCombat = (gameId: number) =>
  api.get<CombatUpdate[]>(`/games/${gameId}/combat`).then(r => r.data);
export const deleteCombat = (id: number) => api.delete(`/combat/${id}`);

// ── Quotes ─────────────────────────────────────────────────────────────────
export const getQuotes = (gameId: number) =>
  api.get<ImportantQuote[]>(`/games/${gameId}/quotes`).then(r => r.data);
export const deleteQuote = (id: number) => api.delete(`/quotes/${id}`);

// ── Note-specific linked data ──────────────────────────────────────────────
export const getNoteEvents = (gameId: number, noteId: number) =>
  api.get<Event[]>(`/games/${gameId}/notes/${noteId}/events`).then(r => r.data);
export const getNoteLoot = (gameId: number, noteId: number) =>
  api.get<Loot[]>(`/games/${gameId}/notes/${noteId}/loot`).then(r => r.data);
export const getNoteThreads = (gameId: number, noteId: number) =>
  api.get<Thread[]>(`/games/${gameId}/threads`).then(r => 
    r.data.filter(t => t.resolved_by_note_id === noteId)
  );
export const getNoteQuests = (gameId: number, noteId: number) =>
  api.get<Quest[]>(`/games/${gameId}/quests`).then(r => 
    r.data.filter(q => q.note_ids.includes(noteId))
  );

// ── Player characters ──────────────────────────────────────────────────────
export const getPlayerCharacters = (gameId: number) =>
  api.get<PlayerCharacter[]>(`/games/${gameId}/player_characters`).then(r => r.data);

// ── Search ─────────────────────────────────────────────────────────────────
export const searchGame = (gameId: number, query: string, contentType?: string, limit?: number) =>
  api.get<SearchResults>(`/games/${gameId}/search`, {
    params: { q: query, ...(contentType ? { content_type: contentType } : {}), ...(limit !== undefined ? { limit } : {}) },
  }).then(r => r.data);
