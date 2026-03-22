import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { deleteCombat, getCombat } from '../../api'
import { TabHeader } from '../../components/TabHeader'
import type { CombatUpdate } from '../../types'

export default function CombatTab({ gameId }: { gameId: number }) {
  const qc = useQueryClient()
  const { data: combat = [], isLoading } = useQuery({ queryKey: ['combat', gameId], queryFn: () => getCombat(gameId) })

  const deleteMut = useMutation({
    mutationFn: deleteCombat,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['combat', gameId] }),
  })

  if (isLoading) return <div className="p-6 text-gray-400">Loading…</div>

  return (
    <div className="p-6 max-w-3xl">
      <TabHeader title="Combat" count={combat.length} />

      {combat.length === 0 ? (
        <p className="text-gray-500 text-sm">No combat encounters recorded.</p>
      ) : (
        <div className="grid gap-3">
          {combat.map((c: CombatUpdate) => (
            <div key={c.id} className="bg-gray-800 rounded-xl border border-gray-700 p-4 flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <p className="font-medium text-red-300">{c.encounter}</p>
                <p className="text-sm text-gray-400 mt-1">{c.outcome}</p>
                <p className="text-xs text-gray-600 mt-2">{new Date(c.created_at).toLocaleDateString()}</p>
              </div>
              <button onClick={() => confirm('Delete combat record?') && deleteMut.mutate(c.id)}
                className="text-gray-600 hover:text-red-400 transition-colors shrink-0"><Trash2 size={14} /></button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
