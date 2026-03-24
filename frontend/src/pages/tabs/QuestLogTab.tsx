import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle, ChevronDown, ChevronUp, History, PlusCircle, Trash2, User } from 'lucide-react'
import { useState } from 'react'
import {
  createQuest,
  deleteQuest,
  getEntities,
  getLoot,
  getNotes,
  getQuestHistory,
  getQuests,
  getThreads,
  updateQuest,
  updateThread,
} from '../../api'
import { TabHeader } from '../../components/TabHeader'
import type { Entity, Loot, Note, Quest, QuestDescriptionHistory, Thread } from '../../types'

const STATUS_BADGE: Record<Quest['status'], string> = {
  active: 'bg-amber-900 text-amber-200 border border-amber-700',
  completed: 'bg-emerald-900 text-emerald-200 border border-emerald-700',
}

function QuestHistorySection({ questId }: { questId: number }) {
  const { data: history = [], isLoading } = useQuery<QuestDescriptionHistory[]>({
    queryKey: ['quest-history', questId],
    queryFn: () => getQuestHistory(questId),
  })
  if (isLoading) return <p className="text-xs text-gray-500">Loading history…</p>
  if (history.length === 0)
    return <p className="text-xs text-gray-600">No previous descriptions recorded.</p>
  return (
    <ol className="grid gap-2">
      {history.map(h => (
        <li key={h.id} className="grid gap-1 bg-gray-900 rounded-lg px-3 py-2">
          <time className="text-xs text-gray-500">
            {new Date(h.created_at).toLocaleString()}
          </time>
          <p className="text-xs text-gray-400">{h.description}</p>
        </li>
      ))}
    </ol>
  )
}

