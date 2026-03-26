import { useState } from 'react'
import type { AuditFlag } from '../types'

type DiffViewProps = {
  flag: AuditFlag
}

type RowTone = 'added' | 'removed' | 'neutral'

type DiffRow = {
  keyName: string
  value: string
  sigil: '+' | '-' | ' '
  tone: RowTone
}

const META_FIELDS = new Set([
  'operation',
  'id',
  'target_id',
  'table_name',
  'confidence',
  'description',
  'data',
  'changes',
  '_before',
  '_after',
  '_canonical',
  '_duplicate',
  'canonical_id',
  'duplicate_id',
])

const MAX_VALUE_LENGTH = 60
const INITIAL_UNCHANGED_ROWS = 3

function formatValue(value: unknown): string {
  if (value === null) return 'null'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') {
    return String(value)
  }

  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function truncateValue(value: string): string {
  if (value.length <= MAX_VALUE_LENGTH) return value
  return `${value.slice(0, MAX_VALUE_LENGTH - 1)}…`
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  return null
}

function nonMetaRecord(record: Record<string, unknown>): Record<string, unknown> {
  const cleaned: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(record)) {
    if (!META_FIELDS.has(key)) {
      cleaned[key] = value
    }
  }
  return cleaned
}

function buildRows(record: Record<string, unknown>, tone: RowTone, sigil: '+' | '-' | ' '): DiffRow[] {
  return Object.keys(record)
    .sort((a, b) => a.localeCompare(b))
    .map(keyName => ({
      keyName,
      value: formatValue(record[keyName]),
      sigil,
      tone,
    }))
}

function rowToneClass(tone: RowTone): string {
  if (tone === 'added') return 'text-emerald-300'
  if (tone === 'removed') return 'text-red-300'
  return 'text-gray-400'
}

function DiffRowLine({ row }: { row: DiffRow }) {
  const displayValue = truncateValue(row.value)

  return (
    <div className={`grid grid-cols-[1.25rem,minmax(8rem,12rem),minmax(0,1fr)] gap-2 font-mono text-xs ${rowToneClass(row.tone)}`}>
      <span className="text-center select-none">{row.sigil}</span>
      <span className="truncate" title={row.keyName}>
        {row.keyName}
      </span>
      <span className="truncate" title={row.value}>
        {displayValue}
      </span>
    </div>
  )
}

function renderRecordSection(title: string, rows: DiffRow[], titleClassName: string) {
  return (
    <section className="space-y-1.5">
      <h4 className={`text-xs uppercase tracking-wide ${titleClassName}`}>{title}</h4>
      <div className="space-y-1">
        {rows.map(row => (
          <DiffRowLine key={`${title}:${row.sigil}:${row.keyName}:${row.value}`} row={row} />
        ))}
      </div>
    </section>
  )
}

function getCreatedId(flag: AuditFlag, payload: Record<string, unknown>): number | string | null {
  const data = asRecord(payload.data)
  const after = asRecord(payload._after)

  const payloadId = data?.id ?? after?.id
  if (typeof payloadId === 'number' || typeof payloadId === 'string') {
    return payloadId
  }

  if (flag.target_id != null) {
    return flag.target_id
  }

  return null
}

