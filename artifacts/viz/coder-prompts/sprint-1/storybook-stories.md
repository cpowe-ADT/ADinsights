# Storybook Stories for Shared Viz Kit

**Sprint:** 1
**Estimated size:** S
**Depends on:** all Sprint 1 components (KpiTile, TrendLine, Sparkline, DistributionBar, BubbleScatter, PieComposition, DataTable, ChartSkeleton, AccessibleTableToggle)
**Blocks:** nothing (stories are dev tooling only)
**Role needed:** frontend-engineer

## Context

Storybook 8.6.14 is already installed with `@storybook/react-vite`, `@storybook/addon-essentials`, and `@storybook/addon-interactions`. The `.storybook/` config lives at `frontend/.storybook/`. Stories provide visual regression baseline, interactive documentation, and dev-time a11y checking. Note: `@storybook/addon-a11y` is NOT installed — a11y is verified via `jest-axe` in vitest instead.

## Inputs already in the repo (do not re-invent)

- `frontend/.storybook/main.ts`: Storybook config. Do not modify.
- `frontend/.storybook/preview.ts` and `preview.tsx`: global decorators. Do not modify unless you need to add a global CSS import.
- All Sprint 1 component files.

## Deliverable

- **File(s) to create**:
  - `frontend/src/components/viz/KpiTile.stories.tsx`
  - `frontend/src/components/viz/TrendLine.stories.tsx`
  - `frontend/src/components/viz/Sparkline.stories.tsx`
  - `frontend/src/components/viz/DistributionBar.stories.tsx`
  - `frontend/src/components/viz/BubbleScatter.stories.tsx`
  - `frontend/src/components/viz/PieComposition.stories.tsx`
  - `frontend/src/components/viz/DataTable.stories.tsx`
  - `frontend/src/components/viz/ChartSkeleton.stories.tsx`
  - `frontend/src/components/viz/AccessibleTableToggle.stories.tsx`

## Required story variants per component

Each component must have these variants:

1. **Default** — typical production data
2. **Loading** — `isLoading=true`
3. **Empty** — empty data with a `reasonCode`
4. **WithError** — `emptyReasonCode="adapter_error"` (where applicable)

Additional variants per component:

- `KpiTile`: Positive change, Negative change, Null value, Currency format, Percent format
- `TrendLine`: SingleSeries, MultiSeries (3 accounts), DualAxis, StackedArea, WithPeerAverage
- `DistributionBar`: SingleValue, PairedBars, ShowPercent, VerticalLayout
- `PieComposition`: Pie, Donut, 6 segments
- `BubbleScatter`: CirclesOnly, MixedShapes, WithClickHandler
- `DataTable`: WithRowClick, WithCSVExport, WithInlineSparkline, LargePaginated

## Story structure (use CSF3 format)

```typescript
// Example: KpiTile.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';
import { KpiTile } from './KpiTile';

const meta: Meta<typeof KpiTile> = {
  title: 'Viz/KpiTile',
  component: KpiTile,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
};
export default meta;

type Story = StoryObj<typeof KpiTile>;

export const Default: Story = {
  args: {
    label: 'Total Spend',
    value: 1234567,
    format: 'currency',
    currency: 'JMD',
    change: 0.12,
  },
};

export const Loading: Story = {
  args: {
    label: 'Total Spend',
    value: null,
    format: 'currency',
    isLoading: true,
  },
};

export const Empty: Story = {
  args: {
    label: 'Total Spend',
    value: null,
    format: 'currency',
    reasonCode: 'no_data_for_range',
  },
};

export const NegativeChange: Story = {
  args: {
    label: 'CTR',
    value: 0.023,
    format: 'percent',
    change: -0.08,
  },
};
```

## Mock data constants

Create a shared mock data file for stories to keep them DRY:

**File:** `frontend/src/components/viz/__tests__/mockData.ts`

```typescript
export const trendData = Array.from({ length: 30 }, (_, i) => ({
  date: new Date(2026, 0, i + 1).toISOString().slice(0, 10),
  spend_meta: Math.round(1000 + Math.random() * 500),
  spend_google: Math.round(800 + Math.random() * 400),
}));

export const sparklineData = Array.from({ length: 14 }, (_, i) => ({
  date: new Date(2026, 0, i + 1).toISOString().slice(0, 10),
  value: Math.round(100 + Math.random() * 50),
}));

export const distributionData = [
  { label: 'Meta', value: 5000 },
  { label: 'Google Ads', value: 3200 },
  { label: 'Instagram', value: 1800 },
];

export const pieData = [
  { label: 'Search', value: 4500 },
  { label: 'Display', value: 2100 },
  { label: 'Video', value: 1800 },
  { label: 'Shopping', value: 900 },
];

export const bubbleData = [
  {
    id: 'c1',
    label: 'Brand Campaign',
    x: 5000,
    y: 3.2,
    z: 120000,
    shape: 'circle' as const,
  },
  {
    id: 'c2',
    label: 'Retargeting',
    x: 2000,
    y: 5.1,
    z: 60000,
    shape: 'triangle' as const,
  },
  {
    id: 'c3',
    label: 'Prospecting',
    x: 8000,
    y: 1.8,
    z: 200000,
    shape: 'circle' as const,
  },
];
```

## Definition of Done

- [ ] All 9 story files created
- [ ] Each component has at minimum Default, Loading, Empty stories
- [ ] Stories import from `mockData.ts` — no inline large arrays
- [ ] `npx storybook dev` starts without errors (check by running `cd frontend && npx storybook dev --ci --smoke-test`)
- [ ] `autodocs` tag present so Storybook auto-generates docs pages
- [ ] Lint clean: `cd frontend && npm run lint`
- [ ] Build clean: `cd frontend && npm run build`

## Out of scope

- Do NOT install `@storybook/addon-a11y` — use jest-axe in vitest instead
- Do NOT write interaction tests (`play` functions) — interactions addon is available but optional for Sprint 1
- Do NOT write visual regression tests
