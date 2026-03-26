import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { Check, Loader2, RotateCcw, X, Zap } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  applyAuditFlag,
  dismissAuditFlag,
  getAuditFlags,
  getAuditRuns,
  reopenAuditFlag,
  triggerAudit,
} from '../../api'
import DiffView from '../../components/DiffView'
import Toast from '../../components/Toast'
import { TabHeader } from '../../components/TabHeader'
import type { AuditFlag, AuditFlagMutation, AuditRun, FlagStatus } from '../../types'
import { sortByCreatedAtDesc } from '../../utils/datetime'

const PAGE_SIZE = 50

type AuditFilter = 'all' | FlagStatus

type ToastState = {
  message: string
  undoFlagId: number
  key: number
}

const STATUS_BADGE: Record<FlagStatus, string> = {
  pending: 'bg-amber-900 text-amber-200 border border-amber-700',
  applied: 'bg-emerald-900 text-emerald-200 border border-emerald-700',
  dismissed: 'bg-gray-700 text-gray-300 border border-gray-600',
}

const CONFIDENCE_BADGE: Record<AuditFlag['confidence'], string> = {
  high: 'bg-emerald-900 text-emerald-200',
  medium: 'bg-yellow-900 text-yellow-200',
  low: 'bg-red-900 text-red-200',
}

function toFilterStatus(filter: AuditFilter): FlagStatus | undefined {
  return filter === 'all' ? undefined : filter
}

function formatErrorMessage(error: unknown, fallback: string): string {
  if (isAxiosError(error)) {
    const payload = error.response?.data as { message?: string; detail?: string } | undefined
    if (payload?.message) return payload.message
    if (typeof payload?.detail === 'string') return payload.detail
  }
  return fallback
}

function getDisplayStatus(flag: AuditFlag, optimisticStatus: Record<number, FlagStatus>): FlagStatus {
  return optimisticStatus[flag.id] ?? flag.status
}

function formatRunStatus(status: AuditRun['status']): string {
  return status[0].toUpperCase() + status.slice(1)
}

function invalidateDomainQueries(queryClient: ReturnType<typeof useQueryClient>, gameId: number) {
  const keys = [
    'game',
    'quests',
    'search',
    'notes',
    'entities',
    'threads',
    'transcripts',
    'loot',
    'decisions',
    'events',
    'combat',
    'quotes',
    'characters',
    'noteEvents',
    'noteLoot',
  ]

  for (const key of keys) {
    queryClient.invalidateQueries({ queryKey: [key, gameId] })
  }
}

