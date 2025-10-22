import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ColumnDef,
  ColumnPinningState,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from '@tanstack/react-table';

import useDashboardStore, { CampaignPerformanceRow } from '../state/useDashboardStore';
import { formatCurrency, formatNumber, formatPercent, formatRatio } from '../lib/format';
import { TABLE_VIEW_KEYS } from '../lib/savedViews';
import EmptyState from './EmptyState';
import Skeleton from './Skeleton';

type CampaignTableViewState = {
  sorting?: SortingState;
  columnPinning?: ColumnPinningState;
};

const DEFAULT_SORTING: SortingState = [{ id: 'spend', desc: true }];
const DEFAULT_COLUMN_PINNING: ColumnPinningState = { left: ['name'] };

const createDefaultSorting = (): SortingState => DEFAULT_SORTING.map((item) => ({ ...item }));
const createDefaultColumnPinning = (): ColumnPinningState => ({
  left: DEFAULT_COLUMN_PINNING.left ? [...DEFAULT_COLUMN_PINNING.left] : undefined,
  right: DEFAULT_COLUMN_PINNING.right ? [...DEFAULT_COLUMN_PINNING.right] : undefined,
});

interface CampaignTableProps {
  rows: CampaignPerformanceRow[];
  currency: string;
  isLoading?: boolean;
  onReload?: () => void;
}

const TablePlaceholderIcon = () => (
  <svg
    width="48"
    height="48"
    viewBox="0 0 48 48"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.2"
  >
    <rect x="8" y="12" width="32" height="24" rx="3.5" />
    <path d="M8 20h32M18 12v24" strokeLinecap="round" />
  </svg>
);

const headers = [
  'Campaign',
  'Platform',
  'Parish',
  'Spend',
  'Impressions',
  'Clicks',
  'Conversions',
  'ROAS',
  'CTR',
  'CPC',
  'CPM',
];

