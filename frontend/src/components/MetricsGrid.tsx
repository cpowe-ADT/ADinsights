import { useMemo } from "react";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";

import useDashboardStore, { MetricRow } from "../state/useDashboardStore";

const MetricsGrid = () => {
  const { rows, selectedParish, selectedMetric } = useDashboardStore();

  const filteredRows = useMemo<MetricRow[]>(() => {
    if (!selectedParish) {
      return rows;
    }
    return rows.filter((row) => row.parish === selectedParish);
  }, [rows, selectedParish]);

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
    data: filteredRows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="metrics-grid">
      <h2>Performance Grid</h2>
      {selectedParish ? (
        <p>
          Showing results for <strong>{selectedParish}</strong> ordered by {selectedMetric}.
        </p>
      ) : (
        <p>Showing all parishes ordered by {selectedMetric}.</p>
      )}
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
            <tr key={row.id}>
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
