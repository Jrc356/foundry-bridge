import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle, Circle, PlusCircle, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { createThread, deleteThread, getNotes, getQuests, getThreads, updateThread } from '../../api'
import { NotesBadge } from '../../components/NotesBadge'
import { TabHeader } from '../../components/TabHeader'
import type { Note, Quest, Thread } from '../../types'
import { formatTimestamp, sortByCreatedAtDesc } from '../../utils/datetime'

export default function ThreadsTab({ gameId }: { gameId: number }) {
  const qc = useQueryClient()
  const [filter, setFilter] = useState<'all' | 'open' | 'resolved'>('open')
  const [showAdd, setShowAdd] = useState(false)
  const [newText, setNewText] = useState('')
  const [resolving, setResolving] = useState<number | null>(null)
  const [resolution, setResolution] = useState('')
  const [linkingQuestFor, setLinkingQuestFor] = useState<number | null>(null)

  const resolved = filter === 'resolved' ? true : filter === 'open' ? false : undefined
  const { data: threads = [], isLoading } = useQuery({
    queryKey: ['threads', gameId, resolved],
    queryFn: () => getThreads(gameId, resolved),
  })
  const sortedThreads = sortByCreatedAtDesc(threads)

  const { data: quests = [] } = useQuery({
    queryKey: ['quests', gameId],
    queryFn: () => getQuests(gameId),
  })
  const questMap = new Map((quests as Quest[]).map(q => [q.id, q]))
  const { data: notes = [] } = useQuery({ queryKey: ['notes', gameId], queryFn: () => getNotes(gameId) })

  const createMut = useMutation({
    mutationFn: () => createThread(gameId, newText),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['threads', gameId] }); setShowAdd(false); setNewText('') },
  })

  const resolveMut = useMutation({
    mutationFn: (id: number) => updateThread(id, { is_resolved: true, resolution }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['threads', gameId] }); setResolving(null); setResolution('') },
  })

  const unlinkQuestMut = useMutation({
    mutationFn: (id: number) => updateThread(id, { quest_id: null }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['threads', gameId] }),
  })

  const linkQuestMut = useMutation({
    mutationFn: ({ id, quest_id }: { id: number; quest_id: number | null }) =>
      updateThread(id, { quest_id }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['threads', gameId] }); setLinkingQuestFor(null) },
  })

  const deleteMut = useMutation({
    mutationFn: deleteThread,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['threads', gameId] }),
  })

  if (isLoading) return <div className="p-6 text-gray-400">Loading…</div>

  return (
    <div className="p-6 max-w-4xl">
      <TabHeader
        title="Plot Threads"
        count={threads.length}
        action={
          <button onClick={() => setShowAdd(v => !v)}
            className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors">
            <PlusCircle size={14} /> Add Thread
          </button>
        }
      />

      {/* Filter */}
      <div className="flex gap-2 mb-5">
        {(['all', 'open', 'resolved'] as const).map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded-full text-xs font-medium capitalize transition-colors ${filter === f ? 'bg-purple-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>
            {f}
          </button>
        ))}
      </div>

      {/* Add form */}
      {showAdd && (
        <form onSubmit={e => { e.preventDefault(); createMut.mutate() }}
          className="bg-gray-800 rounded-xl p-4 mb-5 border border-gray-700 grid gap-3">
          <textarea required placeholder="What is the unanswered question or hook?" value={newText} onChange={e => setNewText(e.target.value)} rows={2}
            className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none" />
          <div className="flex gap-2">
            <button type="submit" disabled={createMut.isPending}
              className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors">
              {createMut.isPending ? 'Adding…' : 'Add'}
            </button>
            <button type="button" onClick={() => setShowAdd(false)}
              className="bg-gray-700 hover:bg-gray-600 text-gray-200 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors">Cancel</button>
          </div>
        </form>
      )}

      {threads.length === 0 ? (
        <p className="text-gray-500 text-sm">No {filter !== 'all' ? filter : ''} threads.</p>
      ) : (
        <div className="grid gap-3">
          {sortedThreads.map((thread: Thread) => (
            <div key={thread.id} className="bg-gray-800 rounded-xl border border-gray-700 p-4">
              {resolving === thread.id ? (
                <div className="grid gap-3">
                  <p className="text-sm text-gray-300 italic">"{thread.text}"</p>
                  <textarea placeholder="How was this resolved? (optional)" value={resolution} onChange={e => setResolution(e.target.value)} rows={2}
                    className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none" />
                  <div className="flex gap-2">
                    <button onClick={() => resolveMut.mutate(thread.id)} disabled={resolveMut.isPending}
                      className="flex items-center gap-1 bg-green-700 hover:bg-green-600 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors">
                      <CheckCircle size={13} /> Mark Resolved
                    </button>
                    <button onClick={() => setResolving(null)}
                      className="bg-gray-700 hover:bg-gray-600 text-gray-200 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors">Cancel</button>
                  </div>
                </div>
              ) : (
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    {thread.is_resolved
                      ? <CheckCircle size={16} className="text-green-500 mt-0.5 shrink-0" />
                      : <Circle size={16} className="text-gray-500 mt-0.5 shrink-0" />
                    }
                    <div>
                      <p className={`text-sm leading-relaxed ${thread.is_resolved ? 'text-gray-500 line-through' : 'text-gray-200'}`}>{thread.text}</p>
                      {thread.is_resolved && thread.resolution && (
                        <p className="text-xs text-green-600 mt-1 italic">Resolved: {thread.resolution}</p>
                      )}
                      {thread.opened_by_note_id != null && (
                        <NotesBadge notes={(notes as Note[]).filter(n => n.id === thread.opened_by_note_id)} />
                      )}
                      {thread.resolved_by_note_id != null && thread.resolved_by_note_id !== thread.opened_by_note_id && (
                        <NotesBadge notes={(notes as Note[]).filter(n => n.id === thread.resolved_by_note_id)} />
                      )}
                      {thread.quest_id != null && (
                        <span className="inline-flex items-center gap-1 mt-1 text-xs font-medium px-2 py-0.5 rounded-full bg-amber-900 text-amber-200 border border-amber-700">
                          ↗ {questMap.get(thread.quest_id)?.name ?? `Quest #${thread.quest_id}`}
                          <button
                            onClick={() => unlinkQuestMut.mutate(thread.id)}
                            className="ml-0.5 text-amber-400 hover:text-amber-100 leading-none"
                            title="Unlink quest"
                          >×</button>
                        </span>
                      )}
                      {linkingQuestFor === thread.id ? (
                        <div className="mt-2 flex items-center gap-2">
                          <select
                            autoFocus
                            className="bg-gray-900 border border-gray-600 rounded-lg px-2 py-1 text-xs text-gray-200 focus:outline-none focus:ring-2 focus:ring-amber-500"
                            defaultValue={thread.quest_id ?? ''}
                            onChange={e => {
                              const val = e.target.value
                              linkQuestMut.mutate({ id: thread.id, quest_id: val ? Number(val) : null })
                            }}
                          >
                            <option value="">— none —</option>
                            {(quests as Quest[]).map(q => (
                              <option key={q.id} value={q.id}>{q.name} ({q.status})</option>
                            ))}
                          </select>
                          <button onClick={() => setLinkingQuestFor(null)} className="text-xs text-gray-500 hover:text-gray-300">Cancel</button>
                        </div>
                      ) : null}
                      <p className="text-xs text-gray-600 mt-1">{formatTimestamp(thread.created_at)}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {!thread.is_resolved && (
                      <>
                        <button onClick={() => setLinkingQuestFor(v => v === thread.id ? null : thread.id)}
                          className="text-xs text-amber-600 hover:text-amber-400 font-medium transition-colors">
                          Link Quest ▾
                        </button>
                        <button onClick={() => setResolving(thread.id)}
                          className="text-xs text-green-600 hover:text-green-400 font-medium transition-colors">Resolve</button>
                      </>
                    )}
                    <button onClick={() => confirm('Delete thread?') && deleteMut.mutate(thread.id)}
                      className="text-gray-600 hover:text-red-400 transition-colors"><Trash2 size={14} /></button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
