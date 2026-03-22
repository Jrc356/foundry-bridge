import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { deleteQuote, getQuotes } from '../../api'
import { TabHeader } from '../../components/TabHeader'
import type { ImportantQuote } from '../../types'

export default function QuotesTab({ gameId }: { gameId: number }) {
  const qc = useQueryClient()
  const { data: quotes = [], isLoading } = useQuery({ queryKey: ['quotes', gameId], queryFn: () => getQuotes(gameId) })

  const deleteMut = useMutation({
    mutationFn: deleteQuote,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['quotes', gameId] }),
  })

  if (isLoading) return <div className="p-6 text-gray-400">Loading…</div>

  return (
    <div className="p-6 max-w-3xl">
      <TabHeader title="Important Quotes" count={quotes.length} />

      {quotes.length === 0 ? (
        <p className="text-gray-500 text-sm">No quotes recorded.</p>
      ) : (
        <div className="grid gap-3">
          {quotes.map((q: ImportantQuote) => (
            <div key={q.id} className="bg-gray-800 rounded-xl border border-gray-700 p-4 flex items-start justify-between gap-4">
              <div className="flex-1 border-l-2 border-blue-600 pl-3">
                <p className="text-gray-200 italic">"{q.text}"</p>
                {q.speaker && <p className="text-sm text-blue-400 mt-1">— {q.speaker}</p>}
                <p className="text-xs text-gray-600 mt-1">{new Date(q.created_at).toLocaleDateString()}</p>
              </div>
              <button onClick={() => confirm('Delete quote?') && deleteMut.mutate(q.id)}
                className="text-gray-600 hover:text-red-400 transition-colors shrink-0"><Trash2 size={14} /></button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