export default function DiffView({ flag }: DiffViewProps) {
  const [showAllUnchangedRows, setShowAllUnchangedRows] = useState(false)
  const payload = asRecord(flag.suggested_change) ?? {}
  const operation = flag.operation

  if (operation === 'create') {
    const afterSnapshot = asRecord(payload._after)
    if (afterSnapshot) {
      const rows = buildRows(afterSnapshot, 'added', '+')

      return (
        <div className="mt-3 rounded-lg border border-gray-700 bg-gray-900/70 p-3 space-y-1">
          {rows.length > 0 ? (
            rows.map(row => <DiffRowLine key={`create:${row.keyName}:${row.value}`} row={row} />)
          ) : (
            <p className="font-mono text-xs text-gray-400">Record will be created.</p>
          )}
        </div>
      )
    }

    const proposedData = asRecord(payload.data)
    if (proposedData && Object.keys(proposedData).length > 0) {
      const rows = buildRows(proposedData, 'added', '+')
      return (
        <div className="mt-3 rounded-lg border border-gray-700 bg-gray-900/70 p-3 space-y-1">
          {rows.map(row => (
            <DiffRowLine key={`create:data:${row.keyName}:${row.value}`} row={row} />
          ))}
        </div>
      )
    }

    const createdId = getCreatedId(flag, payload)

    return (
      <div className="mt-3 rounded-lg border border-gray-700 bg-gray-900/70 p-3">
        <p className="font-mono text-xs text-emerald-300">
          {createdId != null ? `Created record #${createdId}.` : 'Created record.'}
        </p>
      </div>
    )
  }

  if (operation === 'delete') {
    const beforeSnapshot = asRecord(payload._before)
    const candidate = beforeSnapshot ?? nonMetaRecord(payload)
    const rows = Object.keys(candidate).length > 0 ? buildRows(candidate, 'removed', '-') : []

    return (
      <div className="mt-3 rounded-lg border border-gray-700 bg-gray-900/70 p-3 space-y-1">
        {rows.length > 0 ? (
          rows.map(row => <DiffRowLine key={`delete:${row.keyName}:${row.value}`} row={row} />)
        ) : (
          <p className="font-mono text-xs text-gray-400">Record will be deleted.</p>
        )}
      </div>
    )
  }

  if (operation === 'update') {
    const beforeSnapshot = asRecord(payload._before)
    const afterSnapshot = asRecord(payload._after)

    if (!beforeSnapshot || !afterSnapshot) {
      const proposedChanges = asRecord(payload.changes)
      if (proposedChanges && Object.keys(proposedChanges).length > 0) {
        const rows = buildRows(proposedChanges, 'added', '+')
        return (
          <div className="mt-3 rounded-lg border border-gray-700 bg-gray-900/70 p-3 space-y-1">
            {rows.map(row => (
              <DiffRowLine key={`update:fallback:${row.keyName}:${row.value}`} row={row} />
            ))}
          </div>
        )
      }

      return (
        <div className="mt-3 rounded-lg border border-gray-700 bg-gray-900/70 p-3">
          <p className="font-mono text-xs text-gray-400">No field-level diff available for this update.</p>
        </div>
      )
    }

    const allKeys = Array.from(new Set([...Object.keys(beforeSnapshot), ...Object.keys(afterSnapshot)])).sort((a, b) =>
      a.localeCompare(b),
    )

    const changedRows: DiffRow[] = []
    const unchangedRows: DiffRow[] = []

    for (const keyName of allKeys) {
      const beforeValue = formatValue(beforeSnapshot[keyName])
      const afterValue = formatValue(afterSnapshot[keyName])

      if (beforeValue !== afterValue) {
        changedRows.push({ keyName, value: beforeValue, sigil: '-', tone: 'removed' })
        changedRows.push({ keyName, value: afterValue, sigil: '+', tone: 'added' })
      } else {
        unchangedRows.push({ keyName, value: beforeValue, sigil: ' ', tone: 'neutral' })
      }
    }

    const collapsedRows = unchangedRows.slice(0, INITIAL_UNCHANGED_ROWS)
    const hiddenRowCount = Math.max(0, unchangedRows.length - INITIAL_UNCHANGED_ROWS)
    const rowsToRender = showAllUnchangedRows ? unchangedRows : collapsedRows

    return (
      <div className="mt-3 rounded-lg border border-gray-700 bg-gray-900/70 p-3 space-y-2">
        {flag.status === 'applied' && (
          <p className="font-mono text-[11px] text-amber-300">snapshot as of {flag.created_at}</p>
        )}

        <div className="space-y-1">
          {changedRows.map(row => (
            <DiffRowLine key={`update:changed:${row.sigil}:${row.keyName}:${row.value}`} row={row} />
          ))}
          {rowsToRender.map(row => (
            <DiffRowLine key={`update:unchanged:${row.keyName}:${row.value}`} row={row} />
          ))}
        </div>

        {hiddenRowCount > 0 && (
          <button
            type="button"
            onClick={() => setShowAllUnchangedRows(prev => !prev)}
            className="text-xs text-gray-400 hover:text-gray-200"
          >
            {showAllUnchangedRows ? 'Collapse unchanged rows' : `Show ${hiddenRowCount} more unchanged rows`}
          </button>
        )}
      </div>
    )
  }

  if (operation === 'merge') {
    const duplicateSnapshot = asRecord(payload._duplicate)
    const canonicalSnapshot = asRecord(payload._canonical)

    if (!duplicateSnapshot || !canonicalSnapshot) {
      const fallbackRowsPayload: Record<string, unknown> = {}
      const canonicalId = payload.canonical_id
      const duplicateId = payload.duplicate_id

      if (typeof canonicalId === 'number' || typeof canonicalId === 'string') {
        fallbackRowsPayload.canonical_id = canonicalId
      }
      if (typeof duplicateId === 'number' || typeof duplicateId === 'string') {
        fallbackRowsPayload.duplicate_id = duplicateId
      }

      const fallbackRows = buildRows(fallbackRowsPayload, 'neutral', ' ')
      return (
        <div className="mt-3 rounded-lg border border-gray-700 bg-gray-900/70 p-3 space-y-1">
          {fallbackRows.length > 0 ? (
            fallbackRows.map(row => <DiffRowLine key={`merge:fallback:${row.keyName}:${row.value}`} row={row} />)
          ) : (
            <p className="font-mono text-xs text-gray-400">Merge details unavailable for this flag.</p>
          )}
        </div>
      )
    }

    const duplicateRows = buildRows(duplicateSnapshot, 'removed', '-')
    const canonicalRows = buildRows(canonicalSnapshot, 'neutral', ' ')

    return (
      <div className="mt-3 rounded-lg border border-gray-700 bg-gray-900/70 p-3 space-y-3">
        {renderRecordSection('Duplicate (to remove)', duplicateRows, 'text-red-300')}
        {renderRecordSection('Merge into', canonicalRows, 'text-gray-300')}
      </div>
    )
  }

  return null
}
