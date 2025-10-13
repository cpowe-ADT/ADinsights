import { useMemo, useState } from "react";
import {
  ColumnDef,
  ColumnPinningState,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from "@tanstack/react-table";

import useDashboardStore, { CampaignPerformanceRow } from "../state/useDashboardStore";
import { formatCurrency, formatNumber, formatPercent, formatRatio } from "../lib/format";

interface CampaignTableProps {
  rows: CampaignPerformanceRow[];
  currency: string;
}

const headers = [
  "Campaign",
  "Platform",
  "Parish",
  "Spend",
  "Impressions",
  "Clicks",
  "Conversions",
  "ROAS",
  "CTR",
  "CPC",
  "CPM",
];

const CampaignTable = ({ rows, currency }: CampaignTableProps) => {
  const { selectedParish, setSelectedParish } = useDashboardStore((state) => ({
    selectedParish: state.selectedParish,
    setSelectedParish: state.setSelectedParish,
  }));

  const [sorting, setSorting] = useState<SortingState>([{ id: "spend", desc: true }]);
  const [columnPinning, setColumnPinning] = useState<ColumnPinningState>({ left: ["name"] });

  const columns = useMemo<ColumnDef<CampaignPerformanceRow>[]>(
    () => [
      {
        accessorKey: "name",
        header: "Campaign",
        enablePinning: true,
        cell: ({ row }) => (
          <div className="campaign-name">
            <strong>{row.original.name}</strong>
            <span className="campaign-meta">{row.original.status}</span>
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
      {
        accessorKey: "cpc",
        header: "CPC",
        cell: ({ getValue }) => formatCurrency(Number(getValue()), currency, 2),
      },
      {
        accessorKey: "cpm",
        header: "CPM",
        cell: ({ getValue }) => formatCurrency(Number(getValue()), currency, 2),
      },
    ],
    [currency]
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
    if (typeof window === "undefined") {
      return;
    }

    const csvRows = table.getRowModel().rows.map((row) => [
      row.original.name,
      row.original.platform,
      row.original.parish ?? "—",
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
      .map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(","))
      .join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `campaign-performance-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="table-card">
      <div className="table-card__header">
        <div>
          <h3>Campaign performance</h3>
          {selectedParish ? (
            <p className="status-message muted">
              Filtering to <strong>{selectedParish}</strong>
              <button type="button" onClick={() => setSelectedParish(undefined)} className="link-button">
                Clear
              </button>
            </p>
          ) : (
            <p className="status-message muted">Click a parish to focus the table.</p>
          )}
        </div>
        <button type="button" onClick={handleExport} className="button secondary">
          Export CSV
        </button>
      </div>
      <div className="table-responsive">
        <table>
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id} colSpan={header.colSpan} className={header.column.getIsPinned() ? "pinned" : undefined}>
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
                  <td key={cell.id} className={cell.column.getIsPinned() ? "pinned" : undefined}>
                    {flexRender(cell.column.columnDef.cell ?? ((ctx) => ctx.getValue()), cell.getContext())}
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
