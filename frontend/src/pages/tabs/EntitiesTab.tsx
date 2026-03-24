import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, PlusCircle, Trash2, X } from 'lucide-react'
import { useState } from 'react'
import { createEntity, deleteEntity, getEntities, getNotes, updateEntity } from '../../api'
import { NotesBadge } from '../../components/NotesBadge'
import { TabHeader } from '../../components/TabHeader'
import type { Entity, Note } from '../../types'

const ENTITY_TYPES = ['npc', 'location', 'item', 'faction', 'other'] as const

const TYPE_COLORS: Record<string, string> = {
  npc: 'bg-purple-900 text-purple-200',
  location: 'bg-emerald-900 text-emerald-200',
  item: 'bg-blue-900 text-blue-200',
  faction: 'bg-red-900 text-red-200',
  other: 'bg-gray-700 text-gray-300',
}

export default function EntitiesTab({ gameId }: { gameId: number }) {
  const qc = useQueryClient()
  const [filter, setFilter] = useState<string>('all')
  const [showAdd, setShowAdd] = useState(false)
  const [new_, setNew] = useState({ name: '', description: '', entity_type: 'npc' as Entity['entity_type'] })
  const [editing, setEditing] = useState<number | null>(null)
  const [editValues, setEditValues] = useState<Partial<Entity>>({})

  const { data: entities = [], isLoading } = useQuery({
    queryKey: ['entities', gameId, filter === 'all' ? undefined : filter],
    queryFn: () => getEntities(gameId, filter === 'all' ? undefined : filter),
  })
  const { data: notes = [] } = useQuery({ queryKey: ['notes', gameId], queryFn: () => getNotes(gameId) })

  const createMut = useMutation({
    mutationFn: () => createEntity(gameId, new_),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['entities', gameId] }); setShowAdd(false); setNew({ name: '', description: '', entity_type: 'npc' }) },
  })

  const updateMut = useMutation({
    mutationFn: (id: number) => updateEntity(id, editValues),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['entities', gameId] }); setEditing(null) },
  })

  const deleteMut = useMutation({
    mutationFn: deleteEntity,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['entities', gameId] }),
  })

  const startEdit = (e: Entity) => { setEditing(e.id); setEditValues({ name: e.name, description: e.description, entity_type: e.entity_type }) }

  if (isLoading) return <div className="p-6 text-gray-400">Loading…</div>

  return (
    <div className="p-6 max-w-4xl">
      <TabHeader
        title="Entities"
        count={entities.length}
        action={
          <button onClick={() => setShowAdd(v => !v)}
            className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors">
            <PlusCircle size={14} /> Add Entity
          </button>
        }
      />

      {/* Type filter */}
      <div className="flex gap-2 flex-wrap mb-5">
        {['all', ...ENTITY_TYPES].map(t => (
          <button key={t} onClick={() => setFilter(t)}
            className={`px-3 py-1 rounded-full text-xs font-medium capitalize transition-colors ${filter === t ? 'bg-purple-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>
            {t}
          </button>
        ))}
      </div>

      {/* Add form */}
      {showAdd && (
        <form onSubmit={e => { e.preventDefault(); createMut.mutate() }}
          className="bg-gray-800 rounded-xl p-4 mb-5 border border-gray-700 grid gap-3">
          <div className="grid grid-cols-2 gap-3">
            <input required placeholder="Name" value={new_.name} onChange={e => setNew(f => ({ ...f, name: e.target.value }))}
              className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500" />
            <select value={new_.entity_type} onChange={e => setNew(f => ({ ...f, entity_type: e.target.value as Entity['entity_type'] }))}
              className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-purple-500">
              {ENTITY_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <textarea required placeholder="Description" value={new_.description} onChange={e => setNew(f => ({ ...f, description: e.target.value }))} rows={2}
            className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none" />
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

      {entities.length === 0 ? (
        <p className="text-gray-500 text-sm">No entities found.</p>
      ) : (
        <div className="grid gap-3">
          {entities.map((entity: Entity) => (
            <div key={entity.id} className="bg-gray-800 rounded-xl border border-gray-700 p-4">
              {editing === entity.id ? (
                <div className="grid gap-3">
                  <div className="grid grid-cols-2 gap-3">
                    <input value={editValues.name ?? ''} onChange={e => setEditValues(v => ({ ...v, name: e.target.value }))}
                      className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-purple-500" />
                    <select value={editValues.entity_type ?? 'npc'} onChange={e => setEditValues(v => ({ ...v, entity_type: e.target.value as Entity['entity_type'] }))}
                      className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-purple-500">
                      {ENTITY_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                  <textarea value={editValues.description ?? ''} onChange={e => setEditValues(v => ({ ...v, description: e.target.value }))} rows={3}
                    className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none" />
                  <div className="flex gap-2">
                    <button onClick={() => updateMut.mutate(entity.id)} disabled={updateMut.isPending}
                      className="flex items-center gap-1 bg-green-700 hover:bg-green-600 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors">
                      <Check size={13} /> Save
                    </button>
                    <button onClick={() => setEditing(null)}
                      className="flex items-center gap-1 bg-gray-700 hover:bg-gray-600 text-gray-200 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors">
                      <X size={13} /> Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0 cursor-pointer" onClick={() => startEdit(entity)}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-white">{entity.name}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${TYPE_COLORS[entity.entity_type]}`}>{entity.entity_type}</span>
                    </div>
                    <p className="text-sm text-gray-400 leading-relaxed">{entity.description}</p>
                    <NotesBadge notes={(notes as Note[]).filter(n => entity.note_ids.includes(n.id))} />
                  </div>
                  <button onClick={() => confirm(`Delete ${entity.name}?`) && deleteMut.mutate(entity.id)}
                    className="text-gray-600 hover:text-red-400 transition-colors shrink-0"><Trash2 size={14} /></button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
