import axios from 'axios';
import type {
  CombatUpdate,



















































































































































































































































































































































}  )    </div>      )}        )          </div>            </div>              })}                )                  </div>                    )}                      </div>                        </p>                          {quest.note_ids.length} note{quest.note_ids.length !== 1 ? 's' : ''}                          Created {new Date(quest.created_at).toLocaleDateString()} ·{' '}                        <p className="text-xs text-gray-600">                        {/* Meta */}                        )}                          </div>                            </select>                              ))}                                </option>                                  {t.text.length > 80 ? t.text.slice(0, 80) + '…' : t.text}                                <option key={t.id} value={t.id}>                              {unlinkedOpenThreads().map(t => (                              <option value="" disabled>— select a thread to link —</option>                            >                              className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-1.5 text-xs text-gray-300 focus:outline-none focus:ring-1 focus:ring-amber-500 w-full"                              }}                                e.target.value = ''                                if (tid) linkThreadMut.mutate({ threadId: tid, questId: quest.id })                                const tid = Number(e.target.value)                              onChange={e => {                              defaultValue=""                            <select                            </p>                              Link a Thread                            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">                          <div>                        {unlinkedOpenThreads().length > 0 && (                        {/* Link an unlinked thread */}                        </div>                          )}                            </ul>                              ))}                                </li>                                  </button>                                    ×                                  >                                    title="Unlink from quest"                                    className="text-gray-600 hover:text-red-400 transition-colors shrink-0"                                    onClick={() => linkThreadMut.mutate({ threadId: t.id, questId: null })}                                  <button                                  </span>                                    {t.text}                                  <span className={`flex-1 ${t.is_resolved ? 'text-gray-500 line-through' : 'text-gray-300'}`}>                                <li key={t.id} className="flex items-start justify-between gap-2 text-xs bg-gray-900 rounded-lg px-3 py-2">                              {linkedThreads.map(t => (                            <ul className="grid gap-1.5">                          ) : (                            <p className="text-xs text-gray-600">No threads linked yet.</p>                          {linkedThreads.length === 0 ? (                          </p>                            Linked Threads ({linkedThreads.length})                          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">                        <div>                        {/* Linked threads */}                      <div className="border-t border-gray-700 px-4 py-3 grid gap-3">                    {isExpanded && (                    {/* Expanded: threads and thread linking */}                    </div>                      )}                        <p className="text-sm text-gray-300">{quest.description}</p>                      ) : (                        />                          className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-1 focus:ring-amber-500 resize-none"                          rows={3}                          onChange={e => setEditValues(v => ({ ...v, description: e.target.value }))}                          value={editValues.description ?? ''}                        <textarea                      {isEditing ? (                    <div className="px-4 pb-3">                    {/* Description (always visible; editable when editing) */}                    </div>                      </div>                        </button>                          {isExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}                        >                          title={isExpanded ? 'Collapse' : 'Expand'}                          className="p-1.5 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-gray-700 transition-colors"                          onClick={() => toggleExpand(quest.id)}                        <button                        </button>                          <Trash2 size={14} />                        >                          className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-gray-700 transition-colors"                          onClick={() => deleteMut.mutate(quest.id)}                        <button                        )}                          </button>                            Cancel                          >                            className="p-1.5 rounded-lg text-xs text-gray-400 hover:text-gray-200 hover:bg-gray-700 transition-colors"                            onClick={() => setEditing(null)}                          <button                        {isEditing && (                        </button>                          {isEditing ? 'Save' : 'Edit'}                        >                          className="p-1.5 rounded-lg text-xs text-gray-400 hover:text-amber-300 hover:bg-gray-700 transition-colors font-medium"                          onClick={() => (isEditing ? updateMut.mutate(quest.id) : startEdit(quest))}                        <button                        </button>                          <CheckCircle size={15} />                        >                          className="p-1.5 rounded-lg text-gray-400 hover:text-emerald-400 hover:bg-gray-700 transition-colors"                          title={quest.status === 'active' ? 'Mark completed' : 'Reopen'}                          onClick={() => toggleStatusMut.mutate({ id: quest.id, current: quest.status })}                        <button                      <div className="flex items-center gap-1 shrink-0">                      {/* Actions */}                      </div>                        )}                          </p>                            <User size={11} /> Given by entity #{quest.quest_giver_entity_id}                          <p className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">                        {quest.quest_giver_entity_id != null && (                        </div>                          )}                            <span className="font-semibold text-gray-100 text-sm">{quest.name}</span>                          ) : (                            />                              className="bg-gray-900 border border-gray-600 rounded px-2 py-0.5 text-sm text-gray-100 focus:outline-none focus:ring-1 focus:ring-amber-500 flex-1"                              onChange={e => setEditValues(v => ({ ...v, name: e.target.value }))}                              value={editValues.name ?? ''}                            <input                          {isEditing ? (                          </span>                            {quest.status}                          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${STATUS_BADGE[quest.status]}`}>                        <div className="flex items-center gap-2 flex-wrap mb-1">                      <div className="flex-1 min-w-0">                    <div className="flex items-start justify-between gap-4 p-4">                    {/* Card header */}                  <div key={quest.id} className="bg-gray-800 rounded-xl border border-gray-700">                return (                const isEditing = editing === quest.id                const linkedThreads = questThreads(quest.id)                const isExpanded = expanded.has(quest.id)              {items.map(quest => {            <div className="grid gap-3">            )}              </h3>                {label} ({items.length})              <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3">            {filter === 'all' && (          <div key={label} className="mb-6">        ) : (          <p key={label} className="text-gray-500 text-sm">No {label.toLowerCase()} quests.</p>        items.length === 0 && filter !== 'all' ? (      {displayGroups.map(({ label, items }) =>      {/* Quest groups */}      )}        </form>          </div>            </button>              Cancel            >              className="bg-gray-700 hover:bg-gray-600 text-gray-200 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"              onClick={() => setShowAdd(false)}              type="button"            <button            </button>              {createMut.isPending ? 'Adding…' : 'Add Quest'}            >              className="bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"              disabled={createMut.isPending}              type="submit"            <button          <div className="flex gap-2">          />            className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-amber-500 resize-none"            rows={2}            onChange={e => setNewQuest(v => ({ ...v, description: e.target.value }))}            value={newQuest.description}            placeholder="Description"            required          <textarea          />            className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-amber-500"            onChange={e => setNewQuest(v => ({ ...v, name: e.target.value }))}            value={newQuest.name}            placeholder="Quest name"            required          <input        >          className="bg-gray-800 rounded-xl p-4 mb-5 border border-gray-700 grid gap-3"          onSubmit={e => { e.preventDefault(); createMut.mutate() }}        <form      {showAdd && (      {/* Add form */}      </div>        ))}          </button>            {f}          >            }`}              filter === f ? 'bg-amber-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'            className={`px-3 py-1 rounded-full text-xs font-medium capitalize transition-colors ${            onClick={() => setFilter(f)}            key={f}          <button        {(['all', 'active', 'completed'] as const).map(f => (      <div className="flex gap-2 mb-5">      {/* Filter bar */}      />        }          </button>            <PlusCircle size={14} /> Add Quest          >            className="flex items-center gap-2 bg-amber-600 hover:bg-amber-700 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"            onClick={() => setShowAdd(v => !v)}          <button        action={        count={quests.length}        title="Quest Log"      <TabHeader    <div className="p-6 max-w-4xl">  return (      : [{ label: filter === 'active' ? 'Active' : 'Completed', items: quests }]        ]          { label: 'Completed', items: completedQuests },          { label: 'Active', items: activeQuests },      ? [    filter === 'all'  const displayGroups: Array<{ label: string; items: Quest[] }> =  const completedQuests = quests.filter(q => q.status === 'completed')  const activeQuests = quests.filter(q => q.status === 'active')  if (isLoading) return <div className="p-6 text-gray-400">Loading…</div>    (threads as Thread[]).filter(t => !t.is_resolved && t.quest_id == null)  const unlinkedOpenThreads = (): Thread[] =>    (threads as Thread[]).filter(t => t.quest_id === questId)  const questThreads = (questId: number): Thread[] =>  }    setEditValues({ name: q.name, description: q.description, quest_giver_entity_id: q.quest_giver_entity_id })    setEditing(q.id)  const startEdit = (q: Quest) => {    })      return next      next.has(id) ? next.delete(id) : next.add(id)      const next = new Set(prev)    setExpanded(prev => {  const toggleExpand = (id: number) =>  })    onSuccess: () => qc.invalidateQueries({ queryKey: ['threads', gameId] }),      updateThread(threadId, { quest_id: questId }),    mutationFn: ({ threadId, questId }: { threadId: number; questId: number | null }) =>  const linkThreadMut = useMutation({  })    onSuccess: () => qc.invalidateQueries({ queryKey: ['quests', gameId] }),    mutationFn: deleteQuest,  const deleteMut = useMutation({  })    onSuccess: () => qc.invalidateQueries({ queryKey: ['quests', gameId] }),      updateQuest(id, { status: current === 'active' ? 'completed' : 'active' }),    mutationFn: ({ id, current }: { id: number; current: Quest['status'] }) =>  const toggleStatusMut = useMutation({  })    },      setEditing(null)      qc.invalidateQueries({ queryKey: ['quests', gameId] })    onSuccess: () => {    mutationFn: (id: number) => updateQuest(id, editValues),  const updateMut = useMutation({  })    },      setNewQuest({ name: '', description: '' })      setShowAdd(false)      qc.invalidateQueries({ queryKey: ['quests', gameId] })    onSuccess: () => {    mutationFn: () => createQuest(gameId, newQuest),  const createMut = useMutation({  })    queryFn: () => getThreads(gameId),    queryKey: ['threads', gameId, undefined],  const { data: threads = [] } = useQuery({  })    queryFn: () => getQuests(gameId, status),    queryKey: ['quests', gameId, status],  const { data: quests = [], isLoading } = useQuery({  const status = filter === 'all' ? undefined : filter  const [expanded, setExpanded] = useState<Set<number>>(new Set())  const [editValues, setEditValues] = useState<Partial<Quest>>({})  const [editing, setEditing] = useState<number | null>(null)  const [newQuest, setNewQuest] = useState({ name: '', description: '' })  const [showAdd, setShowAdd] = useState(false)  const [filter, setFilter] = useState<'all' | 'active' | 'completed'>('active')  const qc = useQueryClient()export default function QuestLogTab({ gameId }: { gameId: number }) {}  completed: 'bg-emerald-900 text-emerald-200 border border-emerald-700',  active: 'bg-amber-900 text-amber-200 border border-amber-700',const STATUS_BADGE: Record<Quest['status'], string> = {import type { Quest, Thread } from '../../types'import { TabHeader } from '../../components/TabHeader'} from '../../api'  updateThread,  updateQuest,  getThreads,  getQuests,  deleteQuest,  createQuest,import {  Decision,
  Entity,
  Event,
  Game,
  ImportantQuote,
  Loot,
  Note,
  PlayerCharacter,
  Quest,
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
export const updateThread = (id: number, data: Partial<Pick<Thread, 'text' | 'is_resolved' | 'resolution' | 'resolved_by_note_id' | 'quest_id'>>) =>
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
