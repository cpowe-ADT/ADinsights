# Saved Dashboards Builder — Visualization Upgrade

**Sprint:** 4
**Estimated size:** M
**Depends on:** sprint-1/\* (all kit components), sprint-4/platforms.md (for platformLabels.ts)
**Blocks:** nothing (final Sprint 4 deliverable)
**Role needed:** frontend-engineer

## Context

Three related pages: `SavedDashboardPage` (`/dashboards/saved/:id`), `DashboardCreate` (`/dashboards/create`), `DashboardLibrary` (`/dashboards/library`). A4 patches B-SAVED-01 (normalizeFilters restores platforms field) and B-SAVED-02 (seededRef dep array fix) are applied. This sprint wires each saved slot type to a Sprint 1 kit component.

## Inputs already in the repo (do not re-invent)

- `frontend/src/routes/SavedDashboardPage.tsx`: existing file. B-SAVED-01 and B-SAVED-02 applied.
- `frontend/src/routes/DashboardCreate.tsx`: existing file.
- `frontend/src/routes/DashboardLibrary.tsx`: existing file.
- All Sprint 1 viz components.
- `frontend/src/lib/platformLabels.ts`.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/routes/SavedDashboardPage.tsx` (modify)
  - `frontend/src/routes/DashboardCreate.tsx` (modify — light)
  - `frontend/src/routes/DashboardLibrary.tsx` (modify — light)
  - `frontend/src/lib/dashboardSlotRenderer.tsx` (create — new helper)
  - `frontend/src/types/dashboardSlot.ts` (create — new types file)
  - `frontend/src/routes/__tests__/SavedDashboardPage.test.tsx` (modify)

---

### Step 1: Define slot types

Create `frontend/src/types/dashboardSlot.ts`:

```typescript
export type SlotType =
  | 'kpi-strip'
  | 'trend-line'
  | 'distribution-bar'
  | 'pie-composition'
  | 'bubble-scatter'
  | 'data-table'
  | 'map';

export interface SlotDataBinding {
  endpoint: string; // e.g., '/api/metrics/combined/'
  fields: string[]; // field keys to extract
  filters?: Record<string, unknown>; // static filter overrides
  aggregation?: 'sum' | 'mean' | 'count' | 'none';
}

export interface DashboardSlot {
  id: string;
  type: SlotType;
  title?: string;
  gridColumn?: string; // CSS grid-column value, e.g., '1 / 7'
  gridRow?: string; // CSS grid-row value
  dataBinding: SlotDataBinding;
  props?: Record<string, unknown>; // extra props passed to the kit component
}

export interface SavedDashboardDefinition {
  id: string;
  name: string;
  filters: {
    platforms: string[];
    dateRange?: { start: string; end: string };
    accountId?: string;
  };
  slots: DashboardSlot[];
}
```

---

### Step 2: Create slot renderer

Create `frontend/src/lib/dashboardSlotRenderer.tsx`:

```typescript
import { KpiTile } from '../components/viz/KpiTile'
import { TrendLine } from '../components/viz/TrendLine'
import { DistributionBar } from '../components/viz/DistributionBar'
import { PieComposition } from '../components/viz/PieComposition'
import { BubbleScatter } from '../components/viz/BubbleScatter'
import { DataTable } from '../components/viz/DataTable'
import type { DashboardSlot } from '../types/dashboardSlot'