export default function AuditTab({ gameId }: { gameId: number }) {
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<AuditFilter>('all')
  const [optimisticStatus, setOptimisticStatus] = useState<Record<number, FlagStatus>>({})
  const [inFlightOptimistic, setInFlightOptimistic] = useState<Set<number>>(new Set())
  const [toast, setToast] = useState<ToastState | null>(null)
  const previousRunStatus = useRef<AuditRun['status'] | null>(null)
  const toastKeyRef = useRef(0)

  const auditRunsQuery = useQuery({
    queryKey: ['audit-runs', gameId],
    queryFn: () => getAuditRuns(gameId),
  })
  const { refetch: refetchAuditRuns } = auditRunsQuery

  const latestRun = auditRunsQuery.data?.[0] ?? null

  function nextToastKey(): number {
    toastKeyRef.current += 1
    return toastKeyRef.current
  }

  useEffect(() => {
    if (latestRun?.status !== 'running') return

    const timer = window.setInterval(() => {
      void refetchAuditRuns()
    }, 3000)

    return () => window.clearInterval(timer)
  }, [latestRun?.id, latestRun?.status, refetchAuditRuns])

  useEffect(() => {
    const nextStatus = latestRun?.status ?? null
    if (previousRunStatus.current === 'running' && nextStatus === 'completed') {
      invalidateDomainQueries(queryClient, gameId)
      queryClient.invalidateQueries({ queryKey: ['audit-flags', gameId] })
    }
    previousRunStatus.current = nextStatus
  }, [latestRun?.status, queryClient, gameId])

  const flagsQuery = useInfiniteQuery({
    queryKey: ['audit-flags', gameId, statusFilter],
    queryFn: ({ pageParam }) => getAuditFlags(gameId, toFilterStatus(statusFilter), pageParam, PAGE_SIZE),
    initialPageParam: 0,
    getNextPageParam: (lastPage, pages) => (lastPage.length === PAGE_SIZE ? pages.length * PAGE_SIZE : undefined),
  })

  const allFetchedFlags = useMemo(() => flagsQuery.data?.pages.flat() ?? [], [flagsQuery.data])

  const visibleFlags = useMemo(
    () =>
      sortByCreatedAtDesc(
        allFetchedFlags.filter(flag => {
          if (statusFilter === 'all') return true
          return getDisplayStatus(flag, optimisticStatus) === statusFilter
        }),
      ),
    [allFetchedFlags, optimisticStatus, statusFilter],
  )

  const triggerRunMutation = useMutation({
    mutationFn: () => triggerAudit(gameId),
    onSuccess: result => {
      const message = result.message || 'Audit run triggered.'
      setToast({ message, undoFlagId: -1, key: nextToastKey() })
      queryClient.invalidateQueries({ queryKey: ['audit-runs', gameId] })
    },
    onError: error => {
      setToast({
        message: formatErrorMessage(error, 'Unable to trigger audit run.'),
        undoFlagId: -1,
        key: nextToastKey(),
      })
    },
  })

  function handleMutateFlag(flag: AuditFlag, nextStatus: FlagStatus) {
    setInFlightOptimistic(prev => {
      const next = new Set(prev)
      next.add(flag.id)
      return next
    })
    setOptimisticStatus(prev => ({ ...prev, [flag.id]: nextStatus }))
  }

  function handleMutationError(flag: AuditFlag) {
    setInFlightOptimistic(prev => {
      const next = new Set(prev)
      next.delete(flag.id)
      return next
    })
    setOptimisticStatus(prev => {
      const next = { ...prev }
      delete next[flag.id]
      return next
    })
  }

  function handleMutationSuccess(result: AuditFlagMutation, flag: AuditFlag) {
    const message = result.message || `Audit flag ${result.status ?? 'updated'}.`
    setToast({
      message,
      undoFlagId: flag.id,
      key: nextToastKey(),
    })
  }

  const applyMutation = useMutation({
    mutationFn: (flagId: number) => applyAuditFlag(gameId, flagId),
    onSettled: (_result, _error, flagId) => {
      setInFlightOptimistic(prev => {
        const next = new Set(prev)
        next.delete(flagId)
        return next
      })
      setOptimisticStatus(prev => {
        const next = { ...prev }
        delete next[flagId]
        return next
      })
      queryClient.invalidateQueries({ queryKey: ['audit-flags', gameId] })
    },
  })

  const dismissMutation = useMutation({
    mutationFn: (flagId: number) => dismissAuditFlag(gameId, flagId),
    onSettled: (_result, _error, flagId) => {
      setInFlightOptimistic(prev => {
        const next = new Set(prev)
        next.delete(flagId)
        return next
      })
      setOptimisticStatus(prev => {
        const next = { ...prev }
        delete next[flagId]
        return next
      })
      queryClient.invalidateQueries({ queryKey: ['audit-flags', gameId] })
    },
  })

  const reopenMutation = useMutation({
    mutationFn: (flagId: number) => reopenAuditFlag(gameId, flagId),
    onSuccess: result => {
      setToast({ message: result.message || 'Flag reopened.', undoFlagId: -1, key: nextToastKey() })
    },
    onSettled: (_result, _error, flagId) => {
      setInFlightOptimistic(prev => {
        const next = new Set(prev)
        next.delete(flagId)
        return next
      })
      setOptimisticStatus(prev => {
        const next = { ...prev }
        delete next[flagId]
        return next
      })
      queryClient.invalidateQueries({ queryKey: ['audit-flags', gameId] })
    },
  })

  const pendingActionFlagId =
    (applyMutation.isPending ? applyMutation.variables : undefined) ??
    (dismissMutation.isPending ? dismissMutation.variables : undefined)

  const filterOptions: Array<{ key: AuditFilter; label: string }> = [
    { key: 'all', label: 'All' },
    { key: 'pending', label: 'Pending' },
    { key: 'applied', label: 'Applied' },
    { key: 'dismissed', label: 'Dismissed' },
  ]

  return (
    <div className="p-6 max-w-5xl">
      <TabHeader
        title="Audit Flags"
        count={visibleFlags.length}
        action={
          <button
            onClick={() => triggerRunMutation.mutate()}
            disabled={triggerRunMutation.isPending || latestRun?.status === 'running'}
            className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
          >
            {triggerRunMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
            {latestRun?.status === 'running' ? 'Audit Running…' : 'Run Audit'}
          </button>
        }
      />

      <section className="bg-gray-800 rounded-xl border border-gray-700 p-4 mb-5">
        {latestRun ? (
          <div className="flex flex-wrap items-start gap-3 text-sm">
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${latestRun.status === 'running'
              ? 'bg-blue-900 text-blue-200 border border-blue-700'
              : latestRun.status === 'completed'
                ? 'bg-emerald-900 text-emerald-200 border border-emerald-700'
                : 'bg-red-900 text-red-200 border border-red-700'
              }`}
            >
              {formatRunStatus(latestRun.status)}
            </span>
            <span className="text-gray-300">Triggered {new Date(latestRun.triggered_at).toLocaleString()}</span>
            <span className="text-gray-500">Source: {latestRun.trigger_source}</span>
            <span className="text-gray-500">Notes audited: {latestRun.notes_audited_count}</span>
          </div>
        ) : (
          <p className="text-sm text-gray-500">No audit runs yet. Trigger a run to generate review flags.</p>
        )}
      </section>

      <div className="flex gap-2 flex-wrap mb-5">
        {filterOptions.map(option => (
          <button
            key={option.key}
            onClick={() => setStatusFilter(option.key)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${statusFilter === option.key ? 'bg-purple-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {flagsQuery.isLoading ? (
        <p className="text-gray-400">Loading…</p>
      ) : flagsQuery.isError ? (
        <p className="text-sm text-red-400">Unable to load audit flags.</p>
      ) : visibleFlags.length === 0 ? (
        <p className="text-sm text-gray-500">No flags for this filter.</p>
      ) : (
        <div className="grid gap-3">
          {visibleFlags.map(flag => {
            const displayStatus = getDisplayStatus(flag, optimisticStatus)
            const isPending = pendingActionFlagId === flag.id || inFlightOptimistic.has(flag.id)
            return (
              <article key={flag.id} className="bg-gray-800 rounded-xl border border-gray-700 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-1.5">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_BADGE[displayStatus]}`}>
                        {displayStatus}
                      </span>
                      <span className="text-xs text-gray-500 uppercase tracking-wider">{`${flag.operation} ${flag.table_name}`.replaceAll('_', ' ')}</span>
                      <span
                        className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${CONFIDENCE_BADGE[flag.confidence]}`}
                      >
                        {flag.confidence === 'high' && <Zap size={11} className="shrink-0" />}
                        {flag.confidence}
                      </span>
                      {flag.target_id != null && <span className="text-xs text-gray-500">#{flag.target_id}</span>}
                    </div>
                    <p className="text-sm text-gray-200 leading-relaxed">{flag.description}</p>
                    <p className="text-xs text-gray-500 mt-2">
                      Created {new Date(flag.created_at).toLocaleString()}
                      {flag.resolved_at ? ` · Resolved ${new Date(flag.resolved_at).toLocaleString()}` : ''}
                    </p>
                  </div>

                  {displayStatus === 'pending' && (
                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        onClick={() => {
                          handleMutateFlag(flag, 'applied')
                          applyMutation.mutate(flag.id, {
                            onSuccess: result => handleMutationSuccess(result, flag),
                            onError: error => {
                              handleMutationError(flag)
                              setToast({
                                message: formatErrorMessage(error, 'Unable to apply audit flag.'),
                                undoFlagId: -1,
                                key: nextToastKey(),
                              })
                            },
                          })
                        }}
                        disabled={isPending}
                        className="inline-flex items-center gap-1 bg-emerald-700 hover:bg-emerald-600 disabled:opacity-50 text-white px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors"
                      >
                        <Check size={13} /> Apply
                      </button>
                      <button
                        onClick={() => {
                          handleMutateFlag(flag, 'dismissed')
                          dismissMutation.mutate(flag.id, {
                            onSuccess: result => handleMutationSuccess(result, flag),
                            onError: error => {
                              handleMutationError(flag)
                              setToast({
                                message: formatErrorMessage(error, 'Unable to dismiss audit flag.'),
                                undoFlagId: -1,
                                key: nextToastKey(),
                              })
                            },
                          })
                        }}
                        disabled={isPending}
                        className="inline-flex items-center gap-1 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-gray-200 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors"
                      >
                        <X size={13} /> Dismiss
                      </button>
                    </div>
                  )}
                </div>

                <DiffView flag={flag} />
              </article>
            )
          })}
        </div>
      )}

      {flagsQuery.hasNextPage && (
        <div className="mt-5">
          <button
            onClick={() => void flagsQuery.fetchNextPage()}
            disabled={flagsQuery.isFetchingNextPage}
            className="bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-gray-200 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
          >
            {flagsQuery.isFetchingNextPage ? 'Loading…' : 'Load More'}
          </button>
        </div>
      )}

      <Toast
        key={toast?.key}
        open={toast !== null}
        message={toast?.message ?? ''}
        onClose={() => setToast(null)}
        durationMs={5000}
        action={
          toast && toast.undoFlagId > 0
            ? {
              label: 'Undo',
              onClick: () => {
                setInFlightOptimistic(prev => {
                  const next = new Set(prev)
                  next.add(toast.undoFlagId)
                  return next
                })
                reopenMutation.mutate(toast.undoFlagId)
                setOptimisticStatus(prev => ({ ...prev, [toast.undoFlagId]: 'pending' }))
                setToast(null)
              },
            }
            : undefined
        }
      />
    </div>
  )
}
