import { useQuery } from '@tanstack/react-query'
import {
  BookOpen,
  ChevronLeft,
  Dices,
  MapPin,
  MessageCircle,
  ScrollText,
  Search,
  Shield,
  Sparkles,
  Swords,
  Trophy,
  Users,
  Zap,
} from 'lucide-react'
import { Link, Navigate, Route, Routes, useParams } from 'react-router-dom'
import { getGame } from '../api'
import CombatTab from './tabs/CombatTab'
import DecisionsTab from './tabs/DecisionsTab'
import EntitiesTab from './tabs/EntitiesTab'
import EventsTab from './tabs/EventsTab'
import LootTab from './tabs/LootTab'
import NotesTab from './tabs/NotesTab'
import PlayerCharactersTab from './tabs/PlayerCharactersTab'
import QuestLogTab from './tabs/QuestLogTab'
import QuotesTab from './tabs/QuotesTab'
import SearchTab from './tabs/SearchTab'
import ThreadsTab from './tabs/ThreadsTab'
import TranscriptsTab from './tabs/TranscriptsTab'

const TABS = [
  { id: 'search', label: 'Search', icon: Search },
  { id: 'quests', label: 'Quest Log', icon: MapPin },
  { id: 'notes', label: 'Notes', icon: BookOpen },
  { id: 'entities', label: 'Entities', icon: Shield },
  { id: 'threads', label: 'Threads', icon: Sparkles },
  { id: 'transcripts', label: 'Transcripts', icon: ScrollText },
  { id: 'loot', label: 'Loot', icon: Trophy },
  { id: 'decisions', label: 'Decisions', icon: Dices },
  { id: 'events', label: 'Events', icon: Zap },
  { id: 'combat', label: 'Combat', icon: Swords },
  { id: 'quotes', label: 'Quotes', icon: MessageCircle },
  { id: 'characters', label: 'Characters', icon: Users },
]

export default function GameDetail() {
  const { id } = useParams<{ id: string }>()
  const gameId = Number(id)
  const { data: game, isLoading } = useQuery({ queryKey: ['game', gameId], queryFn: () => getGame(gameId) })

  if (isLoading) return <div className="min-h-screen bg-gray-950 text-gray-400 p-8 flex items-center justify-center">Loading…</div>
  if (!game) return <div className="min-h-screen bg-gray-950 text-red-400 p-8">Campaign not found</div>

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="p-4 border-b border-gray-800">
          <Link to="/" className="flex items-center gap-2 text-gray-400 hover:text-gray-200 text-sm mb-3 transition-colors">
            <ChevronLeft size={14} /> All campaigns
          </Link>
          <div className="font-semibold text-white truncate">{game.name}</div>
          <div className="text-xs text-gray-500 mt-1 truncate">{game.world_id}</div>
        </div>
        <nav className="flex-1 p-2 overflow-y-auto">
          {TABS.map(tab => (
            <NavLink key={tab.id} gameId={gameId} {...tab} />
          ))}
        </nav>
      </aside>

      {/* Content */}
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route index element={<Navigate to="quests" replace />} />
          <Route path="quests" element={<QuestLogTab gameId={gameId} />} />
          <Route path="search" element={<SearchTab gameId={gameId} />} />
          <Route path="notes" element={<NotesTab gameId={gameId} />} />
          <Route path="entities" element={<EntitiesTab gameId={gameId} />} />
          <Route path="threads" element={<ThreadsTab gameId={gameId} />} />
          <Route path="transcripts" element={<TranscriptsTab gameId={gameId} />} />
          <Route path="loot" element={<LootTab gameId={gameId} />} />
          <Route path="decisions" element={<DecisionsTab gameId={gameId} />} />
          <Route path="events" element={<EventsTab gameId={gameId} />} />
          <Route path="combat" element={<CombatTab gameId={gameId} />} />
          <Route path="quotes" element={<QuotesTab gameId={gameId} />} />
          <Route path="characters" element={<PlayerCharactersTab gameId={gameId} />} />
        </Routes>
      </main>
    </div>
  )
}

function NavLink({ gameId, id, label, icon: Icon }: { gameId: number; id: string; label: string; icon: React.ElementType }) {
  const isActive = location.pathname.endsWith(`/games/${gameId}/${id}`) || location.pathname.includes(`/games/${gameId}/${id}`)
  return (
    <Link
      to={`/games/${gameId}/${id}`}
      className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors mb-0.5 ${
        isActive ? 'bg-purple-600 text-white font-medium' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'
      }`}
    >
      <Icon size={15} />
      {label}
    </Link>
  )
}
