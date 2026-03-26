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

function getCreatedId(flag: AuditFlag): number | string | null {
  const payload = flag.suggested_change
  if (payload.operation !== 'create') return null

  const payloadId = payload.data?.id
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
  const payload = flag.suggested_change

  if (payload.operation === 'create') {
    if (payload._after) {
      const rows = buildRows(payload._after, 'added', '+')

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

    const createdId = getCreatedId(flag)

    return (
      <div className="mt-3 rounded-lg border border-gray-700 bg-gray-900/70 p-3">
        <p className="font-mono text-xs text-emerald-300">
          {createdId != null ? `Created record #${createdId}.` : 'Created record.'}
        </p>
      </div>
    )
  }

  if (payload.operation === 'delete') {
    const rows = buildRows(payload._before, 'removed', '-')

    return (
      <div className="mt-3 rounded-lg border border-gray-700 bg-gray-900/70 p-3 space-y-1">
        {rows.map(row => (
          <DiffRowLine key={`delete:${row.keyName}:${row.value}`} row={row} />
        ))}
      </div>
    )
  }

  if (payload.operation === 'update') {
    const allKeys = Array.from(new Set([...Object.keys(payload._before), ...Object.keys(payload._after)])).sort((a, b) =>
      a.localeCompare(b),
    )

    const changedRows: DiffRow[] = []
    const unchangedRows: DiffRow[] = []

    for (const keyName of allKeys) {
      const beforeValue = formatValue(payload._before[keyName])
      const afterValue = formatValue(payload._after[keyName])

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

  if (payload.operation === 'merge') {
    const duplicateRows = buildRows(payload._duplicate, 'removed', '-')
    const canonicalRows = buildRows(payload._canonical, 'neutral', ' ')

    return (
      <div className="mt-3 rounded-lg border border-gray-700 bg-gray-900/70 p-3 space-y-3">
        {renderRecordSection('Duplicate (to remove)', duplicateRows, 'text-red-300')}
        {renderRecordSection('Merge into', canonicalRows, 'text-gray-300')}
      </div>
    )
  }

  return null
}