export default function QuestLogTab({ gameId }: { gameId: number }) {
  const [filter, setFilter] = useState<'all' | 'active' | 'completed'>('all')
  const [showAdd, setShowAdd] = useState(false)
  const [newQuest, setNewQuest] = useState({ name: '', description: '' })
  const [editing, setEditing] = useState<number | null>(null)
  const [editValues, setEditValues] = useState<Partial<Quest>>({})
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const [linkedOpen, setLinkedOpen] = useState<Set<number>>(new Set())
  const [notesOpen, setNotesOpen] = useState<Set<number>>(new Set())
  const [threadsClosed, setThreadsClosed] = useState<Set<number>>(new Set())
  const [expandedNotes, setExpandedNotes] = useState<Set<number>>(new Set())
  const qc = useQueryClient()

  const status = filter === 'all' ? undefined : filter
  const { data: quests = [], isLoading } = useQuery({
    queryKey: ['quests', gameId, status],
    queryFn: () => getQuests(gameId, status),
  })
  const { data: threads = [] } = useQuery({
    queryKey: ['threads', gameId, undefined],
    queryFn: () => getThreads(gameId),
  })
  const { data: loot = [] } = useQuery({
    queryKey: ['loot', gameId],
    queryFn: () => getLoot(gameId),
  })
  const { data: entities = [] } = useQuery({
    queryKey: ['entities', gameId],
    queryFn: () => getEntities(gameId),
  })
  const { data: notes = [] } = useQuery({
    queryKey: ['notes', gameId],
    queryFn: () => getNotes(gameId),
  })
  const entityName = (id: number | null): string | null => {
    if (id == null) return null
    return (entities as Entity[]).find(e => e.id === id)?.name ?? `Entity #${id}`
  }

  const createMut = useMutation({
    mutationFn: () => createQuest(gameId, newQuest),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['quests', gameId] })
      setShowAdd(false)
      setNewQuest({ name: '', description: '' })
    },
  })

  const updateMut = useMutation({
    mutationFn: (id: number) => updateQuest(id, editValues),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['quests', gameId] })
      setEditing(null)
    },
  })

  const toggleStatusMut = useMutation({
    mutationFn: ({ id, current }: { id: number; current: Quest['status'] }) =>
      updateQuest(id, { status: current === 'active' ? 'completed' : 'active' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['quests', gameId] }),
  })

  const deleteMut = useMutation({
    mutationFn: deleteQuest,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['quests', gameId] }),
  })

  const linkThreadMut = useMutation({
    mutationFn: ({ threadId, questId }: { threadId: number; questId: number | null }) =>
      updateThread(threadId, { quest_id: questId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['threads', gameId] }),
  })

  const resolveThreadMut = useMutation({
    mutationFn: (threadId: number) =>
      updateThread(threadId, { is_resolved: true }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['threads', gameId] }),
  })

  const toggleExpand = (id: number) =>
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  const toggleLinked = (id: number) =>
    setLinkedOpen(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  const toggleNotesOpen = (id: number) =>
    setNotesOpen(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  const toggleThreadsClosed = (id: number) =>
    setThreadsClosed(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  const startEdit = (q: Quest) => {
    setEditing(q.id)
    setEditValues({ name: q.name, description: q.description, quest_giver_entity_id: q.quest_giver_entity_id })
  }

  const questThreads = (questId: number): Thread[] =>
    (threads as Thread[]).filter(t => t.quest_id === questId)

  const questNotesFor = (noteIds: number[]): Note[] =>
    (notes as Note[]).filter(n => noteIds.includes(n.id))

  const questLoot = (questId: number): Loot[] =>
    (loot as Loot[]).filter(l => l.quest_id === questId)

  const unlinkedOpenThreads = (): Thread[] =>
    (threads as Thread[]).filter(t => !t.is_resolved && t.quest_id == null)

  if (isLoading) return <div className="p-6 text-gray-400">Loading…</div>

  const activeQuests = quests.filter(q => q.status === 'active')
  const completedQuests = quests.filter(q => q.status === 'completed')
  const displayGroups: Array<{ label: string; items: Quest[] }> =
    filter === 'all'
      ? [
          { label: 'Active', items: activeQuests },
          { label: 'Completed', items: completedQuests },
        ]
      : [{ label: filter === 'active' ? 'Active' : 'Completed', items: quests }]

  return (
    <div className="p-6 max-w-4xl">
      <TabHeader
        title="Quest Log"
        count={quests.length}
        action={
          <button
            onClick={() => setShowAdd(v => !v)}
            className="flex items-center gap-2 bg-amber-600 hover:bg-amber-700 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
          >
            <PlusCircle size={14} /> Add Quest
          </button>
        }
      />

      {/* Filter bar */}
      <div className="flex gap-2 mb-5">
        {(['all', 'active', 'completed'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded-full text-xs font-medium capitalize transition-colors ${
              filter === f ? 'bg-amber-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Add form */}
      {showAdd && (
        <form
          onSubmit={e => { e.preventDefault(); createMut.mutate() }}
          className="bg-gray-800 rounded-xl p-4 mb-5 border border-gray-700 grid gap-3"
        >
          <input
            required
            placeholder="Quest name"
            value={newQuest.name}
            onChange={e => setNewQuest(v => ({ ...v, name: e.target.value }))}
            className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-amber-500"
          />
          <textarea
            required
            placeholder="Description"
            value={newQuest.description}
            onChange={e => setNewQuest(v => ({ ...v, description: e.target.value }))}
            rows={2}
            className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-amber-500 resize-none"
          />
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={createMut.isPending}
              className="bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
            >
              {createMut.isPending ? 'Adding…' : 'Add Quest'}
            </button>
            <button
              type="button"
              onClick={() => setShowAdd(false)}
              className="bg-gray-700 hover:bg-gray-600 text-gray-200 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Quest groups */}
      {displayGroups.map(({ label, items }) =>
        items.length === 0 && filter !== 'all' ? (
          <p key={label} className="text-gray-500 text-sm">No {label.toLowerCase()} quests.</p>
        ) : (
          <div key={label} className="mb-6">
            {filter === 'all' && (
              <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3">
                {label} ({items.length})
              </h3>
            )}
            <div className="grid gap-3">
              {items.map(quest => {
                const isExpanded = expanded.has(quest.id)
                const linkedThreads = questThreads(quest.id)
                const linkedLoot = questLoot(quest.id)
                const isEditing = editing === quest.id
                return (
                  <div key={quest.id} className="bg-gray-800 rounded-xl border border-gray-700">
                    {/* Card header */}
                    <div className="flex items-start justify-between gap-4 p-4">
                      <div className="flex-1 min-w-0">
                        {/* Quest name */}
                        <div className="mb-2">
                          {isEditing ? (
                            <input
                              value={editValues.name ?? ''}
                              onChange={e => setEditValues(v => ({ ...v, name: e.target.value }))}
                              className="bg-gray-900 border border-gray-600 rounded px-2 py-0.5 text-sm text-gray-100 focus:outline-none focus:ring-1 focus:ring-amber-500 w-full"
                            />
                          ) : (
                            <span className="font-semibold text-gray-100 text-sm block">{quest.name}</span>
                          )}
                        </div>
                        
                        {/* Badges */}
                        <div className="flex items-center gap-2 flex-wrap mb-2">
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${STATUS_BADGE[quest.status]}`}>
                            {quest.status}
                          </span>
                          {linkedThreads.filter(t => !t.is_resolved).length > 0 && (
                            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-red-900 text-red-200 border border-red-700">
                              {linkedThreads.filter(t => !t.is_resolved).length} open
                            </span>
                          )}
                          {quest.note_ids.length > 0 && (
                            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-900 text-indigo-300 border border-indigo-700">
                              {quest.note_ids.length} {quest.note_ids.length === 1 ? 'note' : 'notes'}
                            </span>
                          )}
                        </div>
                        
                        {/* Quest giver */}
                        {quest.quest_giver_entity_id != null && (
                          <p className="text-xs text-gray-500 flex items-center gap-1">
                            <User size={11} /> Given by {entityName(quest.quest_giver_entity_id)}
                          </p>
                        )}
                      </div>
                      {/* Actions */}
                      <div className="flex items-center gap-1 shrink-0">
                        <button
                          onClick={() => toggleStatusMut.mutate({ id: quest.id, current: quest.status })}
                          title={quest.status === 'active' ? 'Mark completed' : 'Reopen'}
                          className="p-1.5 rounded-lg text-gray-400 hover:text-emerald-400 hover:bg-gray-700 transition-colors"
                        >
                          <CheckCircle size={15} />
                        </button>
                        <button
                          onClick={() => (isEditing ? updateMut.mutate(quest.id) : startEdit(quest))}
                          className="p-1.5 rounded-lg text-xs text-gray-400 hover:text-amber-300 hover:bg-gray-700 transition-colors font-medium"
                        >
                          {isEditing ? 'Save' : 'Edit'}
                        </button>
                        {isEditing && (
                          <button
                            onClick={() => setEditing(null)}
                            className="p-1.5 rounded-lg text-xs text-gray-400 hover:text-gray-200 hover:bg-gray-700 transition-colors"
                          >
                            Cancel
                          </button>
                        )}
                        <button
                          onClick={() => deleteMut.mutate(quest.id)}
                          className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-gray-700 transition-colors"
                        >
                          <Trash2 size={14} />
                        </button>
                        <button
                          onClick={() => toggleExpand(quest.id)}
                          title={isExpanded ? 'Collapse' : 'Expand'}
                          className="p-1.5 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-gray-700 transition-colors"
                        >
                          {isExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                        </button>
                      </div>
                    </div>

                    {/* Description */}
                    <div className="px-4 pb-3">
                      {isEditing ? (
                        <div className="grid gap-3">
                          <textarea
                            value={editValues.description ?? ''}
                            onChange={e => setEditValues(v => ({ ...v, description: e.target.value }))}
                            rows={3}
                            className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-1 focus:ring-amber-500 resize-none"
                          />
                          <select
                            value={editValues.quest_giver_entity_id ?? ''}
                            onChange={e => setEditValues(v => ({ ...v, quest_giver_entity_id: e.target.value ? Number(e.target.value) : null }))}
                            className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-300 focus:outline-none focus:ring-1 focus:ring-amber-500"
                          >
                            <option value="" label="No quest giver" />
                            {(entities as Entity[]).map(e => (
                              <option key={e.id} value={e.id} label={e.name} />
                            ))}
                          </select>
                        </div>
                      ) : (
                        <p className="text-sm text-gray-300 line-clamp-3">{quest.description}</p>
                      )}
                    </div>

                    {/* Expanded: description history, threads, session notes, and loot */}
                    {isExpanded && (
                      <div className="border-t border-gray-700 px-4 py-3 grid gap-3">
                        {/* Description history - always visible */}
                        <div>
                          <p className="flex items-center gap-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                            <History size={11} />
                            Description History
                          </p>
                          <QuestHistorySection questId={quest.id} />
                        </div>
                        {/* Threads - collapsible, expanded by default */}
                        <div>
                          <button
                            onClick={() => toggleThreadsClosed(quest.id)}
                            className="flex items-center gap-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 hover:text-gray-300 transition-colors w-full text-left"
                          >
                            Threads ({linkedThreads.length})
                            {threadsClosed.has(quest.id) ? <ChevronDown size={11} /> : <ChevronUp size={11} />}
                          </button>
                          {!threadsClosed.has(quest.id) && (
                            <div className="grid gap-3">
                              {linkedThreads.length === 0 ? (
                                <p className="text-xs text-gray-600">No threads linked yet.</p>
                              ) : (
                                <ul className="grid gap-1.5">
                                  {linkedThreads.map(t => (
                                    <li key={t.id} className="flex items-start justify-between gap-2 text-xs bg-gray-900 rounded-lg px-3 py-2">
                                      <span className={`flex-1 ${t.is_resolved ? 'text-gray-500 line-through' : 'text-gray-300'}`}>
                                        {t.text}
                                      </span>
                                      <div className="flex gap-1 shrink-0">
                                        {!t.is_resolved && (
                                          <button
                                            onClick={() => resolveThreadMut.mutate(t.id)}
                                            className="text-gray-600 hover:text-green-400 transition-colors"
                                            title="Mark as resolved"
                                          >
                                            ✓
                                          </button>
                                        )}
                                        <button
                                          onClick={() => linkThreadMut.mutate({ threadId: t.id, questId: null })}
                                          className="text-gray-600 hover:text-red-400 transition-colors"
                                          title="Unlink from quest"
                                        >
                                          ×
                                        </button>
                                      </div>
                                    </li>
                                  ))}
                                </ul>
                              )}
                              {unlinkedOpenThreads().length > 0 && (
                                <div>
                                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                                    Link a Thread
                                  </p>
                                  <select
                                    defaultValue=""
                                    onChange={e => {
                                      const tid = Number(e.target.value)
                                      if (tid) linkThreadMut.mutate({ threadId: tid, questId: quest.id })
                                      e.currentTarget.value = ''
                                    }}
                                    className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-1.5 text-xs text-gray-300 focus:outline-none focus:ring-1 focus:ring-amber-500 w-full"
                                  >
                                    <option value="" disabled>— select a thread to link —</option>
                                    {unlinkedOpenThreads().map(t => (
                                      <option key={t.id} value={t.id}>
                                        {t.text.length > 80 ? t.text.slice(0, 80) + '…' : t.text}
                                      </option>
                                    ))}
                                  </select>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                        {/* Session notes - collapsible */}
                        {questNotesFor(quest.note_ids).length > 0 && (
                          <div>
                            <button
                              onClick={() => toggleNotesOpen(quest.id)}
                              className="flex items-center gap-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 hover:text-gray-300 transition-colors w-full text-left"
                            >
                              Session Notes ({questNotesFor(quest.note_ids).length})
                              {notesOpen.has(quest.id) ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                            </button>
                            {notesOpen.has(quest.id) && (
                              <ul className="grid gap-2">
                                {questNotesFor(quest.note_ids).map(n => (
                                  <li key={n.id} className="text-xs bg-gray-900 rounded-lg px-3 py-2">
                                    <time className="text-gray-500 block mb-0.5">{new Date(n.created_at).toLocaleDateString()}</time>
                                    <p className="text-gray-300">{n.summary.length > 120 ? n.summary.slice(0, 120) + '…' : n.summary}</p>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>
                        )}
                        {/* Loot - collapsible */}
                        {linkedLoot.length > 0 && (
                          <div>
                            <button
                              onClick={() => toggleLinked(quest.id)}
                              className="flex items-center gap-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 hover:text-gray-300 transition-colors w-full text-left"
                            >
                              Loot ({linkedLoot.length})
                              {linkedOpen.has(quest.id) ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                            </button>
                            {linkedOpen.has(quest.id) && (
                              <ul className="grid gap-1.5">
                                {linkedLoot.map(l => (
                                  <li key={l.id} className="text-xs bg-gray-900 rounded-lg px-3 py-2 text-gray-300">
                                    {l.item_name} <span className="text-gray-500">— {l.acquired_by}</span>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>
                        )}
                        <p className="text-xs text-gray-600">
                          Created {new Date(quest.created_at).toLocaleDateString()} ·{' '}
                          {quest.note_ids.length} note{quest.note_ids.length !== 1 ? 's' : ''}
                        </p>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )
      )}
    </div>
  )
}
