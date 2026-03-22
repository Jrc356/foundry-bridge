import { useQuery } from '@tanstack/react-query'
import { Users } from 'lucide-react'
import { getPlayerCharacters } from '../../api'
import { TabHeader } from '../../components/TabHeader'
import type { PlayerCharacter } from '../../types'

export default function PlayerCharactersTab({ gameId }: { gameId: number }) {
  const { data: characters = [], isLoading } = useQuery({
    queryKey: ['characters', gameId],
    queryFn: () => getPlayerCharacters(gameId),
  })

  if (isLoading) return <div className="p-6 text-gray-400">Loading…</div>

  return (
    <div className="p-6 max-w-2xl">
      <TabHeader title="Player Characters" count={characters.length} />

      {characters.length === 0 ? (
        <p className="text-gray-500 text-sm">No player characters recorded yet. They appear when audio transcription runs.</p>
      ) : (
        <div className="grid gap-2">
          {characters.map((c: PlayerCharacter) => (
            <div key={c.id} className="bg-gray-800 rounded-xl border border-gray-700 p-4 flex items-center gap-3">
              <Users size={16} className="text-purple-400 shrink-0" />
              <span className="text-gray-100 font-medium">{c.character_name}</span>
              <span className="ml-auto text-xs text-gray-500">{new Date(c.created_at).toLocaleDateString()}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
