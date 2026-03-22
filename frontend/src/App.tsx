import { Route, Routes } from 'react-router-dom'
import GameDetail from './pages/GameDetail'
import GameList from './pages/GameList'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<GameList />} />
      <Route path="/games/:id/*" element={<GameDetail />} />
    </Routes>
  )
}

