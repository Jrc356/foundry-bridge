import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, ChevronUp, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { deleteNote, getCombat, getDecisions, getNotes, getQuotes, getNoteEvents, getNoteLoot, getNoteThreads, getNoteQuests } from '../../api'
import type { CombatUpdate, Decision, ImportantQuote, Note, Event, Loot, Thread, Quest } from '../../types'
import { TabHeader } from '../../components/TabHeader'

export default function NotesTab({ gameId }: { gameId: number }) {
  const qc = useQueryClient()
  const { data: notes = [], isLoading } = useQuery({ queryKey: ['notes', gameId], queryFn: () => getNotes(gameId) })
  const { data: combat = [] } = useQuery({ queryKey: ['combat', gameId], queryFn: () => getCombat(gameId) })
  const { data: decisions = [] } = useQuery({ queryKey: ['decisions', gameId], queryFn: () => getDecisions(gameId) })
  const { data: quotes = [] } = useQuery({ queryKey: ['quotes', gameId], queryFn: () => getQuotes(gameId) })
  const { data: threads = [] } = useQuery({ queryKey: ['threads', gameId], queryFn: () => getNoteThreads(gameId, 0).catch(() => []) })
  const { data: quests = [] } = useQuery({ queryKey: ['quests', gameId], queryFn: () => getNoteQuests(gameId, 0).catch(() => []) })
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  const deleteMut = useMutation({
    mutationFn: deleteNote,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notes', gameId] }),
  })

  const toggle = (id: number) => setExpanded(s => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n })

  if (isLoading) return <LoadingState />

  return (
    <div className="p-6 max-w-4xl">
      <TabHeader title="Session Notes" count={notes.length} />
      {notes.length === 0 ? (
        <EmptyState message="No notes generated yet. Notes appear automatically after a session is transcribed." />
      ) : (
        <div className="grid gap-4">
          {notes.map((note: Note) => (
            <NoteCard
              key={note.id}
              note={note}
              gameId={gameId}
              expanded={expanded.has(note.id)}
              onToggle={() => toggle(note.id)}
              combat={combat as CombatUpdate[]}
              decisions={decisions as Decision[]}
              quotes={quotes as ImportantQuote[]}
              threads={threads as Thread[]}
              quests={quests as Quest[]}
              onDelete={() => deleteMut.mutate(note.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

interface NoteCardProps {
  note: Note
  gameId: number
  expanded: boolean
  onToggle: () => void
  combat: CombatUpdate[]
  decisions: Decision[]
  quotes: ImportantQuote[]
  threads: Thread[]
  quests: Quest[]
  onDelete: () => void
}

function NoteCard({ note, gameId, expanded, onToggle, combat, decisions, quotes, threads, quests, onDelete }: NoteCardProps) {
  // Fetch events and loot only when expanded (per-note queries)
  const { data: events = [] } = useQuery({
    queryKey: ['noteEvents', gameId, note.id],
    queryFn: () => getNoteEvents(gameId, note.id),
    enabled: expanded,
  })
  const { data: loot = [] } = useQuery({
    queryKey: ['noteLoot', gameId, note.id],
    queryFn: () => getNoteLoot(gameId, note.id),
    enabled: expanded,
  })

  const noteCombat = combat.filter(c => c.note_id === note.id)
  const noteDecisions = decisions.filter(d => d.note_id === note.id)
  const noteQuotes = quotes.filter(q => q.note_id === note.id)
  const noteEvents = (events as Event[])
  const noteLoot = (loot as Loot[])
  const noteThreads = threads.filter(t => t.resolved_by_note_id === note.id)
  const noteQuestList = quests.filter(q => q.note_ids.includes(note.id))
  const hasExtras = noteCombat.length > 0 || noteDecisions.length > 0 || noteQuotes.length > 0 || noteThreads.length > 0 || noteQuestList.length > 0

  // Compute if there *could* be extras (for expansion button) - includes events/loot which we don't know until fetched
  const hasKnownExtras = hasExtras

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700">
      <div className="p-5">
        <div className="flex justify-between items-start gap-4">
          <p className="text-gray-100 leading-relaxed flex-1">{note.summary}</p>
          <div className="flex items-center gap-2 shrink-0">
            {hasKnownExtras && (
              <button onClick={onToggle} className="text-gray-400 hover:text-gray-200 transition-colors p-1">
                {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </button>
            )}
            <button onClick={() => confirm('Delete note?') && onDelete()}
              className="text-gray-600 hover:text-red-400 transition-colors p-1">
              <Trash2 size={14} />
            </button>
          </div>
        </div>
        <div className="text-xs text-gray-500 mt-2 flex items-center gap-3">
          <span>{new Date(note.created_at).toLocaleString()}</span>
          <span>{note.source_transcript_ids.length} transcript{note.source_transcript_ids.length !== 1 ? 's' : ''}</span>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-gray-700 p-5 grid gap-4">
          {noteDecisions.length > 0 && (
            <section>
              <h4 className="text-xs font-semibold text-purple-400 uppercase tracking-wider mb-2">Decisions</h4>
              <ul className="grid gap-1.5">
                {noteDecisions.map(d => (
                  <li key={d.id} className="text-sm text-gray-300">
                    <span className="text-gray-500">{d.made_by}:</span> {d.decision}
                  </li>
                ))}
              </ul>
            </section>
          )}
          {noteCombat.length > 0 && (
            <section>
              <h4 className="text-xs font-semibold text-red-400 uppercase tracking-wider mb-2">Combat</h4>
              <ul className="grid gap-2">
                {noteCombat.map(c => (
                  <li key={c.id} className="text-sm">
                    <div className="text-gray-200 font-medium">{c.encounter}</div>
                    <div className="text-gray-400">{c.outcome}</div>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {noteQuotes.length > 0 && (
            <section>
              <h4 className="text-xs font-semibold text-blue-400 uppercase tracking-wider mb-2">Quotes</h4>
              <ul className="grid gap-2">
                {noteQuotes.map(q => (
                  <li key={q.id} className="text-sm text-gray-300 italic border-l-2 border-blue-600 pl-3">
                    "{q.text}"
                    {q.speaker && <span className="text-gray-500 not-italic"> — {q.speaker}</span>}
                  </li>
                ))}
              </ul>
            </section>
          )}
          {noteEvents.length > 0 && (
            <section>
              <h4 className="text-xs font-semibold text-green-400 uppercase tracking-wider mb-2">Events</h4>
              <ul className="grid gap-1.5">
                {noteEvents.map(e => (
                  <li key={e.id} className="text-sm text-gray-300">
                    {e.text}
                  </li>
                ))}
              </ul>
            </section>
          )}
          {noteLoot.length > 0 && (
            <section>
              <h4 className="text-xs font-semibold text-yellow-400 uppercase tracking-wider mb-2">Loot</h4>
              <ul className="grid gap-1.5">
                {noteLoot.map(l => (
                  <li key={l.id} className="text-sm text-gray-300">
                    <span className="text-gray-400">{l.acquired_by}:</span> {l.item_name}
                  </li>
                ))}
              </ul>
            </section>
          )}
          {noteThreads.length > 0 && (
            <section>
              <h4 className="text-xs font-semibold text-cyan-400 uppercase tracking-wider mb-2">Resolved Threads</h4>
              <ul className="grid gap-2">
                {noteThreads.map(t => (
                  <li key={t.id} className="text-sm">
                    <div className="text-gray-200">{t.text}</div>
                    {t.resolution && <div className="text-gray-400 text-xs mt-1">Resolution: {t.resolution}</div>}
                  </li>
                ))}
              </ul>
            </section>
          )}
          {noteQuestList.length > 0 && (
            <section>
              <h4 className="text-xs font-semibold text-orange-400 uppercase tracking-wider mb-2">Quests</h4>
              <ul className="grid gap-2">
                {noteQuestList.map(q => (
                  <li key={q.id} className="text-sm">
                    <div className="text-gray-200 font-medium">{q.name}</div>
                    <div className="text-gray-400 text-xs">Status: {q.status}</div>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </div>
  )
}

export function LoadingState() {
  return <div className="p-6 text-gray-400">Loading…</div>
}

export function EmptyState({ message }: { message: string }) {
  return <p className="text-gray-500 text-sm mt-4">{message}</p>
}
