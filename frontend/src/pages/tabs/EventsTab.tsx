import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { PlusCircle, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { createEvent, deleteEvent, getEvents, getNotes } from '../../api'
import { NotesBadge } from '../../components/NotesBadge'
import { TabHeader } from '../../components/TabHeader'
import type { Event, Note } from '../../types'
import { formatTimestamp, sortByCreatedAtDesc } from '../../utils/datetime'

export default function EventsTab({ gameId }: { gameId: number }) {
  const qc = useQueryClient()
  const { data: events = [], isLoading } = useQuery({ queryKey: ['events', gameId], queryFn: () => getEvents(gameId) })
  const sortedEvents = sortByCreatedAtDesc(events)
  const { data: notes = [] } = useQuery({ queryKey: ['notes', gameId], queryFn: () => getNotes(gameId) })
  const [showAdd, setShowAdd] = useState(false)
  const [text, setText] = useState('')

  const createMut = useMutation({
    mutationFn: () => createEvent(gameId, text),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['events', gameId] }); setShowAdd(false); setText('') },
  })

  const deleteMut = useMutation({
    mutationFn: deleteEvent,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['events', gameId] }),
  })

  if (isLoading) return <div className="p-6 text-gray-400">Loading…</div>

  return (
    <div className="p-6 max-w-3xl">
      <TabHeader
        title="Events"
        count={events.length}
        action={
          <button onClick={() => setShowAdd(v => !v)}
            className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors">
            <PlusCircle size={14} /> Add Event
          </button>
        }
      />

      {showAdd && (
        <form onSubmit={e => { e.preventDefault(); createMut.mutate() }}
          className="bg-gray-800 rounded-xl p-4 mb-5 border border-gray-700 grid gap-3">
          <textarea required placeholder="Describe the event…" value={text} onChange={e => setText(e.target.value)} rows={2}
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

      {events.length === 0 ? (
        <p className="text-gray-500 text-sm">No events recorded.</p>
      ) : (
        <div className="grid gap-2">
          {sortedEvents.map((event: Event) => (
            <div key={event.id} className="bg-gray-800 rounded-xl border border-gray-700 p-4 flex items-start justify-between gap-4">
              <div>
                <p className="text-sm text-gray-200">{event.text}</p>
                <p className="text-xs text-gray-500 mt-1">{formatTimestamp(event.created_at)}</p>
                <NotesBadge notes={(notes as Note[]).filter(n => event.note_ids.includes(n.id))} />
              </div>
              <button onClick={() => confirm('Delete event?') && deleteMut.mutate(event.id)}
                className="text-gray-600 hover:text-red-400 transition-colors shrink-0"><Trash2 size={13} /></button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
