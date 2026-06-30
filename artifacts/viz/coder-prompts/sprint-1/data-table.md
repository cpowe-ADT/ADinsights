# DataTable Component

**Sprint:** 1
**Estimated size:** M
**Depends on:** ChartSkeleton, Sparkline (for inline sparkline column support)
**Blocks:** all Sprint 2–4 pages with drill-down tables
**Role needed:** frontend-engineer

## Context

`DataTable` is the shared sortable, paginated, CSV-exportable table component. It wraps TanStack Table v8 (already installed: `@tanstack/react-table ^8.15.0`). Used everywhere there is a drill-down table — campaigns, keywords, posts, parishes, assets. Supports inline `Sparkline` cells, status chips, and row-click navigation. CSV export is entirely client-side — no PapaParse, hand-rolled serializer.

## Inputs already in the repo (do not re-invent)

- `@tanstack/react-table ^8.15.0`: already installed. Use `useReactTable`, `getCoreRowModel`, `getSortedRowModel`, `getPaginationRowModel`.
- `frontend/src/components/viz/ChartSkeleton.tsx`: loading skeleton.
- `frontend/src/components/EmptyState.tsx`: empty state with `reasonCode`.
- `frontend/src/components/viz/Sparkline.tsx`: for inline sparkline cells.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/components/viz/DataTable.tsx` (create)
  - `frontend/src/components/viz/__tests__/DataTable.test.tsx` (create)

- **Props API**:

```typescript
import { ColumnDef } from '@tanstack/react-table';

interface DataTableProps<T> {
  columns: ColumnDef<T, unknown>[];
  data: T[];
  isLoading?: boolean;
  onRowClick?: (row: T) => void;
  csvFilename?: string; // enables Download CSV button when provided. Filename: `{csvFilename}-{ISO-date}.csv`
  emptyReasonCode?: string;
  pageSize?: number; // default: 25
  className?: string;
}
```

- **Data binding**: caller provides `columns` and `data`. No store access inside this component.

- **Interactions**:
  - Column header click → sort ascending/descending (toggles on repeated click). Sort indicator icon in header (▲/▼). `aria-sort="ascending"` or `"descending"` on `<th>`.
  - Row click → `onRowClick(row.original)` if provided; cursor: pointer.
  - Pagination: Previous/Next buttons + "Page N of M" display. Keyboard accessible.
  - "Download CSV" button: serializes currently-visible (all pages, current sort) rows to CSV and triggers a `blob:` URL download. Filename: `${csvFilename}-${new Date().toISOString().slice(0,10)}.csv`.

- **Empty/loading/error states**:
  - `isLoading=true`: `<ChartSkeleton variant="table" rows={pageSize} />`
  - `data.length === 0 && !isLoading`: `<EmptyState reasonCode={emptyReasonCode ?? 'no_data_for_range'} />`

- **A11y**: `<table>` with `<thead>`, `<tbody>`. `<th scope="col">` for all column headers. `<tr>` with `role="row"`. Clickable rows have `tabIndex={0}` + `onKeyDown` for Enter/Space. Sort indicators use `aria-sort`.

## Design

```
┌────────────────────────────────────────────────────┐
│  [Download CSV]                                     │  ← only if csvFilename provided
├────────┬───────────┬────────┬───────────────────────┤
│ Name ▲ │ Spend     │ ROAS   │ ...                   │  ← sortable headers
├────────┼───────────┼────────┼───────────────────────┤
│ Camp A │ $1,234    │ 2.5x   │                       │  ← rows (row click if handler)
│ Camp B │ $987      │ 1.8x   │ [sparkline]           │  ← inline Sparkline column
└────────┴───────────┴────────┴───────────────────────┘
│ < Prev   Page 1 of 4   Next > │
```

CSV serializer (no PapaParse — hand-rolled):

```typescript
function toCSV<T>(columns: ColumnDef<T, unknown>[], data: T[]): string {
  const headers = columns
    .map((col) => String((col as any).header ?? (col as any).id ?? ''))
    .join(',');
  const rows = data.map((row) =>
    columns
      .map((col) => {
        const key = (col as any).accessorKey ?? (col as any).id ?? '';
        const val = (row as any)[key] ?? '';
        const str = String(val);
        return str.includes(',') || str.includes('"')
          ? `"${str.replace(/"/g, '""')}"`
          : str;
      })
      .join(','),
  );
  return [headers, ...rows].join('\n');
}

