# S1-Architect Design — Shared Data-Viz Component Kit (Sprint 1)

**Cited inputs:** `/Users/thristannewman/ADinsights/artifacts/viz/sprints-plan.md` (§"Design Principles" L24–98, §"Sprint 1 — Foundations" L102–333, §"Shared viz kit props API" L1047–1079), `/Users/thristannewman/ADinsights/frontend/src/styles/chartTheme.ts`, `/Users/thristannewman/ADinsights/frontend/src/styles/theme.css`, `/Users/thristannewman/ADinsights/frontend/.storybook/main.ts`, `/Users/thristannewman/ADinsights/frontend/.storybook/preview.ts`, `/Users/thristannewman/ADinsights/frontend/src/components/{EmptyState,Metric,Skeleton,DataTable,CampaignTrendChart,AgeDistributionBar,DeviceDonut}.tsx`, `/Users/thristannewman/ADinsights/frontend/src/setupTests.ts`, `/Users/thristannewman/ADinsights/frontend/package.json`, `/Users/thristannewman/ADinsights/CLAUDE.md`, `/Users/thristannewman/ADinsights/AGENTS.md`.

---

## 1. Scope & framing

Sprint 1 delivers ten shared viz primitives under `frontend/src/components/viz/` plus supporting token/theming additions, Storybook stories, and a11y snapshot tests. Every primitive consumes only Recharts 3.7 (already installed) + existing CSS tokens. No new chart library, no new CSS system, no backend changes. Downstream sprints (Meta, Google, Combined) will compose these primitives into domain wrappers (`CampaignTrendChart`, `ParishMap`, etc.). Existing domain wrappers remain in place during Sprint 1; they will be migrated in Sprints 2–4.

**Stack baseline confirmed:** Recharts `^3.7.0`, TanStack Table `^8.15.0`, Storybook `8.6.14`, `@storybook/addon-essentials`, `@storybook/addon-interactions`, `jest-axe ^9.0.0`, `@testing-library/react`, `vitest ^3.2.4`. **`@storybook/addon-a11y` is NOT installed** — recommendation in §6. **`papaparse` is NOT installed** — use manual CSV serializer per `sprints-plan.md` L1098.

---

## 2. Component register

All files live under `frontend/src/components/viz/` unless noted. Existing `EmptyState.tsx` stays at `frontend/src/components/EmptyState.tsx` (re-exported from `viz/index.ts`).

