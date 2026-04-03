import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { getTranscripts } from '../../api'
import { TabHeader } from '../../components/TabHeader'
import type { Transcript } from '../../types'
import { formatTimestamp } from '../../utils/datetime'

const PAGE_SIZE = 50

export default function TranscriptsTab({ gameId }: { gameId: number }) {
  const [charFilter, setCharFilter] = useState('')
  const [offset, setOffset] = useState(0)

  const params = { limit: PAGE_SIZE, offset, ...(charFilter.trim() ? { character_name: charFilter.trim() } : {}) }

  const { data: transcripts = [], isLoading } = useQuery({
    queryKey: ['transcripts', gameId, params],
    queryFn: () => getTranscripts(gameId, params),
    refetchInterval: 5000,
  })

  const handleFilter = (v: string) => { setCharFilter(v); setOffset(0) }

  return (
    <div className="p-6">
      <TabHeader title="Transcripts" count={transcripts.length} />

      <div className="flex gap-3 mb-5">
        <input
          placeholder="Filter by character name…"
          value={charFilter}
          onChange={e => handleFilter(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 w-64"
        />
      </div>

      {isLoading ? (
        <p className="text-gray-400">Loading…</p>
      ) : transcripts.length === 0 ? (
        <p className="text-gray-500 text-sm">No transcripts found.</p>
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-gray-700">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-800 text-left text-xs text-gray-400 uppercase tracking-wider">
                  <th className="px-4 py-3">Character</th>
                  <th className="px-4 py-3">Turn</th>
                  <th className="px-4 py-3">Text</th>
                  <th className="px-4 py-3">Confidence</th>
                  <th className="px-4 py-3">Processed</th>
                  <th className="px-4 py-3">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {transcripts.map((t: Transcript) => (
                  <tr key={t.id} className="hover:bg-gray-800/50">
                    <td className="px-4 py-3 text-purple-300 font-medium whitespace-nowrap">{t.character_name}</td>
                    <td className="px-4 py-3 text-gray-400 text-center">{t.turn_index}</td>
                    <td className="px-4 py-3 text-gray-200 max-w-md">
                      <p className="line-clamp-2">{t.text}</p>
                    </td>
                    <td className="px-4 py-3 text-gray-400 whitespace-nowrap">{(t.end_of_turn_confidence * 100).toFixed(0)}%</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${t.note_taker_processed ? 'bg-green-900 text-green-300' : 'bg-gray-700 text-gray-400'}`}>
                        {t.note_taker_processed ? 'yes' : 'no'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap text-xs">{formatTimestamp(t.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center gap-3 mt-4 text-sm">
            <button disabled={offset === 0} onClick={() => setOffset(o => Math.max(0, o - PAGE_SIZE))}
              className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 disabled:opacity-40 text-gray-200 rounded-lg transition-colors">← Prev</button>
            <span className="text-gray-500">rows {offset + 1}–{offset + transcripts.length}</span>
            <button disabled={transcripts.length < PAGE_SIZE} onClick={() => setOffset(o => o + PAGE_SIZE)}
              className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 disabled:opacity-40 text-gray-200 rounded-lg transition-colors">Next →</button>
          </div>
        </>
      )}
    </div>
  )
}
