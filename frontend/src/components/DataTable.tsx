import { Fragment, ReactNode, useId, useState } from "react";
import type { ChangeEvent, CSSProperties } from "react";
import {
  ColumnDef,
  FilterFn,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  Row,
  SortingState,
  useReactTable,
} from "@tanstack/react-table";

type DataTableDensity = "comfortable" | "compact";

type DataTableProps<TData> = {
  columns: ColumnDef<TData, unknown>[];
  data: TData[];
  /**
   * Provide a stable row id when the source data lacks a natural unique key.
   */
  getRowId?: (originalRow: TData, index: number, parent?: Row<TData>) => string;
  /**
   * Optional heading rendered above the table.
   */
  title?: ReactNode;
  /**
   * Optional helper text rendered under the title.
   */
  description?: ReactNode;
  /**
   * Placeholder to show when no rows remain after filtering.
   */
  emptyMessage?: ReactNode;
  /**
   * Placeholder text for the search box.
   */
  searchPlaceholder?: string;
  /**
   * Provide an initial sorting state when required.
   */
  initialSorting?: SortingState;
  /**
   * Configure the initial density when rendering the table.
   */
  initialDensity?: DataTableDensity;
};

const classNames = (...values: Array<string | false | null | undefined>) =>
  values.filter(Boolean).join(" ");

const makeGlobalFilterFn = <TData,>(): FilterFn<TData> =>
  (row, _columnId, filterValue) => {
    const raw = typeof filterValue === "string" ? filterValue : String(filterValue ?? "");
    const search = raw.trim().toLowerCase();

    if (!search) {
      return true;
    }

    return row
      .getAllCells()
      .some((cell) => {
        const value = cell.getValue();
        if (value === null || value === undefined) {
          return false;
        }
        if (typeof value === "number") {
          return String(value).toLowerCase().includes(search);
        }
        if (typeof value === "string") {
          return value.toLowerCase().includes(search);
        }
        if (Array.isArray(value)) {
          return value.some((item) => String(item ?? "").toLowerCase().includes(search));
        }

        return String(value).toLowerCase().includes(search);
      });
  };

