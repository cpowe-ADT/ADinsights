import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
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
import { TABLE_VIEW_KEYS } from '../lib/savedViews';

type CreativeTableViewState = {
  sorting?: SortingState;
};

const DEFAULT_SORTING: SortingState = [{ id: 'spend', desc: true }];

const createDefaultSorting = (): SortingState => DEFAULT_SORTING.map((item) => ({ ...item }));

interface CreativeTableProps {
  rows: CreativePerformanceRow[];
  currency: string;
}

const CreativeTable = ({ rows, currency }: CreativeTableProps) => {
  const selectedParish = useDashboardStore((state) => state.selectedParish);
  const loadView = useDashboardStore((state) => state.getSavedTableView);
  const persistView = useDashboardStore((state) => state.setSavedTableView);

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
                to={`/dashboards/creatives/${encodeURIComponent(row.original.id)}`}
                className="table-link"
              >
                {row.original.name}
              </Link>
            </strong>
            <span className="creative-meta">
              Campaign:{' '}
              <Link
                to={`/dashboards/campaigns/${encodeURIComponent(row.original.campaignId)}`}
                className="table-link"
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
  );

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="table-card">
      <div className="table-card__header">
        <div>
          <h3>Top creatives</h3>
          {selectedParish ? (
            <p className="status-message muted">Showing creatives active in {selectedParish}.</p>
          ) : (
            <p className="status-message muted">Sort by any column to prioritise reviews.</p>
          )}
        </div>
      </div>
      <div className="table-responsive">
        <table>
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
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
        <p className="status-message muted">No creatives match the current filters.</p>
      ) : null}
    </div>
  );
};

export default CreativeTable;
