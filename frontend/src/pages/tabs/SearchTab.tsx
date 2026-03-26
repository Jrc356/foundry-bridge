import { useQuery } from '@tanstack/react-query'
import { BookOpen, Dices, MapPin, Search, Shield, Sparkles, Swords, Trophy, Zap } from 'lucide-react'
import { useState } from 'react'
import { searchGame } from '../../api'
import { TabHeader } from '../../components/TabHeader'
import { formatTimestamp, sortByCreatedAtDesc } from '../../utils/datetime'
import type {
  CombatUpdate,
  Decision,
  Entity,
  Event,
  Loot,
  Note,
  Quest,
  Thread,
} from '../../types'

const TYPE_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'entities', label: 'Entities', icon: Shield },
  { value: 'notes', label: 'Notes', icon: BookOpen },
  { value: 'threads', label: 'Threads', icon: Sparkles },
  { value: 'events', label: 'Events', icon: Zap },
  { value: 'decisions', label: 'Decisions', icon: Dices },
  { value: 'loot', label: 'Loot', icon: Trophy },
  { value: 'combat', label: 'Combat', icon: Swords },
  { value: 'quests', label: 'Quests', icon: MapPin },
] as const

const ENTITY_TYPE_COLORS: Record<string, string> = {
  npc: 'bg-purple-900 text-purple-200',
  location: 'bg-emerald-900 text-emerald-200',
  item: 'bg-blue-900 text-blue-200',
  faction: 'bg-red-900 text-red-200',
  other: 'bg-gray-700 text-gray-300',
}

