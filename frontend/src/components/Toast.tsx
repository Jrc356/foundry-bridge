import { useEffect } from 'react'

interface ToastAction {
  label: string
  onClick: () => void
}

interface ToastProps {
  open: boolean
  message: string
  action?: ToastAction
  onClose: () => void
  durationMs?: number
}

export default function Toast({ open, message, action, onClose, durationMs = 5000 }: ToastProps) {
  useEffect(() => {
    if (!open) return

    const timer = window.setTimeout(onClose, durationMs)
    return () => window.clearTimeout(timer)
  }, [open, onClose, durationMs])

  if (!open) return null

  return (
    <div className="fixed bottom-4 left-4 right-4 z-50 sm:left-auto sm:right-6 sm:w-[26rem]">
      <div className="bg-gray-900 border border-gray-700 rounded-xl shadow-xl px-4 py-3 flex items-start gap-3">
        <p className="text-sm text-gray-200 leading-relaxed flex-1">{message}</p>
        <div className="flex items-center gap-2 shrink-0">
          {action && (
            <button
              onClick={action.onClick}
              className="text-xs font-semibold text-purple-300 hover:text-purple-200 bg-purple-900/50 border border-purple-700 px-2.5 py-1 rounded-md transition-colors"
            >
              {action.label}
            </button>
          )}
          <button
            onClick={onClose}
            className="text-xs text-gray-400 hover:text-gray-200 px-1 py-0.5 transition-colors"
            aria-label="Dismiss toast"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
