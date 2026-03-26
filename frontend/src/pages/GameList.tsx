import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { PlusCircle, Sword, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { createGame, deleteGame, getGames } from '../api'
import type { Game } from '../types'
import { formatTimestamp, sortByCreatedAtDesc } from '../utils/datetime'

export default function GameList() {
  const qc = useQueryClient()
  const { data: games = [], isLoading } = useQuery({ queryKey: ['games'], queryFn: getGames })
  const sortedGames = sortByCreatedAtDesc(games)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', hostname: '', world_id: '' })

  const createMut = useMutation({
    mutationFn: createGame,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['games'] }); setShowForm(false); setForm({ name: '', hostname: '', world_id: '' }) },
  })

  const deleteMut = useMutation({
    mutationFn: deleteGame,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['games'] }),
  })

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <Sword className="text-purple-400" size={32} />
          <h1 className="text-3xl font-bold text-white">Foundry Bridge</h1>
        </div>

        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-semibold text-gray-200">Your Campaigns</h2>
          <button
            onClick={() => setShowForm(v => !v)}
            className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            <PlusCircle size={16} /> New Campaign
          </button>
        </div>

        {showForm && (
          <form
            onSubmit={e => { e.preventDefault(); createMut.mutate(form) }}
            className="bg-gray-800 rounded-xl p-6 mb-6 border border-gray-700 grid gap-4"
          >
            <h3 className="font-semibold text-gray-100">Add Campaign</h3>
            <input required placeholder="Campaign name" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500" />
            <input required placeholder="Hostname (e.g. foundry.example.com)" value={form.hostname} onChange={e => setForm(f => ({ ...f, hostname: e.target.value }))}
              className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500" />
            <input required placeholder="World ID" value={form.world_id} onChange={e => setForm(f => ({ ...f, world_id: e.target.value }))}
              className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500" />
            <div className="flex gap-3">
              <button type="submit" disabled={createMut.isPending}
                className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                {createMut.isPending ? 'Creating…' : 'Create'}
              </button>
              <button type="button" onClick={() => setShowForm(false)}
                className="bg-gray-700 hover:bg-gray-600 text-gray-200 px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                Cancel
              </button>
            </div>
          </form>
        )}

        {isLoading ? (
          <p className="text-gray-400">Loading…</p>
        ) : games.length === 0 ? (
          <div className="text-center py-16 text-gray-500">
            <Sword size={48} className="mx-auto mb-4 opacity-30" />
            <p>No campaigns yet. Create one to get started.</p>
          </div>
        ) : (
          <div className="grid gap-4">
            {sortedGames.map((game: Game) => (
              <div key={game.id} className="bg-gray-800 rounded-xl border border-gray-700 p-5 flex items-center justify-between hover:border-purple-700 transition-colors">
                <Link to={`/games/${game.id}`} className="flex-1 min-w-0">
                  <div className="font-semibold text-white truncate">{game.name}</div>
                  <div className="text-xs text-gray-400 mt-1">{game.hostname} · {game.world_id}</div>
                  <div className="text-xs text-gray-500 mt-1">{formatTimestamp(game.created_at)}</div>
                </Link>
                <button
                  onClick={() => confirm(`Delete "${game.name}"?`) && deleteMut.mutate(game.id)}
                  className="ml-4 text-gray-600 hover:text-red-400 transition-colors"
                  title="Delete campaign"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