const CampaignTable = ({ rows, currency, isLoading = false, onReload }: CampaignTableProps) => {
  const selectedParish = useDashboardStore((state) => state.selectedParish);
  const setSelectedParish = useDashboardStore((state) => state.setSelectedParish);
  const loadView = useDashboardStore((state) => state.getSavedTableView);
  const persistView = useDashboardStore((state) => state.setSavedTableView);

  const [sorting, setSorting] = useState<SortingState>(() => {
    const stored = loadView<CampaignTableViewState>(TABLE_VIEW_KEYS.campaign);
    return stored?.sorting ?? createDefaultSorting();
  });
  const [columnPinning, setColumnPinning] = useState<ColumnPinningState>(() => {
    const stored = loadView<CampaignTableViewState>(TABLE_VIEW_KEYS.campaign);
    return stored?.columnPinning ?? createDefaultColumnPinning();
  });

  useEffect(() => {
    persistView(TABLE_VIEW_KEYS.campaign, { sorting, columnPinning });
  }, [sorting, columnPinning, persistView]);

  const columns = useMemo<ColumnDef<CampaignPerformanceRow>[]>(
    () => [
      {
        accessorKey: 'name',
        header: 'Campaign',
        enablePinning: true,
        cell: ({ row }) => (
          <div className="campaign-name">
            <strong>
              <Link
                to={`/dashboards/campaigns/${encodeURIComponent(row.original.id)}`}
                className="table-link"
              >
                {row.original.name}
              </Link>
            </strong>
            <span className="campaign-meta">{row.original.status}</span>
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
      {
        accessorKey: 'cpc',
        header: 'CPC',
        cell: ({ getValue }) => formatCurrency(Number(getValue()), currency, 2),
      },
      {
        accessorKey: 'cpm',
        header: 'CPM',
        cell: ({ getValue }) => formatCurrency(Number(getValue()), currency, 2),
      },
    ],
    [currency],
  );

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting, columnPinning },
    onSortingChange: setSorting,
    onColumnPinningChange: setColumnPinning,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const handleExport = () => {
    if (typeof window === 'undefined') {
      return;
    }

    const csvRows = table
      .getRowModel()
      .rows.map((row) => [
        row.original.name,
        row.original.platform,
        row.original.parish ?? '—',
        formatCurrency(row.original.spend, currency),
        formatNumber(row.original.impressions),
        formatNumber(row.original.clicks),
        formatNumber(row.original.conversions),
        formatRatio(row.original.roas, 2),
        formatPercent(row.original.ctr ?? 0, 2),
        formatCurrency(row.original.cpc ?? 0, currency, 2),
        formatCurrency(row.original.cpm ?? 0, currency, 2),
      ]);

    const csvContent = [headers, ...csvRows]
      .map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(','))
      .join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `campaign-performance-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  if (isLoading && rows.length === 0) {
    return (
      <div className="table-card" aria-busy="true">
        <div className="table-card__header">
          <div>
            <Skeleton width="200px" height="1.1rem" />
            <Skeleton width="260px" height="0.85rem" />
          </div>
          <Skeleton width="140px" height="2.5rem" borderRadius="0.9rem" />
        </div>
        <div className="table-skeleton">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={`table-row-skeleton-${index}`} height="2.4rem" borderRadius="0.6rem" />
          ))}
        </div>
      </div>
    );
  }

  const emptyState = (
    <EmptyState
      icon={<TablePlaceholderIcon />}
      title={selectedParish ? `No campaigns in ${selectedParish}` : 'No campaign rows yet'}
      message={
        selectedParish
          ? 'Try clearing the parish filter to see all campaigns.'
          : 'Campaign rows will appear after your next sync finishes.'
      }
      actionLabel={selectedParish ? 'Clear filter' : 'Refresh data'}
      onAction={() => {
        if (selectedParish) {
          setSelectedParish(undefined);
        } else {
          onReload?.();
        }
      }}
      actionVariant={selectedParish ? 'tertiary' : 'secondary'}
    />
  );

  return (
    <div className="table-card" aria-busy={isLoading}>
      <div className="table-card__header">
        <div>
          <h3>Performance breakdown</h3>
          {selectedParish ? (
            <p className="status-message muted">
              Filtering to <strong>{selectedParish}</strong>
              <button
                type="button"
                onClick={() => setSelectedParish(undefined)}
                className="link-button"
              >
                Clear
              </button>
            </p>
          ) : (
            <p className="status-message muted">Click a parish to focus the table.</p>
          )}
        </div>
        <button
          type="button"
          onClick={handleExport}
          className="button secondary"
          disabled={rows.length === 0 || isLoading}
        >
          Export CSV
        </button>
      </div>
      {rows.length > 0 ? (
        <div className="table-responsive">
          <table>
            <thead>
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <th
                      key={header.id}
                      colSpan={header.colSpan}
                      className={header.column.getIsPinned() ? 'pinned' : undefined}
                    >
                      {header.isPlaceholder ? null : (
                        <button
                          type="button"
                          onClick={header.column.getToggleSortingHandler()}
                          className="sort-button"
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
                    <td key={cell.id} className={cell.column.getIsPinned() ? 'pinned' : undefined}>
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
      ) : (
        emptyState
      )}
      <div className="table-responsive">
        <table>
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    colSpan={header.colSpan}
                    className={header.column.getIsPinned() ? 'pinned' : undefined}
                    scope={header.colSpan === 1 ? 'col' : undefined}
                    aria-sort={
                      header.column.getCanSort()
                        ? header.column.getIsSorted() === 'desc'
                          ? 'descending'
                          : header.column.getIsSorted() === 'asc'
                            ? 'ascending'
                            : 'none'
                        : undefined
                    }
                  >
                    {header.isPlaceholder ? null : header.column.getCanSort() ? (
                      <button
                        type="button"
                        onClick={header.column.getToggleSortingHandler()}
                        className="sort-button"
                        aria-label={`Sort by ${
                          typeof header.column.columnDef.header === 'string'
                            ? header.column.columnDef.header
                            : header.column.id
                        }. Currently ${
                          header.column.getIsSorted() === 'desc'
                            ? 'sorted descending'
                            : header.column.getIsSorted() === 'asc'
                              ? 'sorted ascending'
                              : 'not sorted'
                        }.`}
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {header.column.getIsSorted() === 'asc'
                          ? ' ↑'
                          : header.column.getIsSorted() === 'desc'
                            ? ' ↓'
                            : ''}
                      </button>
                    ) : (
                      flexRender(header.column.columnDef.header, header.getContext())
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
                  <td key={cell.id} className={cell.column.getIsPinned() ? 'pinned' : undefined}>
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
        <p className="status-message muted">No campaigns match the selected filters.</p>
      ) : null}
    </div>
  );
};

export default CampaignTable;
