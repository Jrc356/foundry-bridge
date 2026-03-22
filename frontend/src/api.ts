import axios from 'axios';
import type {
  CombatUpdate,
  Decision,
  Entity,
  Event,
  Game,
  ImportantQuote,
  Loot,
  Note,
  PlayerCharacter,
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

// ── Entities ───────────────────────────────────────────────────────────────
export const getEntities = (gameId: number, entityType?: string) =>
  api.get<Entity[]>(`/games/${gameId}/entities`, { params: entityType ? { entity_type: entityType } : undefined })
    .then(r => r.data);
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
export const updateThread = (id: number, data: Partial<Pick<Thread, 'text' | 'is_resolved' | 'resolution' | 'resolved_by_note_id'>>) =>
  api.put<Thread>(`/threads/${id}`, data).then(r => r.data);
export const deleteThread = (id: number) => api.delete(`/threads/${id}`);

// ── Transcripts ────────────────────────────────────────────────────────────
export const getTranscripts = (gameId: number, params?: { character_name?: string; limit?: number; offset?: number }) =>
  api.get<Transcript[]>(`/games/${gameId}/transcripts`, { params }).then(r => r.data);
export const deleteTranscript = (id: number) => api.delete(`/transcripts/${id}`);

// ── Loot ───────────────────────────────────────────────────────────────────
export const getLoot = (gameId: number) =>
  api.get<Loot[]>(`/games/${gameId}/loot`).then(r => r.data);
export const createLoot = (gameId: number, data: Pick<Loot, 'item_name' | 'acquired_by'>) =>
  api.post<Loot>(`/games/${gameId}/loot`, data).then(r => r.data);
export const deleteLoot = (id: number) => api.delete(`/loot/${id}`);

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

// ── Player characters ──────────────────────────────────────────────────────
export const getPlayerCharacters = (gameId: number) =>
  api.get<PlayerCharacter[]>(`/games/${gameId}/player_characters`).then(r => r.data);

// ── Search ─────────────────────────────────────────────────────────────────
export const searchGame = (gameId: number, query: string, contentType?: string, limit?: number) =>
  api.get<SearchResults>(`/games/${gameId}/search`, {
    params: { q: query, ...(contentType ? { content_type: contentType } : {}), ...(limit !== undefined ? { limit } : {}) },
  }).then(r => r.data);
