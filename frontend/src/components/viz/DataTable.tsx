import { useCallback, useMemo, type ReactNode } from 'react';
import {
  flexRender,
  type ColumnDef,
  type Row,
  type SortingState,
} from '@tanstack/react-table';

import BaseDataTable from '../DataTable';
import { downloadCsv, rowsToCsv, type CsvCell } from '../../lib/csvExport';

type Density = 'comfortable' | 'compact';

export type VizDataTableProps<TData> = {
  columns: ColumnDef<TData, unknown>[];
  data: TData[];
  /** Stable row-id accessor when the row data lacks a natural unique key. */
  getRowId?: (originalRow: TData, index: number, parent?: Row<TData>) => string;

  /** Heading rendered above the table (pass-through to the base table). */
  title?: ReactNode;
  description?: ReactNode;
  emptyMessage?: ReactNode;
  searchPlaceholder?: string;

  /** Controls default sort / density when first mounted. */
  initialSorting?: SortingState;
  initialDensity?: Density;

  /**
   * Accessibility caption — rendered as a `<caption>` equivalent above the
   * table. When `captionHidden` is true the text is still exposed to assistive
   * technology via a visually-hidden element.
   */
  caption?: string;
  captionHidden?: boolean;

  /** Optional aria-label on the outer region wrapper. */
  ariaLabel?: string;

  /**
   * When provided, a "Download CSV" button is rendered. The click handler
   * serializes every visible column for every provided row using
   * `lib/csvExport.ts` and triggers a browser download. Pass a custom
   * `csvRowMapper` to control which value appears in each column (default
   * reads `row[column.accessorKey]`).
   */
  csvFilename?: string;
  csvRowMapper?: (row: TData, index: number) => CsvCell[];
};

const classNames = (...values: Array<string | false | null | undefined>) =>
  values.filter(Boolean).join(' ');

/** Pull a header label out of a TanStack column definition for CSV headers. */
const resolveColumnHeader = <TData,>(column: ColumnDef<TData, unknown>): string => {
  const header = column.header;
  if (typeof header === 'string') {
    return header;
  }
  if (typeof column.id === 'string' && column.id.length > 0) {
    return column.id;
  }
  const accessor = (column as { accessorKey?: string }).accessorKey;
  return typeof accessor === 'string' ? accessor : '';
};

/** Resolve a row/column value for CSV rendering (default behaviour). */
const defaultCellValue = <TData,>(
  row: TData,
  column: ColumnDef<TData, unknown>,
): CsvCell => {
  const accessorKey = (column as { accessorKey?: string }).accessorKey;
  if (typeof accessorKey === 'string') {
    const value = (row as Record<string, unknown>)[accessorKey];
    if (value === null || value === undefined) {
      return '';
    }
    if (typeof value === 'number' || typeof value === 'string') {
      return value;
    }
    return String(value);
  }

  // Fall back to invoking a function accessor if the column defines one.
  const accessorFn = (column as { accessorFn?: (row: TData) => unknown }).accessorFn;
  if (typeof accessorFn === 'function') {
    const value = accessorFn(row);
    if (value === null || value === undefined) {
      return '';
    }
    if (typeof value === 'number' || typeof value === 'string') {
      return value;
    }
    return String(value);
  }

  return '';
};

/**
 * Thin viz-kit wrapper around the rich `components/DataTable.tsx`.
 *
 * Adds:
 *   - Visible `<caption>`-equivalent with optional `captionHidden` behaviour.
 *   - Optional `aria-label` on the outer region for pages that render several
 *     tables side-by-side.
 *   - CSV export button wired through `lib/csvExport.ts`.
 *   - Pass-through for default sort and density controls.
 */
const VizDataTable = <TData,>({
  columns,
  data,
  getRowId,
  title,
  description,
  emptyMessage,
  searchPlaceholder,
  initialSorting,
  initialDensity,
  caption,
  captionHidden,
  ariaLabel,
  csvFilename,
  csvRowMapper,
}: VizDataTableProps<TData>) => {
  const headers = useMemo(
    () => columns.map((column) => resolveColumnHeader(column)),
    [columns],
  );

  const handleCsvDownload = useCallback(() => {
    if (!csvFilename) {
      return;
    }

    const mapRow = (row: TData, index: number): CsvCell[] => {
      if (typeof csvRowMapper === 'function') {
        return csvRowMapper(row, index);
      }
      return columns.map((column) => defaultCellValue(row, column));
    };

    const rows = data.map((row, index) => mapRow(row, index));
    const csv = rowsToCsv(headers, rows);
    downloadCsv(csvFilename, csv);
  }, [columns, csvFilename, csvRowMapper, data, headers]);

  const captionNode = caption ? (
    <div
      className={classNames(
        'viz-data-table__caption',
        captionHidden && 'visually-hidden',
      )}
    >
      {caption}
    </div>
  ) : null;

  return (
    <section className="viz-data-table" aria-label={ariaLabel}>
      {captionNode}
      {csvFilename ? (
        <div className="viz-data-table__actions">
          <button
            type="button"
            className="viz-data-table__csv-button button tertiary"
            onClick={handleCsvDownload}
          >
            Download CSV
          </button>
        </div>
      ) : null}
      <BaseDataTable
        columns={columns}
        data={data}
        getRowId={getRowId}
        title={title}
        description={description}
        emptyMessage={emptyMessage}
        searchPlaceholder={searchPlaceholder}
        initialSorting={initialSorting}
        initialDensity={initialDensity}
      />
    </section>
  );
};

// `flexRender` is re-exported so callers building columns with the viz table
// don't need to pull in `@tanstack/react-table` directly for simple cases.
export { flexRender };

export default VizDataTable;
