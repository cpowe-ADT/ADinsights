import { useEffect, useMemo, useState } from 'react'
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from '@tanstack/react-table'

import useDashboardStore, {
  CreativePerformanceRow,
} from '../features/dashboard/store/useDashboardStore'
import { formatCurrency, formatNumber, formatPercent, formatRatio } from '../lib/format'
import { TABLE_VIEW_KEYS } from '../lib/savedViews'
import StatusMessage from './ui/StatusMessage'

import styles from './CreativeTable.module.css'

type CreativeTableViewState = {
  sorting?: SortingState
}

const DEFAULT_SORTING: SortingState = [{ id: 'spend', desc: true }]

const createDefaultSorting = (): SortingState => DEFAULT_SORTING.map((item) => ({ ...item }))

interface CreativeTableProps {
  rows: CreativePerformanceRow[]
  currency: string
}

const CreativeTable = ({ rows, currency }: CreativeTableProps) => {
  const selectedParish = useDashboardStore((state) => state.selectedParish)
  const loadView = useDashboardStore((state) => state.getSavedTableView)
  const persistView = useDashboardStore((state) => state.setSavedTableView)

  const [sorting, setSorting] = useState<SortingState>(() => {
    const stored = loadView<CreativeTableViewState>(TABLE_VIEW_KEYS.creative)
    return stored?.sorting ?? createDefaultSorting()
  })

  useEffect(() => {
    persistView(TABLE_VIEW_KEYS.creative, { sorting })
  }, [sorting, persistView])

  const columns = useMemo<ColumnDef<CreativePerformanceRow>[]>(
    () => [
      {
        accessorKey: 'thumbnail',
        header: 'Preview',
        enableSorting: false,
        cell: ({ row }) => {
          const url = row.original.thumbnailUrl
          if (url) {
            return <img src={url} alt={row.original.name} className={styles.thumb} loading="lazy" />
          }
          return (
            <div className={styles.fallback} aria-hidden="true">
              {row.original.name.slice(0, 2).toUpperCase()}
            </div>
          )
        },
      },
      {
        accessorKey: 'name',
        header: 'Creative',
        cell: ({ row }) => (
          <div className={styles.name}>
            <strong>{row.original.name}</strong>
            <span className={styles.meta}>Campaign: {row.original.campaignName}</span>
          </div>
        ),
      },
      {
        accessorKey: 'platform',
        header: 'Platform',
      },
      {
        accessorKey: 'parish',
        header: 'Parish',
      },
      {
        accessorKey: 'spend',
        header: 'Spend',
        cell: ({ getValue }) => formatCurrency(Number(getValue()), currency),
      },
      {
        accessorKey: 'impressions',
        header: 'Impressions',
        cell: ({ getValue }) => formatNumber(Number(getValue())),
      },
      {
        accessorKey: 'clicks',
        header: 'Clicks',
        cell: ({ getValue }) => formatNumber(Number(getValue())),
      },
      {
        accessorKey: 'conversions',
        header: 'Conversions',
        cell: ({ getValue }) => formatNumber(Number(getValue())),
      },
      {
        accessorKey: 'roas',
        header: 'ROAS',
        cell: ({ getValue }) => formatRatio(Number(getValue()), 2),
      },
      {
        accessorKey: 'ctr',
        header: 'CTR',
        cell: ({ getValue }) => formatPercent(Number(getValue()), 2),
      },
    ],
    [currency],
  )

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <div>
          <h3>Top creatives</h3>
          {selectedParish ? (
            <StatusMessage variant="muted">
              Showing creatives active in {selectedParish}.
            </StatusMessage>
          ) : (
            <StatusMessage variant="muted">Sort by any column to prioritise reviews.</StatusMessage>
          )}
        </div>
      </div>
      <div className={styles.tableWrapper}>
        <table className={styles.table}>
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id}>
                    {header.isPlaceholder ? null : (
                      <button
                        type="button"
                        onClick={header.column.getToggleSortingHandler()}
                        className={styles.sortButton}
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {header.column.getIsSorted() === 'asc'
                          ? ' ↑'
                          : header.column.getIsSorted() === 'desc'
                            ? ' ↓'
                            : ''}
                      </button>
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id}>
                    {flexRender(
                      cell.column.columnDef.cell ?? ((ctx) => ctx.getValue()),
                      cell.getContext(),
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length === 0 ? (
        <StatusMessage variant="muted">No creatives match the current filters.</StatusMessage>
      ) : null}
    </div>
  )
}

export default CreativeTable
