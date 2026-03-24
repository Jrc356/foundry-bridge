import { ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'
import type { Note } from '../types'

/**
 * Renders a count badge for source notes. Clicking the badge expands/collapses
 * a list of truncated note summaries. Returns null when the notes array is empty.
 */
export function NotesBadge({ notes }: { notes: Note[] }) {
  const [open, setOpen] = useState(false)
  if (notes.length === 0) return null
  return (
    <div className="mt-1.5">
      <button
        onClick={e => { e.stopPropagation(); setOpen(v => !v) }}
        className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-indigo-900 text-indigo-300 border border-indigo-700 hover:bg-indigo-800 transition-colors"
      >
        {notes.length} {notes.length === 1 ? 'note' : 'notes'}
        {open ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
      </button>
      {open && (
        <ul className="mt-2 grid gap-1.5">
          {notes.map(n => (
            <li key={n.id} className="text-xs bg-gray-900 rounded-lg px-3 py-2 border border-gray-700/50">
              <time className="text-gray-500 block mb-0.5">{new Date(n.created_at).toLocaleDateString()}</time>
              <p className="text-gray-300">{n.summary.length > 120 ? n.summary.slice(0, 120) + '…' : n.summary}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