const DataTable = <TData,>({
  columns,
  data,
  getRowId,
  title,
  description,
  emptyMessage = "No records found.",
  searchPlaceholder = "Search table",
  initialSorting = [],
  initialDensity = "comfortable",
}: DataTableProps<TData>) => {
  const [sorting, setSorting] = useState<SortingState>(initialSorting);
  const [density, setDensity] = useState<DataTableDensity>(initialDensity);
  const [searchQuery, setSearchQuery] = useState("");

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      globalFilter: searchQuery,
    },
    onSortingChange: setSorting,
    onGlobalFilterChange: setSearchQuery,
    globalFilterFn: makeGlobalFilterFn<TData>(),
    getRowId,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const searchInputId = useId();
  const regionLabel = typeof title === "string" ? title : "Table content";
  const resolveHeaderLabel = (columnId: string) => {
    const header = table.getFlatHeaders().find((item) => item.column.id === columnId);
    if (!header) {
      return columnId;
    }

    return flexRender(header.column.columnDef.header, header.getContext());
  };

  const handleDensityChange = (nextDensity: DataTableDensity) => {
    setDensity(nextDensity);
  };

  const handleSearchChange = (event: ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value;
    setSearchQuery(value);
    table.setGlobalFilter(value);
  };

  const rowCount = table.getRowModel().rows.length;

  return (
    <div className={classNames("data-table", `data-table--${density}`)}>
      <div className="data-table__header">
        {title || description ? (
          <div className="data-table__intro">
            {title ? <h3 className="data-table__title">{title}</h3> : null}
            {description ? <p className="data-table__description">{description}</p> : null}
          </div>
        ) : null}
        <div className="data-table__toolbar" role="group" aria-label="Table tools">
          <label htmlFor={searchInputId} className="data-table__search-label">
            <span className="visually-hidden">{searchPlaceholder}</span>
            <input
              id={searchInputId}
              value={searchQuery}
              onChange={handleSearchChange}
              type="search"
              placeholder={searchPlaceholder}
              className="data-table__search-input"
              aria-label={searchPlaceholder}
            />
          </label>
          <div className="data-table__density" role="group" aria-label="Row density">
            <button
              type="button"
              className="data-table__density-button"
              onClick={() => handleDensityChange("comfortable")}
              aria-pressed={density === "comfortable"}
            >
              Comfortable
            </button>
            <button
              type="button"
              className="data-table__density-button"
              onClick={() => handleDensityChange("compact")}
              aria-pressed={density === "compact"}
            >
              Compact
            </button>
          </div>
        </div>
      </div>
      <div className="data-table__scroll-area" role="region" aria-label={regionLabel}>
        <table className="data-table__table">
          <thead>
            {table.getHeaderGroups().map((headerGroup, headerGroupIndex) => (
              <tr key={headerGroup.id} className="data-table__header-row">
                {headerGroup.headers.map((header) => {
                  const headerRowDepth = headerGroup.depth ?? headerGroupIndex;
                  const headerCellStyle = {
                    ["--data-table-header-depth" as const]: String(headerRowDepth),
                    zIndex: 2 + headerRowDepth,
                  } as CSSProperties;

                  if (header.isPlaceholder) {
                    return (
                      <th
                        key={header.id}
                        className="data-table__header-cell"
                        aria-hidden="true"
                        style={headerCellStyle}
                      />
                    );
                  }

                  const sortState = header.column.getIsSorted();
                  const ariaSort = sortState === "asc" ? "ascending" : sortState === "desc" ? "descending" : "none";

                  return (
                    <th
                      key={header.id}
                      colSpan={header.colSpan}
                      aria-sort={ariaSort}
                      scope="col"
                      className={classNames(
                        "data-table__header-cell",
                        header.column.columnDef.meta && (header.column.columnDef.meta as { isNumeric?: boolean }).isNumeric
                          ? "data-table__cell--numeric"
                          : undefined
                      )}
                      style={headerCellStyle}
                    >
                      {header.column.getCanSort() ? (
                        <button
                          type="button"
                          onClick={header.column.getToggleSortingHandler()}
                          className="data-table__sort-button"
                          aria-label={`Sort by ${String(
                            flexRender(header.column.columnDef.header, header.getContext())
                          )}`}
                        >
                          <span className="data-table__sort-label">
                            {flexRender(header.column.columnDef.header, header.getContext())}
                          </span>
                          <span className="data-table__sort-icon" aria-hidden="true">
                            {sortState === "asc" ? "▲" : sortState === "desc" ? "▼" : "↕"}
                          </span>
                        </button>
                      ) : (
                        <span className="data-table__sort-label">
                          {flexRender(header.column.columnDef.header, header.getContext())}
                        </span>
                      )}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row, index) => {
              const cells = row.getVisibleCells();
              const primaryCells = cells.slice(0, 2);
              const detailCells = cells.slice(2);
              const isZebra = index % 2 === 1;
              const firstValue = primaryCells[0]?.getValue();
              const summaryLabel = firstValue ? `Details for ${String(firstValue)}` : "Row details";

              return (
                <Fragment key={row.id}>
                  <tr
                    className={classNames("data-table__row", isZebra && "data-table__row--zebra")}
                    data-row-type="data"
                  >
                    {primaryCells.map((cell) => (
                      <td
                        key={cell.id}
                        className={classNames(
                          "data-table__cell",
                          (cell.column.columnDef.meta as { isNumeric?: boolean } | undefined)?.isNumeric
                            ? "data-table__cell--numeric"
                            : undefined
                        )}
                      >
                        {flexRender(cell.column.columnDef.cell ?? ((ctx) => ctx.getValue()), cell.getContext())}
                      </td>
                    ))}
                    {detailCells.map((cell) => (
                      <td
                        key={cell.id}
                        className={classNames(
                          "data-table__cell",
                          "data-table__cell--hidden-mobile",
                          (cell.column.columnDef.meta as { isNumeric?: boolean } | undefined)?.isNumeric
                            ? "data-table__cell--numeric"
                            : undefined
                        )}
                      >
                        {flexRender(cell.column.columnDef.cell ?? ((ctx) => ctx.getValue()), cell.getContext())}
                      </td>
                    ))}
                  </tr>
                  {detailCells.length > 0 ? (
                    <tr className="data-table__details-row" data-row-type="details">
                      <td className="data-table__details-cell" colSpan={cells.length}>
                        <details className="data-table__details">
                          <summary>{summaryLabel}</summary>
                          <dl className="data-table__details-grid">
                            {detailCells.map((cell) => {
                              const headerLabel = resolveHeaderLabel(cell.column.id);
                              return (
                                <div key={`${row.id}-${cell.column.id}`} className="data-table__details-item">
                                  <dt>{headerLabel}</dt>
                                  <dd className={classNames(
                                    (cell.column.columnDef.meta as { isNumeric?: boolean } | undefined)?.isNumeric
                                      ? "data-table__cell--numeric"
                                      : undefined
                                  )}>
                                    {flexRender(cell.column.columnDef.cell ?? ((ctx) => ctx.getValue()), cell.getContext())}
                                  </dd>
                                </div>
                              );
                            })}
                          </dl>
                        </details>
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      {rowCount === 0 ? <p className="data-table__empty">{emptyMessage}</p> : null}
    </div>
  );
};

export default DataTable;