export function renderSlot(slot: DashboardSlot, data: unknown, isLoading: boolean): React.ReactNode {
  switch (slot.type) {
    case 'kpi-strip':
      // data is array of { label, value, format, change? }
      return <div style={{ display: 'flex', gap: 12 }}>
        {(data as KpiTileProps[]).map(tile => (
          <KpiTile key={tile.label} {...tile} isLoading={isLoading} />
        ))}
      </div>
    case 'trend-line':
      return <TrendLine {...(slot.props ?? {})} data={data as any} isLoading={isLoading} />
    case 'distribution-bar':
      return <DistributionBar {...(slot.props ?? {})} data={data as any} isLoading={isLoading} />
    case 'pie-composition':
      return <PieComposition {...(slot.props ?? {})} data={data as any} isLoading={isLoading} />
    case 'bubble-scatter':
      return <BubbleScatter {...(slot.props ?? {})} data={data as any} isLoading={isLoading} />
    case 'data-table':
      return <DataTable {...(slot.props ?? {})} data={data as any} isLoading={isLoading} />
    case 'map':
      // Map component is page-level — show a placeholder in saved dashboards
      return <div style={{ height: 200, background: '#f3f4f6', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span>Map (open Map page for full view)</span>
      </div>
    default:
      return null
  }
}
```

---

### Step 3: Update SavedDashboardPage

In `SavedDashboardPage.tsx`:

1. Parse the saved `slots: DashboardSlot[]` from the saved dashboard definition.
2. For each slot, use `slot.dataBinding.endpoint` and `slot.dataBinding.filters` to fetch data (or derive from the already-fetched combined payload in the store).
3. Render each slot in a CSS grid: `display: grid; grid-template-columns: repeat(12, 1fr); gap: 16px`. Each slot uses `gridColumn` and `gridRow` from its definition.
4. Call `renderSlot(slot, data, isLoading)` for each slot.

**Important**: the existing `normalizeFilters` function (B-SAVED-01) restores `platforms` field when loading a saved dashboard. Do NOT remove or modify it.

### Step 4: DashboardCreate + DashboardLibrary (light)

- DashboardCreate: when creating a new dashboard, add a "Slot Type" picker to the slot definition UI (if a slot builder exists). If no builder exists yet, skip and just ensure `SavedDashboardDefinition` type is used for the output JSON.
- DashboardLibrary: verify the heading fix (FP-LIB-01) is in place. Add a test asserting the heading renders.

## Definition of Done

- [ ] `dashboardSlot.ts` type file created with `SlotType`, `SlotDataBinding`, `DashboardSlot`, `SavedDashboardDefinition`
- [ ] `dashboardSlotRenderer.tsx` created with `renderSlot` function covering all 7 slot types
- [ ] `SavedDashboardPage` renders slots using `renderSlot` in a 12-column CSS grid
- [ ] `normalizeFilters` (B-SAVED-01) preserved — test still passes
- [ ] `seededRef` dep array fix (B-SAVED-02) preserved
- [ ] DashboardLibrary heading renders correctly (FP-LIB-01 verified)
- [ ] Tests green
- [ ] Lint clean and build clean

## Test deltas

```typescript
describe('dashboardSlotRenderer', () => {
  it('renders KpiTile for kpi-strip slot', () => {
    const slot: DashboardSlot = { id: '1', type: 'kpi-strip', dataBinding: { endpoint: '/api/...', fields: [] } }
    const data = [{ label: 'Spend', value: 1000, format: 'currency' as const }]
    const node = renderSlot(slot, data, false)
    const { container } = render(<>{node}</>)
    expect(container.querySelector('[role="figure"]')).toBeInTheDocument()
  })

  it('renders map placeholder for map slot', () => {
    const slot: DashboardSlot = { id: '2', type: 'map', dataBinding: { endpoint: '', fields: [] } }
    const node = renderSlot(slot, null, false)
    const { container } = render(<>{node}</>)
    expect(container.textContent).toContain('Map')
  })
})

describe('SavedDashboardPage', () => {
  it('normalizeFilters restores platforms field from saved definition', () => { /* existing test */ })
  it('renders slots in CSS grid layout', () => { ... })
  it('passes isLoading=true to slots while data is loading', () => { ... })
})

describe('DashboardLibrary', () => {
  it('renders correct page heading', () => { /* FP-LIB-01 test */ })
})
```

## Out of scope

- Do NOT build a drag-and-drop slot editor
- Do NOT implement slot data binding resolution logic for all 7 endpoint types — use the existing combined payload for Sprint 4; per-slot endpoint fetching is a future sprint
- Do NOT modify `normalizeFilters` or the `seededRef` pattern
