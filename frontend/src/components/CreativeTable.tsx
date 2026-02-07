import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from '@tanstack/react-table';

import useDashboardStore, { CreativePerformanceRow } from '../state/useDashboardStore';
import { formatCurrency, formatNumber, formatPercent, formatRatio } from '../lib/format';
import { createDefaultFilterState, serializeFilterQueryParams } from '../lib/dashboardFilters';
import { TABLE_VIEW_KEYS } from '../lib/savedViews';
import DashboardState from './DashboardState';
import FilterStatus from './FilterStatus';
import useVirtualRows from './useVirtualRows';

type CreativeTableViewState = {
  sorting?: SortingState;
};

const DEFAULT_SORTING: SortingState = [{ id: 'spend', desc: true }];
const VIRTUALIZATION_ROW_HEIGHT = 68;
const VIRTUALIZATION_THRESHOLD = 60;

const createDefaultSorting = (): SortingState => DEFAULT_SORTING.map((item) => ({ ...item }));

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

interface CreativeTableProps {
  rows: CreativePerformanceRow[];
  currency: string;
  virtualizeRows?: boolean;
}

const CreativeTable = ({
  rows,
  currency,
  virtualizeRows = true,
}: CreativeTableProps) => {
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
    return serializeFilterQueryParams(filters) !== serializeFilterQueryParams(createDefaultFilterState());
  }, [filters]);

  const [sorting, setSorting] = useState<SortingState>(() => {
    const stored = loadView<CreativeTableViewState>(TABLE_VIEW_KEYS.creative);
    return stored?.sorting ?? createDefaultSorting();
  });

  useEffect(() => {
    persistView(TABLE_VIEW_KEYS.creative, { sorting });
  }, [sorting, persistView]);

  const columns = useMemo<ColumnDef<CreativePerformanceRow>[]>(
    () => [
      {
        accessorKey: 'thumbnail',
        header: 'Preview',
        enableSorting: false,
        cell: ({ row }) => {
          const url = row.original.thumbnailUrl;
          if (url) {
            return (
              <img src={url} alt={row.original.name} className="creative-thumb" loading="lazy" />
            );
          }
          return (
            <div className="creative-fallback" aria-hidden="true">
              {row.original.name.slice(0, 2).toUpperCase()}
            </div>
          );
        },
      },
      {
        accessorKey: 'name',
        header: 'Creative',
        cell: ({ row }) => (
          <div className="creative-name">
            <strong>
              <Link
                to={`/dashboards/creatives/${encodeURIComponent(row.original.id)}${filterSearch}`}
                state={{ from: `${location.pathname}${location.search}` }}
                className="table-link dashboard-table__truncate"
                title={row.original.name}
              >
                {row.original.name}
              </Link>
            </strong>
            <span className="creative-meta">
              Campaign:{' '}
              <Link
                to={`/dashboards/campaigns/${encodeURIComponent(row.original.campaignId)}${filterSearch}`}
                state={{ from: `${location.pathname}${location.search}` }}
                className="table-link dashboard-table__truncate"
                title={row.original.campaignName}
              >
                {row.original.campaignName}
              </Link>
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
    ],
    [currency, filterSearch, location.pathname, location.search],
  );

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
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

  return (
    <div className="table-card">
      <div className="table-card__header">
        <div>
          <div className="table-card__title-row">
            <h3>Top creatives</h3>
            <FilterStatus />
          </div>
          {selectedParish ? (
            <p className="status-message muted">Showing creatives active in {selectedParish}.</p>
          ) : (
            <p className="status-message muted">Sort by any column to prioritise reviews.</p>
          )}
        </div>
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
        <DashboardState
          variant={hasActiveFilters || selectedParish ? 'no-results' : 'empty'}
          title={hasActiveFilters || selectedParish ? 'No creatives match these filters' : undefined}
          message={
            hasActiveFilters || selectedParish
              ? 'Try clearing filters or widening the date range.'
              : 'Creatives will appear once ads have spend.'
          }
          actionLabel={hasActiveFilters || selectedParish ? 'Clear filters' : undefined}
          onAction={
            hasActiveFilters || selectedParish
              ? () => {
                  setSelectedParish(undefined);
                  setFilters(createDefaultFilterState());
                }
              : undefined
          }
          layout="compact"
        />
      )}
    </div>
  );
};

export default CreativeTable;
