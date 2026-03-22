import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { PlusCircle, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { createLoot, deleteLoot, getLoot } from '../../api'
import { TabHeader } from '../../components/TabHeader'
import type { Loot } from '../../types'

export default function LootTab({ gameId }: { gameId: number }) {
  const qc = useQueryClient()
  const { data: loot = [], isLoading } = useQuery({ queryKey: ['loot', gameId], queryFn: () => getLoot(gameId) })
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ item_name: '', acquired_by: '' })

  const createMut = useMutation({
    mutationFn: () => createLoot(gameId, form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['loot', gameId] }); setShowAdd(false); setForm({ item_name: '', acquired_by: '' }) },
  })

  const deleteMut = useMutation({
    mutationFn: deleteLoot,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['loot', gameId] }),
  })

  if (isLoading) return <div className="p-6 text-gray-400">Loading…</div>

  return (
    <div className="p-6 max-w-3xl">
      <TabHeader
        title="Loot"
        count={loot.length}
        action={
          <button onClick={() => setShowAdd(v => !v)}
            className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors">
            <PlusCircle size={14} /> Add Item
          </button>
        }
      />

      {showAdd && (
        <form onSubmit={e => { e.preventDefault(); createMut.mutate() }}
          className="bg-gray-800 rounded-xl p-4 mb-5 border border-gray-700 grid gap-3">
          <div className="grid grid-cols-2 gap-3">
            <input required placeholder="Item name" value={form.item_name} onChange={e => setForm(f => ({ ...f, item_name: e.target.value }))}
              className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500" />
            <input required placeholder="Acquired by" value={form.acquired_by} onChange={e => setForm(f => ({ ...f, acquired_by: e.target.value }))}
              className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500" />
          </div>
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

      {loot.length === 0 ? (
        <p className="text-gray-500 text-sm">No loot recorded.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-700">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-800 text-left text-xs text-gray-400 uppercase tracking-wider">
                <th className="px-4 py-3">Item</th>
                <th className="px-4 py-3">Acquired By</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3 w-8"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {loot.map((item: Loot) => (
                <tr key={item.id} className="hover:bg-gray-800/50">
                  <td className="px-4 py-3 text-amber-300 font-medium">{item.item_name}</td>
                  <td className="px-4 py-3 text-gray-300">{item.acquired_by}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{new Date(item.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3">
                    <button onClick={() => confirm('Remove loot?') && deleteMut.mutate(item.id)}
                      className="text-gray-600 hover:text-red-400 transition-colors"><Trash2 size={13} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