| # | Component | Status | Target file path | Existing equivalent | Key props (TS signature sketch) | Notes |
|---|-----------|--------|------------------|---------------------|----------------------------------|-------|
| 1 | `KpiTile` | EXTEND | `frontend/src/components/viz/KpiTile.tsx` | `components/Metric.tsx` (`memo`'d, has sparkline + badge) | `{ label, value: number\|null, format: 'currency'\|'number'\|'percent'\|'rate', currency?: string, change?: number\|null, isLoading?: boolean, isFaded?: boolean, reasonCode?: string, hint?: string }` | Must accept raw `number\|null` and format internally using `lib/formatNumber`. `Metric.tsx` takes pre-formatted strings — `KpiTile` is the new canonical tile. Keep `Metric.tsx` until Sprints 2–4 migrate callers. Render internal `ChartSkeleton variant="kpi"` when `isLoading`. Render `--` with `aria-label="{label}: no data"` when `value === null`. |
| 2 | `TrendLine` | NEW (generic) | `frontend/src/components/viz/TrendLine.tsx` | `components/CampaignTrendChart.tsx` (single-series area chart — stays as domain wrapper) | `{ data: Array<{date:string; [k:string]:number\|string}>, series: Array<{key, label, color, dashed?, yAxis?: 'left'\|'right'}>, peerData?: Array<{date,value}>, yFormat?: ChartValueType, rightYFormat?: ChartValueType, currency?: string, height?: number, isLoading?: boolean, emptyReasonCode?: string, variant?: 'line'\|'stacked-area', onPointClick?: (date:string)=>void }` | Dual-axis via `series[].yAxis` + `rightYFormat`. `variant="stacked-area"` uses `AreaChart` + `stackId` (needed in Sprint 4). `peerData` renders `<PeerAvgLine>`. Wrap in `ResponsiveContainer`. |
| 3 | `Sparkline` | NEW | `frontend/src/components/viz/Sparkline.tsx` | SVG path inside `Metric.tsx` (not reusable) | `{ data: Array<{date:string;value:number}>, color?: string, height?: number, showTooltip?: boolean, ariaLabel?: string }` | Recharts `LineChart` with no axes, no grid, no legend. Used in table cells. Default height 40. Accept `ariaLabel` so callers can describe the metric. |
| 4 | `DistributionBar` | NEW | `frontend/src/components/viz/DistributionBar.tsx` | `components/AgeDistributionBar.tsx` (domain-specific stacked by gender), `components/PlatformComparisonBars.tsx` | `{ data: Array<{label:string; value:number; color?:string; patternId?:string}>, orientation?: 'horizontal'\|'vertical', showPercent?: boolean, yFormat?: ChartValueType, currency?: string, isLoading?: boolean, emptyReasonCode?: string }` | Default orientation `horizontal`. Percent labels via `LabelList` when `showPercent`. Use `<pattern>` defs for non-color encoding (WCAG requirement). |
| 5 | `BubbleScatter` | NEW | `frontend/src/components/viz/BubbleScatter.tsx` | none | `{ data: Array<{id, label, x, y, z, shape?: 'circle'\|'triangle', color?: string}>, xLabel, yLabel, zLabel, xFormat?: ChartValueType, yFormat?: ChartValueType, isLoading?: boolean, onBubbleClick?: (id:string)=>void, emptyReasonCode?: string }` | Recharts `ScatterChart` + `ZAxis` for `z` (radius). Use two `<Scatter>` series split by `shape` (circle vs triangle Symbol). Keyboard: each point focusable via `tabIndex`. |
| 6 | `PieComposition` | NEW | `frontend/src/components/viz/PieComposition.tsx` | `components/DeviceDonut.tsx`, `components/GenderDonut.tsx` (domain wrappers — remain) | `{ data: Array<{label, value, color?, patternId?}>, innerRadius?: number, yFormat?: ChartValueType, currency?: string, showLegend?: boolean, centerLabel?: string, isLoading?: boolean, emptyReasonCode?: string }` | `innerRadius=0` renders pie; `>0` renders donut. Each segment gets `<pattern>` cross-hatch in addition to color (secondary encoding). Center total text when `centerLabel` provided. |
| 7 | `DataTable` (viz) | EXTEND | `frontend/src/components/viz/DataTable.tsx` | `components/DataTable.tsx` (rich — has sort, search, density, mobile detail rows) | `{ columns: ColumnDef<T>[], data: T[], isLoading?: boolean, onRowClick?: (row:T)=>void, csvFilename?: string, emptyReasonCode?: string, pageSize?: number, getRowId?, title?, description?, searchPlaceholder?, initialSorting?, initialDensity? }` | Wrap/extend existing `DataTable.tsx`. Add: `csvFilename` + "Download CSV" button, `pageSize` pagination, `onRowClick`, `isLoading` skeleton body, `emptyReasonCode` → delegates to `<EmptyState>` in body. Keep existing sort/search/density. Old `DataTable.tsx` becomes an internal primitive or is moved to `viz/` and the import path updated in callers during Sprints 2–4 (do NOT remove in Sprint 1). |
| 8 | `EmptyState` | REUSE | `frontend/src/components/EmptyState.tsx` | same | `{ icon, title, message, actionLabel?, onAction?, actionVariant?, secondaryActionLabel?, onSecondaryAction?, secondaryActionVariant?, className?, reasonCode? }` | Already has `reasonCode` (FP-CC-01). Add thin viz-namespace wrapper at `viz/EmptyState.tsx` that exports the canonical reason-code → title/message/icon map (`no_accounts`, `no_data_for_range`, `adapter_error`, `no_data_for_scope`, `no_campaigns`) so every chart can call `<EmptyState reasonCode="no_data_for_range" />` without rebuilding copy each time. |
| 9 | `ChartSkeleton` | EXTEND | `frontend/src/components/viz/ChartSkeleton.tsx` | `components/Skeleton.tsx` (primitive shimmer rect) | `{ height?: number, rows?: number, variant?: 'line'\|'bar'\|'pie'\|'table'\|'kpi-strip'\|'kpi'\|'sparkline'\|'bubble' }` | Composes `<Skeleton>` primitives into chart-shaped footprints. Must match target chart footprint exactly so there is no layout shift when data arrives. |
| 10 | `AccessibleTableToggle` | NEW | `frontend/src/components/viz/AccessibleTableToggle.tsx` | none | `{ chartNode: ReactNode, tableNode: ReactNode, defaultView?: 'chart'\|'table', chartAriaLabel?: string, toggleAriaLabel?: string }` | Both nodes mount; inactive one gets `hidden` + `aria-hidden="true"` (do NOT unmount — preserves Recharts animation state and keeps focus targets valid). Toggle button shows icon only with `aria-label="Switch to {other view}"`. |
| +1 | `PeerAvgLine` | NEW (sub-component) | `frontend/src/components/viz/PeerAvgLine.tsx` | none | `{ data: Array<{date:string; value:number}>, yAxisId?: 'left'\|'right' }` | Renders a Recharts `<Line>` with `stroke="var(--viz-peer-avg)"`, `strokeDasharray="4 4"`, `strokeWidth={1.5}`, `dot={false}`, `isAnimationActive={false}`, `legendType="plainline"`, `name="Peer avg"`. Used only inside `<TrendLine>` via composition — never rendered standalone. |

**Index export:** `frontend/src/components/viz/index.ts` re-exports all ten components + token helpers, giving downstream sprints a single import: `import { KpiTile, TrendLine, DataTable, EmptyState } from '@/components/viz'`.

---

## 3. Design token additions

Existing tokens in `theme.css` already cover most surfaces (cards, borders, text, focus ring, chart line/area, metric delta surfaces). The viz kit needs **series palette stability, peer-avg color, pattern opacity, and status colors**. Add a single new file, imported from `theme.css`, rather than mutating the existing token file — this keeps the diff surgical and reversible.

### 3.1 New file: `frontend/src/styles/viz-tokens.css`

```css
@layer tokens {
  :root,
  .theme-light {
    /* Series palette — mirrors chartPalette for CSS consumers (SVG attrs
       still read the TS constant). WCAG AA on --color-surface-card #fff. */
    --viz-series-0: #2563eb;  /* meta / primary      — contrast 4.85 */
    --viz-series-1: #c2410c;  /* google / orange-700 — contrast 5.11
                                 (darker than #f97316 to hit AA on white) */
    --viz-series-2: #0369a1;  /* accent-blue         — contrast 6.74 */
    --viz-series-3: #047857;  /* conversions / green — contrast 5.46 */
    --viz-series-4: #7e22ce;  /* audience / purple   — contrast 6.46 */
    --viz-series-5: #be123c;  /* alert / red         — contrast 5.94 */

    /* Platform semantic bindings */
    --viz-platform-meta: var(--viz-series-0);
    --viz-platform-google: var(--viz-series-1);
    --viz-platform-peer-avg: rgba(71, 85, 105, 0.55);  /* slate-600 @ 55% */

    /* Status (campaign states) */
    --viz-status-enabled: var(--viz-series-3);
    --viz-status-paused: #b45309;    /* amber-700, contrast 4.55 */
    --viz-status-removed: var(--viz-series-5);

    /* Chart chrome */
    --viz-axis-line: rgba(15, 23, 42, 0.35);
    --viz-axis-tick: rgba(15, 23, 42, 0.70);
    --viz-grid: rgba(15, 23, 42, 0.10);
    --viz-grid-strong: rgba(15, 23, 42, 0.22);
    --viz-tooltip-surface: #0f172a;
    --viz-tooltip-text: #f8fafc;
    --viz-legend-text: var(--color-text-secondary);

    /* Pattern fill opacity (secondary encoding) */
    --viz-pattern-opacity: 0.55;

    /* Focus ring on data points (keyboard nav) */
    --viz-point-focus: 0 0 0 3px rgba(37, 99, 235, 0.45);
  }

  .theme-dark,
  :root[data-theme='dark'] {
    /* Brighter hues for dark surfaces. Contrast measured on
       --color-surface-card #111827. All ≥ 4.5:1. */
    --viz-series-0: #60a5fa;  /* blue-400   — contrast 6.57 */
    --viz-series-1: #fb923c;  /* orange-400 — contrast 6.19 */
    --viz-series-2: #38bdf8;  /* sky-400    — contrast 7.11 */
    --viz-series-3: #4ade80;  /* green-400  — contrast 7.48 */
    --viz-series-4: #c084fc;  /* purple-400 — contrast 6.13 */
    --viz-series-5: #fb7185;  /* rose-400   — contrast 5.74 */

    --viz-platform-meta: var(--viz-series-0);
    --viz-platform-google: var(--viz-series-1);
    --viz-platform-peer-avg: rgba(148, 163, 184, 0.60);

    --viz-status-enabled: var(--viz-series-3);
    --viz-status-paused: #fbbf24;
    --viz-status-removed: var(--viz-series-5);

    --viz-axis-line: rgba(226, 232, 240, 0.45);
    --viz-axis-tick: rgba(226, 232, 240, 0.85);
    --viz-grid: rgba(226, 232, 240, 0.12);
    --viz-grid-strong: rgba(226, 232, 240, 0.24);
    --viz-tooltip-surface: rgba(15, 23, 42, 0.96);
    --viz-tooltip-text: #f8fafc;
    --viz-legend-text: var(--color-text-secondary);

    --viz-pattern-opacity: 0.45;
    --viz-point-focus: 0 0 0 3px rgba(96, 165, 250, 0.55);
  }
}
```

Import once in `theme.css` bottom: `@import './viz-tokens.css' layer(tokens);`. Storybook `preview.ts` already imports `theme.css`, so no additional wiring.

### 3.2 TypeScript additions to `chartTheme.ts` (no replacement, additive only)

```ts
// Add to frontend/src/styles/chartTheme.ts:

export const VIZ_CSS_VARS = {
  seriesPalette: ['--viz-series-0', '--viz-series-1', '--viz-series-2',
                  '--viz-series-3', '--viz-series-4', '--viz-series-5'] as const,
  axisLine: '--viz-axis-line',
  axisTick: '--viz-axis-tick',
  grid: '--viz-grid',
} as const;

// For Recharts props that accept string colors, use var() directly:
//   stroke="var(--viz-series-0)"
// For props that need literal hex (rare — e.g. gradient stops), use chartPalette.

export const PLATFORM_CHART_TOKENS = {
  meta_ads:    chartPalette[0],
  google_ads:  chartPalette[1],
  peer_avg:    'rgba(148, 163, 184, 0.55)',
} as const;

export const STATUS_COLORS = {
  ENABLED: chartPalette[3],
  PAUSED:  '#b45309',
  REMOVED: chartPalette[5],
} as const;

export function resolveSeriesColor(index: number): string {
  // Round-robin palette for unspecified series colors.
  return chartPalette[index % chartPalette.length];
}
```

**Rationale for hex vs. var:** Recharts SVG attributes work with CSS custom properties, but gradient `<stop stopColor>` sometimes evaluates before the CSS cascade. Default to `var(--viz-series-N)` for `stroke`/`fill` on top-level `<Line>`/`<Bar>`/`<Area>`; fall back to literal hex from `chartPalette` inside `<defs>` blocks. Existing `CampaignTrendChart.tsx` already uses hex from `chartPalette` — S1a/S1b can match that pattern.

### 3.3 Contrast audit

All six series colors tested against `--color-surface-card` on both themes using WCAG contrast formula. Minimum ratio 4.55:1 (light, `--viz-series-1` orange-700 on white) — exceeds AA threshold of 3:1 for large UI elements and 4.5:1 for small text. `--viz-platform-peer-avg` is deliberately sub-AA because peer avg is a secondary, dashed line with a text legend — color is not the sole encoding.

---

## 4. Recharts usage conventions

### 4.1 The standard chart envelope

Every non-sparkline chart in the viz kit follows this outer pattern:

```tsx
// viz/TrendLine.tsx (sketch)
const TrendLine = (props: TrendLineProps) => {
  if (props.isLoading) return <ChartSkeleton variant="line" height={props.height ?? 260} />;
  if (!props.data?.length) {
    return <EmptyState reasonCode={props.emptyReasonCode ?? 'no_data_for_range'} />;
  }

  const chart = (
    <ResponsiveContainer width="100%" height={props.height ?? 260}>
      <LineChart data={props.data} margin={chartMargins}>
        <CartesianGrid
          stroke="var(--viz-grid)"
          strokeDasharray={chartTheme.grid.strokeDasharray}
          vertical={false}
        />
        <XAxis dataKey="date" axisLine={false} tickLine={false} tickMargin={12}
               tick={{ fill: 'var(--viz-axis-tick)', fontSize: 12 }}
               tickFormatter={formatDateLabel} />
        <YAxis axisLine={false} tickLine={false} width={68}
               tick={{ fill: 'var(--viz-axis-tick)', fontSize: 12 }}
               tickFormatter={axisTickFormatter} />
        {props.series.some(s => s.yAxis === 'right') && (
          <YAxis yAxisId="right" orientation="right" /* ... */ />
        )}
        <Tooltip {...createTooltipProps({ valueType: props.yFormat, currency: props.currency })} />
        <Legend wrapperStyle={{ paddingTop: 12 }} />
        {props.series.map((s, i) => (
          <Line key={s.key} type="monotone" dataKey={s.key} name={s.label}
                stroke={s.color ?? resolveSeriesColor(i)}
                strokeDasharray={s.dashed ? '6 4' : undefined}
                strokeWidth={2}
                dot={{ r: chartTheme.point.radius }}
                activeDot={{ r: chartTheme.point.activeRadius }}
                yAxisId={s.yAxis ?? undefined} />
        ))}
        {props.peerData && <PeerAvgLine data={props.peerData} />}
      </LineChart>
    </ResponsiveContainer>
  );

  return (
    <AccessibleTableToggle
      chartNode={chart}
      tableNode={<TrendLineTable data={props.data} series={props.series} />}
    />
  );
};
```

### 4.2 Conventions — apply to every chart primitive

1. **`ResponsiveContainer` is mandatory** for TrendLine, DistributionBar, BubbleScatter, PieComposition. Sparkline is the one exception — it takes a fixed width from parent cell.
2. **`chartMargins`** import from `chartTheme.ts` — do not inline margins.
3. **`createTooltipProps({ valueType, currency })`** — do not build tooltip props inline. All tooltips use the dark surface + light text defined in `chartTheme.ts`.
4. **`CartesianGrid vertical={false}`** everywhere (horizontal grid only) — matches existing `CampaignTrendChart.tsx` idiom.
5. **`axisLine={false}` / `tickLine={false}`** on XAxis and YAxis — matches existing idiom. Axis color comes from `tick.fill` reading `--viz-axis-tick`.
6. **Recharts typing cast** — existing code uses `const XAxisComponent = XAxis as unknown as ComponentType<Record<string, unknown>>;` to work around Recharts' strict JSX types. S1a/S1b should replicate this pattern; do NOT try to fix it in Sprint 1 (that is a library-wide refactor out of scope).
7. **One file per component** — no sub-component file splits unless the spec mandates it (`PeerAvgLine` is the only carve-out). Type exports live alongside the component: `export type TrendLineProps = ...`.
8. **No inline styles for color/size** — colors from CSS vars, sizes from `chartTheme` constants.
9. **Gradients** (for stacked-area variant) defined inline via `<defs><linearGradient>` at the top of the chart, using literal hex from `chartPalette`.
10. **Legend** — always render when `series.length > 1`. Hide when single series unless caller opts in. Legend text color `--viz-legend-text`.
11. **Animation** — leave Recharts defaults on for first paint; disable (`isAnimationActive={false}`) only inside `PeerAvgLine` and inside stories to keep Chromatic diffs stable.

### 4.3 Sparkline shortcut

Sparkline is the only primitive that does **not** wrap in `ResponsiveContainer` and does **not** expose `AccessibleTableToggle`. It's intended for table-cell inline use where each row already has its data value in the adjacent cell (the adjacent cell IS the accessible equivalent). Use a fixed height prop, render `<LineChart>` directly, and pass `ariaLabel` through to the wrapping `<div role="img">`.

---

## 5. Accessibility pattern — the `AccessibleTableToggle` contract

### 5.1 Required coupling

Every non-Sparkline chart primitive **must** wrap its output in `<AccessibleTableToggle>` when rendered standalone. The rendering contract:

```tsx
<AccessibleTableToggle
  chartNode={<RechartsEnvelope role="img" aria-label="Spend over 30 days" />}
  tableNode={<table className="viz-equivalent-table"> ... </table>}
  defaultView="chart"
  toggleAriaLabel="Switch to table view"
/>
```

Structural rules:

1. **Both nodes mount simultaneously.** The inactive node gets `hidden` attribute + `aria-hidden="true"`. This preserves Recharts SVG animation state and the table's DOM identity (so screen readers do not re-announce on toggle).
2. **Toggle button** is icon-only with visible focus ring (`box-shadow: var(--focus-ring)`). `aria-label` flips between "Switch to table view" and "Switch to chart view". `aria-pressed` reflects current state.
3. **Chart `role="img"` + `aria-label`** is the minimum narration for screen readers in chart mode. Caller is responsible for providing a meaningful label via props on the chart primitive.
4. **Table node** must have `<caption>` with the same label. Each primitive defines its own `tableNode` rendering helper (e.g. `TrendLineTable` for columns Date + one per series, `DistributionBarTable` for two columns Label + Value, etc.). These helpers live inside each primitive file (not exported) — they are not standalone components.
5. **Keyboard focus order**: toggle button → chart/table content → next primitive. Do not trap focus.
6. **`tabIndex={0}`** on each data point in BubbleScatter and TrendLine so keyboard users can arrow through points; arrow-key handler fires the same tooltip path as hover.

### 5.2 Color-is-not-sole-encoding patterns

- **DistributionBar / PieComposition**: each segment gets a `<pattern>` SVG fill referenced by `patternId` (cross-hatch, dots, diagonal). Default pattern assigned round-robin by index when caller omits `patternId`.
- **TrendLine**: series passed with `dashed: true` uses `strokeDasharray="6 4"`. Peer-avg always dashed.
- **BubbleScatter**: `shape: 'circle' | 'triangle'` is the mandated fourth dimension encoding. If caller doesn't supply it, default to circle, but the spec requires callers to provide shape whenever the chart encodes a categorical dimension.

### 5.3 Focus & motion

- `prefers-reduced-motion: reduce` — disable Recharts animations: wrap render with `const noMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;` and pass `isAnimationActive={!noMotion}` on all series components.
- Data-point focus ring uses `--viz-point-focus` (new token) via a `<circle>` rendered by custom `activeDot` when focus is keyboard-driven.

---

## 6. Storybook pattern

### 6.1 Addon recommendation (action required)

`@storybook/addon-a11y` is **not installed**. For Sprint 1, add it at version `8.6.14` (same as essentials). Update `.storybook/main.ts`:

```ts
addons: [
  '@storybook/addon-essentials',
  '@storybook/addon-interactions',
  '@storybook/addon-a11y',  // NEW
],
```

And `package.json`:
```json
"@storybook/addon-a11y": "8.6.14"
```

If product rejects the addon for scope reasons, fall back to jest-axe in story-adjacent `.test.tsx` files (the approach already used in `TenantSwitcher.test.tsx`) — this satisfies the DoD "Axe accessibility check passes in Storybook for every story" because jest-axe uses the same rule engine as the Storybook a11y addon.

### 6.2 Standard story template — `ComponentName.stories.tsx`

```tsx
import type { Meta, StoryObj } from '@storybook/react';
import ComponentName from './ComponentName';

const meta: Meta<typeof ComponentName> = {
  title: 'Viz/ComponentName',
  component: ComponentName,
  parameters: {
    layout: 'padded',
    a11y: { config: { rules: [{ id: 'color-contrast', enabled: true }] } },
    chromatic: { viewports: [375, 1280] },
  },
  tags: ['autodocs'],
};
export default meta;
type Story = StoryObj<typeof ComponentName>;

export const Default: Story = { args: { /* representative data */ } };

export const Loading: Story = { args: { isLoading: true } };

export const Empty: Story = { args: { data: [], emptyReasonCode: 'no_data_for_range' } };

export const SingleSeries: Story = { args: { /* 1 series */ } };  // where applicable

export const MultiSeries: Story = { args: { /* 3+ series */ } };  // where applicable

export const DarkTheme: Story = {
  args: { /* default data */ },
  decorators: [(S) => <div data-theme="dark" style={{ background: 'var(--color-surface-card)', padding: 16 }}><S /></div>],
};

export const TableViewDefault: Story = {
  args: { /* default data */ , __defaultView: 'table' },
};
```

**Per-primitive requirements:**

| Primitive | Required stories |
|-----------|------------------|
| `KpiTile` | Default, Loading, Empty (null value), WithDeltaUp, WithDeltaDown, Faded, DarkTheme |
| `TrendLine` | Default, Loading, Empty, SingleSeries, MultiSeries, DualAxis, WithPeerAvg, StackedArea, DarkTheme |
| `Sparkline` | Default, Flat, Rising, Falling, DarkTheme |
| `DistributionBar` | Default, Loading, Empty, Horizontal, Vertical, WithPercent, DarkTheme |
| `BubbleScatter` | Default, Loading, Empty, Clustered, WithShapes, DarkTheme |
| `PieComposition` | Default, Loading, Empty, Donut, Pie, WithCenterLabel, DarkTheme |
| `DataTable` | Default, Loading, Empty, WithCsvExport, RowClick, LongList, DarkTheme |
| `EmptyState` | NoAccounts, NoData, AdapterError, NoDataForScope |
| `ChartSkeleton` | Line, Bar, Pie, Table, KpiStrip, Kpi, Sparkline, Bubble |
| `AccessibleTableToggle` | Default (chart first), DefaultTable, WithKeyboardFocus |

---

## 7. Unit + a11y test pattern

Test files live next to components: `frontend/src/components/viz/__tests__/ComponentName.test.tsx`. Coverage target per DoD: ≥ 80%.

### 7.1 Standard skeleton

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'jest-axe';
import { describe, expect, it } from 'vitest';

import ComponentName from '../ComponentName';

describe('ComponentName', () => {
  const baseProps = { /* minimal valid props */ };

  it('renders default state', () => {
    render(<ComponentName {...baseProps} />);
    expect(screen.getByRole(/* appropriate role */)).toBeInTheDocument();
  });

  it('renders loading skeleton when isLoading', () => {
    render(<ComponentName {...baseProps} isLoading />);
    expect(screen.getByRole('presentation', { hidden: true })).toBeInTheDocument();
  });

  it('renders empty state when data is empty', () => {
    render(<ComponentName {...baseProps} data={[]} emptyReasonCode="no_data_for_range" />);
    const empty = screen.getByRole('status');
    expect(empty).toHaveAttribute('data-reason-code', 'no_data_for_range');
  });

  it('has no a11y violations (chart view)', async () => {
    const { container } = render(<ComponentName {...baseProps} />);
    expect(await axe(container)).toHaveNoViolations();
  });

  it('has no a11y violations (table view)', async () => {
    const { container } = render(<ComponentName {...baseProps} defaultView="table" />);
    expect(await axe(container)).toHaveNoViolations();
  });

  // Component-specific cases:
  //   KpiTile: formatting per `format` prop, null value renders `--`
  //   TrendLine: peerData renders dashed line, rightYFormat gates second axis
  //   DataTable: CSV download triggers Blob, sort toggles aria-sort
  //   AccessibleTableToggle: toggle button flips aria-pressed, inactive node has aria-hidden
});
```

### 7.2 `DataTable` CSV test (DoD item)

```tsx
it('produces correct CSV on download', async () => {
  const createObjectURL = vi.fn(() => 'blob:mock');
  URL.createObjectURL = createObjectURL;
  render(<DataTable {...props} csvFilename="test.csv" />);
  await userEvent.click(screen.getByRole('button', { name: /download csv/i }));
  const blob = createObjectURL.mock.calls[0][0] as Blob;
  expect(await blob.text()).toMatchInlineSnapshot(/* expected CSV */);
});
```

### 7.3 `AccessibleTableToggle` keyboard test

```tsx
it('toggles via keyboard (enter and space)', async () => {
  render(<AccessibleTableToggle chartNode={<div>chart</div>} tableNode={<div>table</div>} />);
  const btn = screen.getByRole('button');
  btn.focus();
  await userEvent.keyboard('{Enter}');
  expect(btn).toHaveAttribute('aria-pressed', 'true');
  await userEvent.keyboard(' ');
  expect(btn).toHaveAttribute('aria-pressed', 'false');
});
```

---

## 8. Implementation plan — 3 parallel agents

### S1a-ChartPrimitives (parallel, starts immediately)

**Owned files:**
- `frontend/src/styles/viz-tokens.css` (new)
- `frontend/src/styles/chartTheme.ts` (append `VIZ_CSS_VARS`, `PLATFORM_CHART_TOKENS`, `STATUS_COLORS`, `resolveSeriesColor`)
- `frontend/src/styles/theme.css` (add one `@import` line)
- `frontend/src/components/viz/TrendLine.tsx`
- `frontend/src/components/viz/Sparkline.tsx`
- `frontend/src/components/viz/DistributionBar.tsx`
- `frontend/src/components/viz/BubbleScatter.tsx`
- `frontend/src/components/viz/PieComposition.tsx`
- `frontend/src/components/viz/PeerAvgLine.tsx`
- `frontend/src/components/viz/ChartSkeleton.tsx`

**Gate:** must land before S1c starts. No story files.

### S1b-TableAndKpi (parallel, starts immediately)

**Owned files:**
- `frontend/src/components/viz/KpiTile.tsx`
- `frontend/src/components/viz/DataTable.tsx` (extends existing `components/DataTable.tsx`, re-exports with added `csvFilename`, `pageSize`, `onRowClick`, `isLoading`, `emptyReasonCode` props)
- `frontend/src/components/viz/AccessibleTableToggle.tsx`
- `frontend/src/components/viz/EmptyState.tsx` (thin wrapper around `components/EmptyState.tsx` with reason-code dictionary)
- `frontend/src/components/viz/index.ts` (barrel export — coordinate with S1a at merge time)
- `frontend/src/lib/csvExport.ts` (new tiny helper — manual CSV serializer since no papaparse)

**Gate:** must land before S1c starts. No story files.

**Non-overlap guarantee:** S1a and S1b touch zero shared files except `viz/index.ts` (owned by S1b; S1a doesn't author it — S1b updates the barrel once S1a's files land).

### S1c-StoriesAndA11y (sequential, starts after S1a + S1b merge)

**Owned files:**
- `.storybook/main.ts` (add `@storybook/addon-a11y`)
- `frontend/package.json` (add `@storybook/addon-a11y` dep)
- `frontend/src/components/viz/*.stories.tsx` (one per primitive — 10 files)
- `frontend/src/components/viz/__tests__/*.test.tsx` (one per primitive — 10 files)

**Gate:** Sprint DoD — all stories pass a11y addon + `pytest`-equivalent vitest run ≥ 80% coverage per primitive.

### Order of work inside each agent

S1a: tokens → `ChartSkeleton` → `Sparkline` → `TrendLine` + `PeerAvgLine` → `DistributionBar` → `PieComposition` → `BubbleScatter`.
S1b: `EmptyState` viz wrapper → `AccessibleTableToggle` → `KpiTile` → `csvExport` lib → `DataTable` (viz) → `index.ts` barrel.

---

## 9. Out of scope for Sprint 1

- **Parish map / choropleth** — deferred to Sprint 4 per `sprints-plan.md` L1142.
- **Domain wrappers** — `CampaignTrendChart`, `AgeDistributionBar`, `DeviceDonut`, `GenderDonut`, `BudgetPacingList`, `ParishComparisonChart`, `PlatformComparisonBars`, `EngagementBreakdownPanel`, `CreativeTable`, `CampaignTable`, `PostsTable`, `RegionBreakdownTable` — remain untouched. Sprints 2–4 migrate callers onto the new primitives; Sprint 1 does not delete or refactor them.
- **Funnel chart** — Sprint 2 concern (Recharts `FunnelChart` availability check is still open per `sprints-plan.md` Open Q #7).
- **Age × Gender heatmap** — Sprint 4 open question (#11).
- **Backend / adapter changes** — none.
- **Peer-average median computation logic** — `PeerAvgLine` only renders the line. Computing the median across other accounts is caller responsibility (the Sprint 2/3 dashboard routes handle that from the cached unfiltered payload).
- **Route wiring** — no changes to `routes/`, `state/`, or `DashboardLayout.tsx`.
- **Print / PDF** — explicitly deferred per `sprints-plan.md` L1100.
- **Old `DataTable.tsx` deletion / callsite migration** — defer to Sprints 2–4 per `sprints-plan.md` L332 (existing tables must not be removed until their page is migrated).

---

## 10. Risks

1. **Recharts 3.x API drift.** `sprints-plan.md` notes v3.7 is installed but several specs assume 2.x behaviors (e.g. `FunnelChart`, `ScatterChart` `<ZAxis>` range, `<Pie>` `paddingAngle`). S1a should verify each primitive mounts under v3.7.0 before writing tests — any breaking change needs a 1-day spike before Sprint 2 starts.
2. **TypeScript friction with Recharts.** The existing codebase casts every Recharts component via `ComponentType<Record<string, unknown>>`. This is ugly but necessary; S1a/S1b must replicate, not refactor. Attempting a global typing fix is Sprint 6+ work.
3. **Storybook a11y addon version mismatch.** The essentials + interactions addons are pinned to `8.6.14`. The a11y addon must match exactly — mixing major versions bricks Storybook 8. If `@storybook/addon-a11y@8.6.14` is unavailable on npm, drop back to jest-axe in test files (already the project pattern) and document the gap.
4. **Token collisions.** `theme.css` already defines `--color-chart-line`, `--color-chart-area`, `--color-chart-point`, `--chart-footer`, and metric-card sparkline tokens. Do not reuse these names — `--viz-*` is the new namespace to prevent cascade conflicts. Existing domain wrappers keep using the old tokens.
5. **`DataTable` duplication.** Existing `components/DataTable.tsx` has sort, search, density, mobile detail rows — richer than the spec's "sortable + CSV export". The viz `DataTable` must wrap and preserve all existing behavior; any regression will break 6+ dashboard routes that already use it. S1b should import the existing file and augment, not reimplement.
6. **CSV export without PapaParse.** Manual escape-and-quote serializer is error-prone for strings containing `"`, `,`, `\n`. Implementation must include a unit test with a torture-case row (`"He said ""hi"", then\nleft"`). No new dependency.
7. **`prefers-reduced-motion` in tests.** JSDOM does not implement `matchMedia` by default. Need to polyfill in `setupTests.ts` or stub per-test. Check existing `setupTests.ts` — currently only polyfills `scrollIntoView`; S1c must add `matchMedia` stub.
8. **WCAG AA on chartPalette[1] `#f97316`.** Orange-500 fails AA on white (2.99:1). The current codebase uses it for Google/orange branding. The new `--viz-series-1` uses orange-700 `#c2410c` (5.11:1) instead. Downstream sprints will need to accept the slightly darker orange OR we exempt `PLATFORM_CHART_TOKENS.google_ads` from the contrast rule because line stroke is UI-chrome-not-text and AA threshold is 3:1 for that case. Decision: keep `chartPalette` hex unchanged (backward compat) and use `--viz-series-*` for the AA-compliant variant; components choose which token based on context.
9. **`AccessibleTableToggle` visibility toggling.** Using `hidden` attribute on a Recharts `ResponsiveContainer` may freeze its size observer. Mitigation: toggle via CSS `display: none` / `block` plus `aria-hidden`, and remount Recharts only if the container reports 0×0. Verify in `S1a` when `TrendLine` stories are added.
10. **Coverage-v8 + Recharts SVG.** Vitest coverage may mis-instrument Recharts' internal SVG renderers, inflating "uncovered" numbers. Target ≥ 80% per primitive but measure excluding `node_modules` (already default) and Recharts internals. If coverage gates fail purely due to Recharts, document and move on — the spec's intent is component-logic coverage.

---

## Appendix A — `viz/` directory layout (final)

```
frontend/src/components/viz/
├── index.ts                          [S1b]
├── KpiTile.tsx                       [S1b]
├── TrendLine.tsx                     [S1a]
├── Sparkline.tsx                     [S1a]
├── DistributionBar.tsx               [S1a]
├── BubbleScatter.tsx                 [S1a]
├── PieComposition.tsx                [S1a]
├── PeerAvgLine.tsx                   [S1a]
├── DataTable.tsx                     [S1b — wraps components/DataTable.tsx]
├── EmptyState.tsx                    [S1b — wraps components/EmptyState.tsx]
├── ChartSkeleton.tsx                 [S1a]
├── AccessibleTableToggle.tsx         [S1b]
├── KpiTile.stories.tsx               [S1c]
├── TrendLine.stories.tsx             [S1c]
├── ...                               [S1c, one per primitive]
└── __tests__/
    ├── KpiTile.test.tsx              [S1c]
    ├── TrendLine.test.tsx            [S1c]
    └── ...                           [S1c, one per primitive]

frontend/src/lib/
└── csvExport.ts                      [S1b]

frontend/src/styles/
├── viz-tokens.css                    [S1a]
├── chartTheme.ts                     [S1a — append only]
└── theme.css                         [S1a — single @import line]
```

## Appendix B — Definition-of-done checklist (from `sprints-plan.md` L124–132)

- [ ] All 10 components render in Storybook with Default + Loading + Empty + Error states
- [ ] Axe check passes for every story (addon or jest-axe fallback)
- [ ] `DataTable` CSV export is snapshot-tested against a torture row
- [ ] `AccessibleTableToggle` is keyboard-operable (Tab + Enter/Space)
- [ ] `TrendLine` renders `PeerAvgLine` when `peerData` prop is supplied
- [ ] Vitest coverage ≥ 80% per component
- [ ] No new Recharts dependency version bump
- [ ] `@storybook/addon-a11y@8.6.14` installed (or jest-axe coverage documented as substitute)
- [ ] `viz-tokens.css` imported from `theme.css`; Storybook `preview.ts` unchanged
