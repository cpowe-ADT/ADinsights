import { useMemo, useState } from "react";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from "@tanstack/react-table";

import useDashboardStore, { CreativePerformanceRow } from "../state/useDashboardStore";
import { formatCurrency, formatNumber, formatPercent, formatRatio } from "../lib/format";

interface CreativeTableProps {
  rows: CreativePerformanceRow[];
  currency: string;
}

const CreativeTable = ({ rows, currency }: CreativeTableProps) => {
  const { selectedParish } = useDashboardStore((state) => ({
    selectedParish: state.selectedParish,
  }));

  const [sorting, setSorting] = useState<SortingState>([{ id: "spend", desc: true }]);

  const filteredRows = useMemo(() => {
    if (!selectedParish) {
      return rows;
    }
    return rows.filter((row) => row.parish?.toLowerCase() === selectedParish.toLowerCase());
  }, [rows, selectedParish]);

  const columns = useMemo<ColumnDef<CreativePerformanceRow>[]>(
    () => [
      {
        accessorKey: "thumbnail",
        header: "Preview",
        enableSorting: false,
        cell: ({ row }) => {
          const url = row.original.thumbnailUrl;
          if (url) {
            return <img src={url} alt={row.original.name} className="creative-thumb" loading="lazy" />;
          }
          return (
            <div className="creative-fallback" aria-hidden="true">
              {row.original.name.slice(0, 2).toUpperCase()}
            </div>
          );
        },
      },
      {
        accessorKey: "name",
        header: "Creative",
        cell: ({ row }) => (
          <div className="creative-name">
            <strong>{row.original.name}</strong>
            <span className="creative-meta">Campaign: {row.original.campaignName}</span>
          </div>
        ),
      },
      {
        accessorKey: "platform",
        header: "Platform",
      },
      {
        accessorKey: "parish",
        header: "Parish",
      },
      {
        accessorKey: "spend",
        header: "Spend",
        cell: ({ getValue }) => formatCurrency(Number(getValue()), currency),
      },
      {
        accessorKey: "impressions",
        header: "Impressions",
        cell: ({ getValue }) => formatNumber(Number(getValue())),
      },
      {
        accessorKey: "clicks",
        header: "Clicks",
        cell: ({ getValue }) => formatNumber(Number(getValue())),
      },
      {
        accessorKey: "conversions",
        header: "Conversions",
        cell: ({ getValue }) => formatNumber(Number(getValue())),
      },
      {
        accessorKey: "roas",
        header: "ROAS",
        cell: ({ getValue }) => formatRatio(Number(getValue()), 2),
      },
      {
        accessorKey: "ctr",
        header: "CTR",
        cell: ({ getValue }) => formatPercent(Number(getValue()), 2),
      },
    ],
    [currency]
  );

  const table = useReactTable({
    data: filteredRows,
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
                  <th key={header.id}>
                    {header.isPlaceholder ? null : (
                      <button
                        type="button"
                        onClick={header.column.getToggleSortingHandler()}
                        className="sort-button"
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {header.column.getIsSorted() === "asc"
                          ? " ↑"
                          : header.column.getIsSorted() === "desc"
                          ? " ↓"
                          : ""}
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
                  <td key={cell.id}>{flexRender(cell.column.columnDef.cell ?? ((ctx) => ctx.getValue()), cell.getContext())}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {filteredRows.length === 0 ? (
        <p className="status-message muted">No creatives match the current filters.</p>
      ) : null}
    </div>
  );
};

export default CreativeTable;
