# KpiTile Component

**Sprint:** 1
**Estimated size:** S
**Depends on:** none (but requires EmptyState to be extended first — do that inline)
**Blocks:** all Sprint 2–4 pages
**Role needed:** frontend-engineer

## Context

`KpiTile` is the primary KPI display unit used at the top of every dashboard page. It shows a single metric value, label, optional period-over-period change arrow, and handles loading/null states. It is used in groups of 4–6 across the top of each page in a flex row. The existing `EmptyState` component must also be confirmed to have the `reasonCode` prop (added by A4 synthesis) — if it is missing, add it as part of this ticket.

## Inputs already in the repo (do not re-invent)

- `frontend/src/components/EmptyState.tsx`: existing component; A4 synthesis added `reasonCode?: string` prop that renders as `data-reason-code` attribute. Verify this prop exists before proceeding.
- `frontend/src/styles/chartTheme.ts`: color tokens. Use `chartPalette[0]` for positive change, `chartPalette[5]` for negative change.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/components/viz/KpiTile.tsx` (create)
  - `frontend/src/components/viz/__tests__/KpiTile.test.tsx` (create)

- **Props API**:
```typescript
type ChartValueType = 'currency' | 'number' | 'percent' | 'rate'

interface KpiTileProps {
  label: string
  value: number | null
  format: ChartValueType
  currency?: string          // default 'JMD'
  change?: number | null     // period-over-period delta as decimal (0.12 = +12%)
  isLoading?: boolean
  isFaded?: boolean          // for tiles outside current filter scope
  reasonCode?: string        // passed through to EmptyState if value is null
  className?: string
}
```

- **Data binding**: caller maps `payload.metrics.*` fields to individual tiles. Example: `<KpiTile label="Spend" value={metrics.spend} format="currency" change={metrics.spend_change} />`

- **Interactions**: hover shows tooltip with raw unformatted value + period label (e.g., "Last 30 days"). No click. Tooltip implemented with a simple CSS `title` attribute or a small absolutely-positioned `<div>` — do NOT import a tooltip library.

- **Empty/loading/error states**:
  - `isLoading=true`: shimmer rectangle 100% wide × 80px tall using CSS animation `@keyframes shimmer`
  - `value === null && !isLoading`: shows `--` text and faded background; if `reasonCode` provided, renders `<EmptyState reasonCode={reasonCode} />` inline in compact mode

- **A11y**: `role="figure"` on the root element; `aria-label="{label}: {formatted_value}"` where formatted_value is the human-readable string. Change arrow uses `aria-label="up N%" or "down N%"`.

## Design

```
┌────────────────────────────┐
│ LABEL                      │
│ $1,234,567 JMD  ▲ +12%     │
│ (shimmer when loading)     │
└────────────────────────────┘
```

Color tokens from `frontend/src/styles/chartTheme.ts`:
- Positive change: `chartPalette[3]` (#10b981 green)
- Negative change: `chartPalette[5]` (#f43f5e red)
- Neutral/null: text-gray-400
- Loading shimmer background: `#e5e7eb` → `#f9fafb` animated gradient

Format helpers (implement inline):
```typescript
function formatValue(value: number, format: ChartValueType, currency = 'JMD'): string {
  switch (format) {
    case 'currency': return new Intl.NumberFormat('en-JM', { style: 'currency', currency, maximumFractionDigits: 0 }).format(value)
    case 'percent': return `${(value * 100).toFixed(1)}%`
    case 'rate': return value.toFixed(2)
    case 'number': return new Intl.NumberFormat('en-JM').format(Math.round(value))
  }
}
```

## Definition of Done

- [ ] Renders correctly for all four `format` values (snapshot test)
- [ ] Loading shimmer shows when `isLoading=true` and no value is visible
- [ ] `value === null` renders `--` not a JS error
- [ ] Positive change shows green arrow, negative shows red
- [ ] `isFaded=true` reduces opacity to 0.5
- [ ] `role="figure"` and `aria-label` present in rendered output
- [ ] jest-axe passes: `expect(await axe(container)).toHaveNoViolations()`
- [ ] Tests green: `cd frontend && npm test -- --run src/components/viz/__tests__/KpiTile.test.tsx`
- [ ] Lint clean: `cd frontend && npm run lint`
- [ ] Build clean: `cd frontend && npm run build`

## Test deltas

File: `frontend/src/components/viz/__tests__/KpiTile.test.tsx`

```typescript
import { render, screen } from '@testing-library/react'
import { axe } from 'jest-axe'
import { KpiTile } from '../KpiTile'

describe('KpiTile', () => {
  it('renders formatted currency value', () => {
    render(<KpiTile label="Spend" value={1234567} format="currency" />)
    expect(screen.getByRole('figure')).toBeInTheDocument()
    expect(screen.getByText(/1,234,567/)).toBeInTheDocument()
  })

  it('renders -- when value is null', () => {
    render(<KpiTile label="Spend" value={null} format="currency" />)
    expect(screen.getByText('--')).toBeInTheDocument()
  })

  it('shows shimmer and no value when isLoading', () => {
    const { container } = render(<KpiTile label="Spend" value={null} format="currency" isLoading />)
    expect(container.querySelector('[data-testid="kpi-shimmer"]')).toBeInTheDocument()
    expect(screen.queryByText('--')).not.toBeInTheDocument()
  })

  it('shows green arrow for positive change', () => {
    render(<KpiTile label="Spend" value={100} format="number" change={0.12} />)
    expect(screen.getByLabelText(/up 12%/i)).toBeInTheDocument()
  })

  it('shows red arrow for negative change', () => {
    render(<KpiTile label="Spend" value={100} format="number" change={-0.05} />)
    expect(screen.getByLabelText(/down 5%/i)).toBeInTheDocument()
  })

  it('has no a11y violations', async () => {
    const { container } = render(<KpiTile label="CTR" value={0.023} format="percent" />)
    expect(await axe(container)).toHaveNoViolations()
  })

  it('renders percent format correctly', () => {
    render(<KpiTile label="CTR" value={0.023} format="percent" />)
    expect(screen.getByText('2.3%')).toBeInTheDocument()
  })
})
```

Mocking: none required. All state is prop-driven.

## Out of scope

- Do NOT add a tooltip library
- Do NOT modify `EmptyState.tsx` beyond confirming `reasonCode` prop exists
- Do NOT add click handlers
- Do NOT implement currency conversion logic — display as-is with JMD label

## Open questions resolved

- **OQ-7 (PapaParse dependency)**: Not applicable to this component. PapaParse is NOT installed; the DataTable prompt handles CSV with a hand-rolled serializer.
- **OQ-6 (FunnelChart in Recharts 3.8.1)**: Not applicable to this component. Recharts 3.8.1 does not ship FunnelChart; use stepped-bar fallback — handled in `meta-campaigns.md`.