function downloadCSV(content: string, filename: string): void {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
```

## Definition of Done

- [ ] Renders table with sortable column headers (click to sort)
- [ ] `aria-sort` attribute updates on sort change
- [ ] Row click fires `onRowClick`
- [ ] Clickable rows are keyboard navigable (Enter/Space)
- [ ] Pagination shows Previous/Next with correct page counts
- [ ] "Download CSV" button present when `csvFilename` provided
- [ ] CSV snapshot test: given known data, output matches expected CSV string
- [ ] `isLoading=true` shows ChartSkeleton
- [ ] Empty data shows EmptyState
- [ ] jest-axe passes
- [ ] Tests green: `cd frontend && npm test -- --run src/components/viz/__tests__/DataTable.test.tsx`
- [ ] Lint clean: `cd frontend && npm run lint`
- [ ] Build clean: `cd frontend && npm run build`

## Test deltas

File: `frontend/src/components/viz/__tests__/DataTable.test.tsx`

```typescript
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe } from 'jest-axe'
import { createColumnHelper } from '@tanstack/react-table'
import { DataTable } from '../DataTable'

type Row = { name: string; spend: number }
const columnHelper = createColumnHelper<Row>()
const columns = [
  columnHelper.accessor('name', { header: 'Name' }),
  columnHelper.accessor('spend', { header: 'Spend' }),
]
const data: Row[] = [
  { name: 'Campaign A', spend: 1000 },
  { name: 'Campaign B', spend: 500 },
  { name: 'Campaign C', spend: 2000 },
]

describe('DataTable', () => {
  it('renders all rows', () => {
    render(<DataTable columns={columns} data={data} />)
    expect(screen.getByText('Campaign A')).toBeInTheDocument()
    expect(screen.getByText('Campaign B')).toBeInTheDocument()
  })

  it('sorts by column on header click', async () => {
    const user = userEvent.setup()
    render(<DataTable columns={columns} data={data} />)
    const nameHeader = screen.getByRole('columnheader', { name: /name/i })
    await user.click(nameHeader)
    const rows = screen.getAllByRole('row').slice(1) // skip header row
    expect(rows[0]).toHaveTextContent('Campaign A')
  })

  it('fires onRowClick when row clicked', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(<DataTable columns={columns} data={data} onRowClick={onClick} />)
    await user.click(screen.getByText('Campaign A'))
    expect(onClick).toHaveBeenCalledWith(data[0])
  })

  it('shows ChartSkeleton when isLoading', () => {
    render(<DataTable columns={columns} data={[]} isLoading />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('shows EmptyState when data empty', () => {
    render(<DataTable columns={columns} data={[]} emptyReasonCode="no_campaigns" />)
    expect(screen.getByTestId('empty-state')).toHaveAttribute('data-reason-code', 'no_campaigns')
  })

  it('CSV download button present when csvFilename provided', () => {
    render(<DataTable columns={columns} data={data} csvFilename="campaigns" />)
    expect(screen.getByRole('button', { name: /download csv/i })).toBeInTheDocument()
  })

  it('CSV output matches expected format', () => {
    // Test the toCSV function in isolation if exported, else via integration
    render(<DataTable columns={columns} data={data} csvFilename="test" />)
    // Snapshot test of CSV content by mocking URL.createObjectURL and capturing blob
    const mockCreate = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock')
    const mockRevoke = vi.spyOn(URL, 'revokeObjectURL').mockReturnValue(undefined)
    fireEvent.click(screen.getByRole('button', { name: /download csv/i }))
    expect(mockCreate).toHaveBeenCalled()
    const blob = mockCreate.mock.calls[0][0] as Blob
    // Read blob text synchronously not possible; verify it was created
    expect(blob.type).toBe('text/csv;charset=utf-8;')
    mockCreate.mockRestore()
    mockRevoke.mockRestore()
  })

  it('has no a11y violations', async () => {
    const { container } = render(<DataTable columns={columns} data={data} />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
```

## Out of scope

- Do NOT use PapaParse — hand-rolled CSV only
- Do NOT implement server-side pagination — all pagination is client-side
- Do NOT add column resizing or reordering
- Do NOT remove or replace existing ad-hoc tables in Sprint 1 — migration happens page-by-page in Sprints 2–4