export default function SearchTab({ gameId }: { gameId: number }) {
  const [inputValue, setInputValue] = useState('')
  const [submittedQuery, setSubmittedQuery] = useState('')
  const [contentType, setContentType] = useState('all')

  const { data, isLoading, isError } = useQuery({
    queryKey: ['search', gameId, submittedQuery, contentType],
    queryFn: () =>
      searchGame(gameId, submittedQuery, contentType === 'all' ? undefined : contentType),
    enabled: submittedQuery.trim().length > 0,
  })

  const totalResults = data
    ? data.entities.length +
      data.notes.length +
      data.threads.length +
      data.events.length +
      data.decisions.length +
      data.loot.length +
      data.combat.length +
      (data.quests?.length ?? 0)
    : 0

  const sortedEntities = data ? sortByCreatedAtDesc(data.entities) : []
  const sortedNotes = data ? sortByCreatedAtDesc(data.notes) : []
  const sortedThreads = data ? sortByCreatedAtDesc(data.threads) : []
  const sortedEvents = data ? sortByCreatedAtDesc(data.events) : []
  const sortedDecisions = data ? sortByCreatedAtDesc(data.decisions) : []
  const sortedLoot = data ? sortByCreatedAtDesc(data.loot) : []
  const sortedCombat = data ? sortByCreatedAtDesc(data.combat) : []
  const sortedQuests = data ? sortByCreatedAtDesc(data.quests) : []

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmittedQuery(inputValue.trim())
  }

  return (
    <div className="p-6 max-w-4xl">
      <TabHeader
        title="Search"
        count={submittedQuery ? totalResults : undefined}
      />

      {/* Search bar */}
      <form onSubmit={handleSubmit} className="flex gap-2 mb-6">
        <div className="relative flex-1">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
          <input
            type="text"
            placeholder="Search across all content…"
            value={inputValue}
            onChange={e => setInputValue(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
        </div>
        <select
          value={contentType}
          onChange={e => setContentType(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-purple-500"
        >
          {TYPE_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <button
          type="submit"
          disabled={!inputValue.trim()}
          className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          Search
        </button>
      </form>

      {/* States */}
      {!submittedQuery && (
        <p className="text-gray-500 text-sm">
          Enter a query above to semantically search across your campaign data.
        </p>
      )}

      {submittedQuery && isLoading && (
        <p className="text-gray-400 text-sm">Searching…</p>
      )}

      {submittedQuery && isError && (
        <p className="text-red-400 text-sm">Something went wrong. Please try again.</p>
      )}

      {submittedQuery && data && totalResults === 0 && (
        <p className="text-gray-500 text-sm">No results for "{submittedQuery}".</p>
      )}

      {/* Results */}
      {data && totalResults > 0 && (
        <div className="grid gap-6">
          {/* Entities */}
          {data.entities.length > 0 && (
            <Section title="Entities" icon={<Shield size={14} />} count={data.entities.length}>
              {sortedEntities.map((e: Entity) => (
                <div key={e.id} className="bg-gray-800 rounded-xl border border-gray-700 p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full capitalize ${ENTITY_TYPE_COLORS[e.entity_type] ?? 'bg-gray-700 text-gray-300'}`}>
                      {e.entity_type}
                    </span>
                    <span className="text-sm font-semibold text-gray-100">{e.name}</span>
                  </div>
                  <p className="text-sm text-gray-400">{e.description}</p>
                </div>
              ))}
            </Section>
          )}

          {/* Notes */}
          {data.notes.length > 0 && (
            <Section title="Notes" icon={<BookOpen size={14} />} count={data.notes.length}>
              {sortedNotes.map((n: Note) => (
                <div key={n.id} className="bg-gray-800 rounded-xl border border-gray-700 p-4">
                  <p className="text-sm text-gray-200 leading-relaxed">{n.summary}</p>
                  <p className="text-xs text-gray-500 mt-2">{formatTimestamp(n.created_at)}</p>
                </div>
              ))}
            </Section>
          )}

          {/* Threads */}
          {data.threads.length > 0 && (
            <Section title="Threads" icon={<Sparkles size={14} />} count={data.threads.length}>
              {sortedThreads.map((t: Thread) => (
                <div key={t.id} className="bg-gray-800 rounded-xl border border-gray-700 p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${t.is_resolved ? 'bg-green-900 text-green-200' : 'bg-yellow-900 text-yellow-200'}`}>
                      {t.is_resolved ? 'Resolved' : 'Open'}
                    </span>
                  </div>
                  <p className="text-sm text-gray-200">{t.text}</p>
                  {t.resolution && (
                    <p className="text-xs text-gray-400 mt-1 italic">Resolution: {t.resolution}</p>
                  )}
                </div>
              ))}
            </Section>
          )}

          {/* Events */}
          {data.events.length > 0 && (
            <Section title="Events" icon={<Zap size={14} />} count={data.events.length}>
              {sortedEvents.map((e: Event) => (
                <div key={e.id} className="bg-gray-800 rounded-xl border border-gray-700 p-4">
                  <p className="text-sm text-gray-200">{e.text}</p>
                  <p className="text-xs text-gray-500 mt-1">{formatTimestamp(e.created_at)}</p>
                </div>
              ))}
            </Section>
          )}

          {/* Decisions */}
          {data.decisions.length > 0 && (
            <Section title="Decisions" icon={<Dices size={14} />} count={data.decisions.length}>
              {sortedDecisions.map((d: Decision) => (
                <div key={d.id} className="bg-gray-800 rounded-xl border border-gray-700 p-4">
                  <p className="text-sm text-gray-200">{d.decision}</p>
                  <p className="text-xs text-gray-500 mt-1">by {d.made_by} · {formatTimestamp(d.created_at)}</p>
                </div>
              ))}
            </Section>
          )}

          {/* Loot */}
          {data.loot.length > 0 && (
            <Section title="Loot" icon={<Trophy size={14} />} count={data.loot.length}>
              {sortedLoot.map((l: Loot) => (
                <div key={l.id} className="bg-gray-800 rounded-xl border border-gray-700 p-4">
                  <p className="text-sm font-medium text-gray-100">{l.item_name}</p>
                  <p className="text-xs text-gray-500 mt-0.5">acquired by {l.acquired_by}</p>
                </div>
              ))}
            </Section>
          )}

          {/* Combat */}
          {data.combat.length > 0 && (
            <Section title="Combat" icon={<Swords size={14} />} count={data.combat.length}>
              {sortedCombat.map((c: CombatUpdate) => (
                <div key={c.id} className="bg-gray-800 rounded-xl border border-gray-700 p-4">
                  <p className="text-sm font-medium text-gray-100">{c.encounter}</p>
                  <p className="text-sm text-gray-400 mt-1">{c.outcome}</p>
                  <p className="text-xs text-gray-500 mt-1">{formatTimestamp(c.created_at)}</p>
                </div>
              ))}
            </Section>
          )}

          {/* Quests */}
          {(data.quests?.length ?? 0) > 0 && (
            <Section title="Quests" icon={<MapPin size={14} />} count={data.quests.length}>
              {sortedQuests.map((q: Quest) => (
                <div key={q.id} className="bg-gray-800 rounded-xl border border-gray-700 p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${
                      q.status === 'active'
                        ? 'bg-amber-900 text-amber-200 border-amber-700'
                        : 'bg-emerald-900 text-emerald-200 border-emerald-700'
                    }`}>
                      {q.status}
                    </span>
                    <span className="text-sm font-semibold text-gray-100">{q.name}</span>
                  </div>
                  <p className="text-sm text-gray-400">{q.description}</p>
                </div>
              ))}
            </Section>
          )}
        </div>
      )}
    </div>
  )
}

function Section({
  title,
  icon,
  count,
  children,
}: {
  title: string
  icon: React.ReactNode
  count: number
  children: React.ReactNode
}) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-gray-400">{icon}</span>
        <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">{title}</h3>
        <span className="text-xs bg-gray-700 text-gray-400 px-2 py-0.5 rounded-full">{count}</span>
      </div>
      <div className="grid gap-2">{children}</div>
    </div>
  )
}
