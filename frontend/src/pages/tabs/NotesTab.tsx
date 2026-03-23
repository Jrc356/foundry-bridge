import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, ChevronUp, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { deleteNote, getCombat, getDecisions, getNotes, getQuotes, getNoteEvents, getNoteLoot, getThreads, getQuests } from '../../api'
import type { CombatUpdate, Decision, ImportantQuote, Note, Event, Loot, Thread, Quest } from '../../types'
import { TabHeader } from '../../components/TabHeader'

export default function NotesTab({ gameId }: { gameId: number }) {
  const qc = useQueryClient()
  const { data: notes = [], isLoading } = useQuery({ queryKey: ['notes', gameId], queryFn: () => getNotes(gameId) })
  const { data: combat = [] } = useQuery({ queryKey: ['combat', gameId], queryFn: () => getCombat(gameId) })
  const { data: decisions = [] } = useQuery({ queryKey: ['decisions', gameId], queryFn: () => getDecisions(gameId) })
  const { data: quotes = [] } = useQuery({ queryKey: ['quotes', gameId], queryFn: () => getQuotes(gameId) })
  const { data: threads = [] } = useQuery({ queryKey: ['threads', gameId], queryFn: () => getThreads(gameId) })
  const { data: quests = [] } = useQuery({ queryKey: ['quests', gameId], queryFn: () => getQuests(gameId) })
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
  // Fetch events and loot upfront so badges show immediately
  const { data: events = [] } = useQuery({
    queryKey: ['noteEvents', gameId, note.id],
    queryFn: () => getNoteEvents(gameId, note.id),
  })
  const { data: loot = [] } = useQuery({
    queryKey: ['noteLoot', gameId, note.id],
    queryFn: () => getNoteLoot(gameId, note.id),
  })

  const noteCombat = combat.filter(c => c.note_id === note.id)
  const noteDecisions = decisions.filter(d => d.note_id === note.id)
  const noteQuotes = quotes.filter(q => q.note_id === note.id)
  const noteEvents = (events as Event[])
  const noteLoot = (loot as Loot[])
  const noteThreads = threads.filter(t => t.resolved_by_note_id === note.id)
  const noteQuestList = quests.filter(q => q.note_ids.includes(note.id))
  const hasExtras = noteCombat.length > 0 || noteDecisions.length > 0 || noteQuotes.length > 0 || noteEvents.length > 0 || noteLoot.length > 0 || noteThreads.length > 0 || noteQuestList.length > 0

  // Compute if there *could* be extras (for expansion button) - includes events/loot which we don't know until fetched
  const hasKnownExtras = hasExtras

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700">
      <div className="p-5">
        <div className="flex justify-between items-start gap-4">
          <div className="flex-1">
            <p className="text-gray-100 leading-relaxed">{note.summary}</p>
            <div className="flex flex-wrap gap-2 mt-3">
              {noteDecisions.length > 0 && <Badge label={`Decisions (${noteDecisions.length})`} color="bg-purple-900 text-purple-300" />}
              {noteCombat.length > 0 && <Badge label={`Combat (${noteCombat.length})`} color="bg-red-900 text-red-300" />}
              {noteQuotes.length > 0 && <Badge label={`Quotes (${noteQuotes.length})`} color="bg-blue-900 text-blue-300" />}
              {noteEvents.length > 0 && <Badge label={`Events (${noteEvents.length})`} color="bg-green-900 text-green-300" />}
              {noteLoot.length > 0 && <Badge label={`Loot (${noteLoot.length})`} color="bg-yellow-900 text-yellow-300" />}
              {noteThreads.length > 0 && <Badge label={`Threads (${noteThreads.length})`} color="bg-cyan-900 text-cyan-300" />}
              {noteQuestList.length > 0 && <Badge label={`Quests (${noteQuestList.length})`} color="bg-orange-900 text-orange-300" />}
            </div>
          </div>
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
        <div className="text-xs text-gray-500 mt-3 flex items-center gap-3">
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

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span className={`inline-block px-2.5 py-1 rounded-full text-xs font-medium ${color}`}>
      {label}
    </span>
  )
}

export function LoadingState() {
  return <div className="p-6 text-gray-400">Loading…</div>
}

export function EmptyState({ message }: { message: string }) {
  return <p className="text-gray-500 text-sm mt-4">{message}</p>
}
