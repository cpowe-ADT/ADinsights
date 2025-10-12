import { useCallback, useMemo } from "react";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";

import useDashboardStore, { MetricRow } from "../state/useDashboardStore";

const MetricsGrid = () => {
  const { rows, selectedParish, selectedMetric, setSelectedParish } = useDashboardStore();

  const sortedRows = useMemo<MetricRow[]>(() => {
    if (rows.length === 0) {
      return [];
    }

    return [...rows].sort((a, b) => {
      const left = b[selectedMetric] ?? 0;
      const right = a[selectedMetric] ?? 0;
      return left - right;
    });
  }, [rows, selectedMetric]);

  const handleRowSelect = useCallback(
    (parish: string) => {
      setSelectedParish(parish);
    },
    [setSelectedParish]
  );

  const sortedRows = useMemo<MetricRow[]>(() => {
    if (filteredRows.length === 0) {
      return [];
    }

    return [...filteredRows].sort((a, b) => {
      const left = b[selectedMetric] ?? 0;
      const right = a[selectedMetric] ?? 0;
      return left - right;
    });
  }, [filteredRows, selectedMetric]);

  const columns = useMemo<ColumnDef<MetricRow>[]>(
    () => [
      { header: "Date", accessorKey: "date" },
      { header: "Platform", accessorKey: "platform" },
      { header: "Campaign", accessorKey: "campaign" },
      { header: "Parish", accessorKey: "parish" },
      { header: "Impressions", accessorKey: "impressions" },
      { header: "Clicks", accessorKey: "clicks" },
      { header: "Spend", accessorKey: "spend" },
      { header: "Conversions", accessorKey: "conversions" },
      { header: "ROAS", accessorKey: "roas" },
    ],
    []
  );

  const table = useReactTable({
    data: sortedRows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="metrics-grid">
      <h2>Performance Grid</h2>
      <p>
        Sorted by <strong>{selectedMetric}</strong>
        {selectedParish ? (
          <>
            {" "}— highlighting <strong>{selectedParish}</strong>.
          </>
        ) : (
          "."
        )}
      </p>
      <table>
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th key={header.id}>
                  {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              className={row.original.parish === selectedParish ? "selected" : undefined}
              tabIndex={0}
              onClick={() => handleRowSelect(row.original.parish)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  handleRowSelect(row.original.parish);
                }
              }}
              aria-selected={row.original.parish === selectedParish}
            >
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id}>{flexRender(cell.column.columnDef.cell ?? ((ctx) => ctx.getValue()), cell.getContext())}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default MetricsGrid;
