import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from "@tanstack/react-table";

import useDashboardStore, { MetricRow } from "../state/useDashboardStore";

const MetricsGrid = () => {
  const { rows, selectedParish, selectedMetric, setSelectedParish, status, error } = useDashboardStore();

  const [sorting, setSorting] = useState<SortingState>([
    { id: selectedMetric, desc: true },
  ]);

  useEffect(() => {
    setSorting([{ id: selectedMetric, desc: true }]);
  }, [selectedMetric]);

  const handleRowSelect = useCallback(
    (parish: string) => {
      setSelectedParish(parish);
    },
    [setSelectedParish]
  );

  const columns = useMemo<ColumnDef<MetricRow>[]>(
    () => [
      {
        header: "Date",
        accessorKey: "date",
        enableSorting: true,
        sortingFn: (rowA, rowB, columnId) => {
          const valueA = (rowA.getValue(columnId) as string | undefined) ?? "";
          const valueB = (rowB.getValue(columnId) as string | undefined) ?? "";
          return valueA.localeCompare(valueB);
        },
      },
      {
        header: "Platform",
        accessorKey: "platform",
        enableSorting: true,
        sortingFn: (rowA, rowB, columnId) => {
          const valueA = (rowA.getValue(columnId) as string | undefined) ?? "";
          const valueB = (rowB.getValue(columnId) as string | undefined) ?? "";
          return valueA.localeCompare(valueB);
        },
      },
      {
        header: "Campaign",
        accessorKey: "campaign",
        enableSorting: true,
        sortingFn: (rowA, rowB, columnId) => {
          const valueA = (rowA.getValue(columnId) as string | undefined) ?? "";
          const valueB = (rowB.getValue(columnId) as string | undefined) ?? "";
          return valueA.localeCompare(valueB);
        },
      },
      {
        header: "Parish",
        accessorKey: "parish",
        enableSorting: true,
        sortingFn: (rowA, rowB, columnId) => {
          const valueA = (rowA.getValue(columnId) as string | undefined) ?? "";
          const valueB = (rowB.getValue(columnId) as string | undefined) ?? "";
          return valueA.localeCompare(valueB);
        },
      },
      {
        header: "Impressions",
        accessorKey: "impressions",
        enableSorting: true,
        sortingFn: (rowA, rowB, columnId) => {
          const valueA = Number(rowA.getValue(columnId) ?? 0);
          const valueB = Number(rowB.getValue(columnId) ?? 0);
          return valueA - valueB;
        },
      },
      {
        header: "Clicks",
        accessorKey: "clicks",
        enableSorting: true,
        sortingFn: (rowA, rowB, columnId) => {
          const valueA = Number(rowA.getValue(columnId) ?? 0);
          const valueB = Number(rowB.getValue(columnId) ?? 0);
          return valueA - valueB;
        },
      },
      {
        header: "Spend",
        accessorKey: "spend",
        enableSorting: true,
        sortingFn: (rowA, rowB, columnId) => {
          const valueA = Number(rowA.getValue(columnId) ?? 0);
          const valueB = Number(rowB.getValue(columnId) ?? 0);
          return valueA - valueB;
        },
      },
      {
        header: "Conversions",
        accessorKey: "conversions",
        enableSorting: true,
        sortingFn: (rowA, rowB, columnId) => {
          const valueA = Number(rowA.getValue(columnId) ?? 0);
          const valueB = Number(rowB.getValue(columnId) ?? 0);
          return valueA - valueB;
        },
      },
      {
        header: "ROAS",
        accessorKey: "roas",
        enableSorting: true,
        sortingFn: (rowA, rowB, columnId) => {
          const valueA = Number(rowA.getValue(columnId) ?? 0);
          const valueB = Number(rowB.getValue(columnId) ?? 0);
          return valueA - valueB;
        },
      },
    ],
    []
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
    <div className="metrics-grid">
      <h2>Performance Grid</h2>
      {status === "loading" ? (
        <p className="status-message muted">Loading tenant metrics…</p>
      ) : null}
      {status === "error" ? (
        <p className="status-message error">{error ?? "Unable to load metrics."}</p>
      ) : null}
      {status === "loaded" && table.getRowModel().rows.length === 0 ? (
        <p className="status-message muted">No campaign metrics are available for this tenant yet.</p>
      ) : null}
      {table.getRowModel().rows.length > 0 ? (
        <>
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
                      {header.isPlaceholder ? null : (
                        <button
                          type="button"
                          onClick={header.column.getToggleSortingHandler()}
                          aria-label={`Sort by ${String(header.column.columnDef.header)}`}
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
        </>
      ) : null}
    </div>
  );
};

export default MetricsGrid;
