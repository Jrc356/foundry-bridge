import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { PlusCircle, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { createDecision, deleteDecision, getDecisions, getNotes } from '../../api'
import { TabHeader } from '../../components/TabHeader'
import type { Decision } from '../../types'

export default function DecisionsTab({ gameId }: { gameId: number }) {
  const qc = useQueryClient()
  const { data: decisions = [], isLoading } = useQuery({ queryKey: ['decisions', gameId], queryFn: () => getDecisions(gameId) })
  const { data: notes = [] } = useQuery({ queryKey: ['notes', gameId], queryFn: () => getNotes(gameId) })
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ note_id: 0, decision: '', made_by: '' })

  const createMut = useMutation({
    mutationFn: () => createDecision(gameId, form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['decisions', gameId] }); setShowAdd(false); setForm({ note_id: 0, decision: '', made_by: '' }) },
  })

  const deleteMut = useMutation({
    mutationFn: deleteDecision,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['decisions', gameId] }),
  })

  if (isLoading) return <div className="p-6 text-gray-400">Loading…</div>

  return (
    <div className="p-6 max-w-3xl">
      <TabHeader
        title="Decisions"
        count={decisions.length}
        action={
          <button onClick={() => setShowAdd(v => !v)}
            className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors">
            <PlusCircle size={14} /> Add Decision
          </button>
        }
      />

      {showAdd && (
        <form onSubmit={e => { e.preventDefault(); createMut.mutate() }}
          className="bg-gray-800 rounded-xl p-4 mb-5 border border-gray-700 grid gap-3">
          <select required value={form.note_id || ''} onChange={e => setForm(f => ({ ...f, note_id: Number(e.target.value) }))}
            className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-purple-500">
            <option value="">Link to note…</option>
            {notes.map((n: { id: number; summary: string }) => (
              <option key={n.id} value={n.id}>{n.summary.slice(0, 60)}…</option>
            ))}
          </select>
          <input required placeholder="Decision" value={form.decision} onChange={e => setForm(f => ({ ...f, decision: e.target.value }))}
            className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500" />
          <input required placeholder="Made by (PC, NPC, or 'the party')" value={form.made_by} onChange={e => setForm(f => ({ ...f, made_by: e.target.value }))}
            className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500" />
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

      {decisions.length === 0 ? (
        <p className="text-gray-500 text-sm">No decisions recorded.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-700">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-800 text-left text-xs text-gray-400 uppercase tracking-wider">
                <th className="px-4 py-3">Decision</th>
                <th className="px-4 py-3">Made By</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3 w-8"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {decisions.map((d: Decision) => (
                <tr key={d.id} className="hover:bg-gray-800/50">
                  <td className="px-4 py-3 text-gray-200">{d.decision}</td>
                  <td className="px-4 py-3 text-purple-300">{d.made_by}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{new Date(d.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3">
                    <button onClick={() => confirm('Delete decision?') && deleteMut.mutate(d.id)}
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
