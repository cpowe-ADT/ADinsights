import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
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
import { createDefaultFilterState, serializeFilterQueryParams } from '../lib/dashboardFilters';
import { TABLE_VIEW_KEYS } from '../lib/savedViews';
import DashboardState from './DashboardState';
import FilterStatus from './FilterStatus';
import Skeleton from './Skeleton';
import useVirtualRows from './useVirtualRows';

type CampaignTableViewState = {
  sorting?: SortingState;
  columnPinning?: ColumnPinningState;
};

const DEFAULT_SORTING: SortingState = [{ id: 'spend', desc: true }];
const DEFAULT_COLUMN_PINNING: ColumnPinningState = { left: ['name'] };
const VIRTUALIZATION_ROW_HEIGHT = 68;
const VIRTUALIZATION_THRESHOLD = 60;

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
  virtualizeRows?: boolean;
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

const classNames = (...values: Array<string | false | null | undefined>) =>
  values.filter(Boolean).join(' ');

const renderTruncatedText = (value: string | null | undefined) => {
  const text = value ? String(value) : '—';
  return (
    <span className="dashboard-table__truncate" title={value ? String(value) : undefined}>
      {text}
    </span>
  );
};

const CampaignTable = ({
  rows,
  currency,
  isLoading = false,
  onReload,
  virtualizeRows = true,
}: CampaignTableProps) => {
  const selectedParish = useDashboardStore((state) => state.selectedParish);
  const filters = useDashboardStore((state) => state.filters);
  const setSelectedParish = useDashboardStore((state) => state.setSelectedParish);
  const setFilters = useDashboardStore((state) => state.setFilters);
  const loadView = useDashboardStore((state) => state.getSavedTableView);
  const persistView = useDashboardStore((state) => state.setSavedTableView);
  const location = useLocation();

  const filterSearch = useMemo(() => {
    const serialized = serializeFilterQueryParams(filters);
    return serialized ? `?${serialized}` : '';
  }, [filters]);

  const hasActiveFilters = useMemo(() => {
    return (
      serializeFilterQueryParams(filters) !== serializeFilterQueryParams(createDefaultFilterState())
    );
  }, [filters]);

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
                to={`/dashboards/campaigns/${encodeURIComponent(row.original.id)}${filterSearch}`}
                state={{ from: `${location.pathname}${location.search}` }}
                className="table-link dashboard-table__truncate"
                title={row.original.name}
              >
                {row.original.name}
              </Link>
            </strong>
            <span
              className="campaign-meta dashboard-table__truncate"
              title={row.original.status ?? undefined}
            >
              {row.original.status ?? '—'}
            </span>
          </div>
        ),
      },
      {
        accessorKey: 'platform',
        header: 'Platform',
        cell: ({ getValue }) => renderTruncatedText(getValue() as string | undefined),
      },
      {
        accessorKey: 'parish',
        header: 'Parish',
        cell: ({ getValue }) => renderTruncatedText(getValue() as string | undefined),
      },
      {
        accessorKey: 'spend',
        header: 'Spend',
        meta: { isNumeric: true },
        cell: ({ getValue }) => formatCurrency(Number(getValue()), currency),
      },
      {
        accessorKey: 'impressions',
        header: 'Impressions',
        meta: { isNumeric: true },
        cell: ({ getValue }) => formatNumber(Number(getValue())),
      },
      {
        accessorKey: 'clicks',
        header: 'Clicks',
        meta: { isNumeric: true },
        cell: ({ getValue }) => formatNumber(Number(getValue())),
      },
      {
        accessorKey: 'conversions',
        header: 'Conversions',
        meta: { isNumeric: true },
        cell: ({ getValue }) => formatNumber(Number(getValue())),
      },
      {
        accessorKey: 'roas',
        header: 'ROAS',
        meta: { isNumeric: true },
        cell: ({ getValue }) => formatRatio(Number(getValue()), 2),
      },
      {
        accessorKey: 'ctr',
        header: 'CTR',
        meta: { isNumeric: true },
        cell: ({ getValue }) => formatPercent(Number(getValue()), 2),
      },
      {
        accessorKey: 'cpc',
        header: 'CPC',
        meta: { isNumeric: true },
        cell: ({ getValue }) => formatCurrency(Number(getValue()), currency, 2),
      },
      {
        accessorKey: 'cpm',
        header: 'CPM',
        meta: { isNumeric: true },
        cell: ({ getValue }) => formatCurrency(Number(getValue()), currency, 2),
      },
    ],
    [currency, filterSearch, location.pathname, location.search],
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
  const tableRows = table.getRowModel().rows;
  const rowCount = tableRows.length;
  const shouldVirtualize = virtualizeRows && rowCount > VIRTUALIZATION_THRESHOLD;
  const { containerRef, startIndex, endIndex, paddingTop, paddingBottom, isVirtualized } =
    useVirtualRows({
      enabled: shouldVirtualize,
      rowCount,
      rowHeight: VIRTUALIZATION_ROW_HEIGHT,
    });
  const visibleRows = isVirtualized ? tableRows.slice(startIndex, endIndex) : tableRows;
  const columnCount = table.getVisibleLeafColumns().length;

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

  if (isLoading && rowCount === 0) {
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

  const clearFilters = () => {
    if (selectedParish) {
      setSelectedParish(undefined);
    }
    if (hasActiveFilters) {
      setFilters(createDefaultFilterState());
    }
  };
  const emptyAction = () => {
    if (selectedParish || hasActiveFilters) {
      clearFilters();
    } else {
      onReload?.();
    }
  };
  const emptyVariant = selectedParish || hasActiveFilters ? 'no-results' : 'empty';
  const emptyTitle = selectedParish
    ? `No campaigns in ${selectedParish}`
    : hasActiveFilters
      ? 'No campaigns match these filters'
      : 'No campaign rows yet';
  const emptyMessage = selectedParish
    ? 'Try clearing the parish filter to see all campaigns.'
    : hasActiveFilters
      ? 'Try widening the date range or clearing filters.'
      : 'Campaign rows will appear after your next sync finishes.';
  const emptyActionLabel =
    selectedParish || hasActiveFilters ? 'Clear filters' : onReload ? 'Refresh data' : undefined;

  const emptyState = (
    <DashboardState
      variant={emptyVariant}
      icon={<TablePlaceholderIcon />}
      title={emptyTitle}
      message={emptyMessage}
      actionLabel={emptyActionLabel}
      onAction={emptyActionLabel ? emptyAction : undefined}
      layout="compact"
    />
  );

  return (
    <div className="table-card" aria-busy={isLoading}>
      <div className="table-card__header">
        <div>
          <div className="table-card__title-row">
            <h3>Performance breakdown</h3>
            <FilterStatus />
          </div>
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
          disabled={rowCount === 0 || isLoading}
        >
          Export CSV
        </button>
      </div>
      {rowCount > 0 ? (
        <div className="table-responsive dashboard-table__scroll" ref={containerRef}>
          <table className="dashboard-table">
            <thead>
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id} className="dashboard-table__header-row">
                  {headerGroup.headers.map((header) => (
                    <th
                      key={header.id}
                      colSpan={header.colSpan}
                      className={classNames(
                        'dashboard-table__header-cell',
                        header.column.getIsPinned() && 'pinned',
                        (header.column.columnDef.meta as { isNumeric?: boolean } | undefined)
                          ?.isNumeric
                          ? 'dashboard-table__cell--numeric'
                          : undefined,
                      )}
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
              {isVirtualized && paddingTop > 0 ? (
                <tr className="dashboard-table__spacer" aria-hidden="true">
                  <td colSpan={columnCount} style={{ height: paddingTop }} />
                </tr>
              ) : null}
              {visibleRows.map((row, visibleIndex) => {
                const rowPosition = startIndex + visibleIndex;
                const isZebra = rowPosition % 2 === 1;
                return (
                  <tr
                    key={row.id}
                    className={classNames(
                      'dashboard-table__row',
                      isZebra && 'dashboard-table__row--zebra',
                    )}
                  >
                    {row.getVisibleCells().map((cell) => {
                      const isNumeric = (
                        cell.column.columnDef.meta as { isNumeric?: boolean } | undefined
                      )?.isNumeric;
                      return (
                        <td
                          key={cell.id}
                          className={classNames(
                            'dashboard-table__cell',
                            cell.column.getIsPinned() && 'pinned',
                            isNumeric ? 'dashboard-table__cell--numeric' : undefined,
                          )}
                        >
                          {flexRender(
                            cell.column.columnDef.cell ?? ((ctx) => ctx.getValue()),
                            cell.getContext(),
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
              {isVirtualized && paddingBottom > 0 ? (
                <tr className="dashboard-table__spacer" aria-hidden="true">
                  <td colSpan={columnCount} style={{ height: paddingBottom }} />
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      ) : (
        emptyState
      )}
    </div>
  );
};

export default CampaignTable;
