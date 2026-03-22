import { type ReactNode } from 'react'

export function TabHeader({ title, count, action }: { title: string; count?: number; action?: ReactNode }) {
  return (
    <div className="flex items-center justify-between mb-6">
      <div className="flex items-center gap-3">
        <h2 className="text-xl font-semibold text-white">{title}</h2>
        {count !== undefined && (
          <span className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded-full">{count}</span>
        )}
      </div>
      {action}
    </div>
  )
}
