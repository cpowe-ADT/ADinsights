# Google Ads PMax Tab — Visualization Upgrade

**Sprint:** 3
**Estimated size:** S
**Depends on:** sprint-1/\* (all kit components)
**Blocks:** none
**Role needed:** frontend-engineer

## Context

The PMax (Performance Max) tab in the Google Ads workspace. Endpoint: `GET /api/google-ads/pmax-asset-groups/`. Shows asset group performance with a Recharts `Treemap` (spend × ROAS color intensity). Treemap IS available in Recharts 3.x.

## Inputs already in the repo (do not re-invent)

- PMax asset group row fields: `asset_group_id, asset_group_name, asset_group_status, spend, impressions, clicks, conversions, cpa, roas`
- All Sprint 1 viz components.
- `frontend/src/styles/chartTheme.ts`: `chartPalette[1]` = `#f97316` (orange, Google Ads color).

## Deliverable

- **File(s) to create/modify**: identify the PMax tab component and modify it.

- **Data binding**:
  - KPI strip (3 tiles): Total Asset Groups = count rows; Total Cost = sum(spend); Total Conv = sum(conversions).
  - Treemap: `rows` mapped to Recharts `<Treemap>` data format. Each node: `{ name: asset_group_name, size: spend, roas: roas }`. Color intensity: map `roas` to opacity — `opacity = Math.min(1.0, Math.max(0.2, roas / 3))` (ROAS 0 → 0.2 opacity, ROAS 3+ → 1.0 opacity). Fill: `rgba(249, 115, 22, {opacity})` (orange at varying opacity).
  - DataTable: Asset Group, Status chip, Cost, Impressions, Conv, CPA, ROAS. CSV export filename `google-ads-pmax`.

- **Treemap implementation**:

```tsx
import { Treemap, ResponsiveContainer, Tooltip } from 'recharts';

const CustomCell = (props) => {
  const { x, y, width, height, name, roas } = props;
  const opacity = Math.min(1.0, Math.max(0.2, (roas || 0) / 3));
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={`rgba(249,115,22,${opacity})`}
        stroke="#fff"
        strokeWidth={2}
      />
      {width > 40 && height > 20 && (
        <text
          x={x + width / 2}
          y={y + height / 2}
          textAnchor="middle"
          fill="#fff"
          fontSize={11}
        >
          {name}
        </text>
      )}
    </g>
  );
};

<ResponsiveContainer width="100%" height={240}>
  <Treemap
    data={treemapData}
    dataKey="size"
    content={<CustomCell />}
    isAnimationActive={false}
  >
    <Tooltip formatter={(v) => `$${v.toLocaleString()}`} />
  </Treemap>
</ResponsiveContainer>;
```

- **A11y**: Treemap wrapped in `<AccessibleTableToggle>`. Table columns: Asset Group, Spend, ROAS.

- **Empty/loading/error states**: standard.

## Design

```
┌────────────────────────────────────────────────────────┐
│ [Asset Groups] [Total Cost] [Total Conv]               │  ← 3 KpiTiles
├────────────────────────────────────────────────────────┤
│ Treemap: size=Spend, color intensity=ROAS              │  ← height=240
│ [orange, darker = higher ROAS]                         │
├────────────────────────────────────────────────────────┤
│ DataTable: Asset Group | Status | Cost | Conv | ROAS   │  ← CSV: google-ads-pmax
└────────────────────────────────────────────────────────┘
```

## Definition of Done

- [ ] 3 KpiTiles
- [ ] Treemap renders with ROAS-intensity color
- [ ] Treemap is wrapped in AccessibleTableToggle
- [ ] DataTable with asset group rows and CSV export
- [ ] Loading and empty states
- [ ] Tests green
- [ ] Lint clean and build clean

## Test deltas

```typescript
it('renders 3 KpiTiles', () => { ... })
it('renders Treemap with asset group data', () => {
  const { container } = render(<PMaxTab data={mockRows} />)
  expect(container.querySelector('.recharts-treemap')).toBeInTheDocument()
})
it('DataTable renders asset group rows', () => { ... })
```

## Out of scope

- Do NOT add drill-down from treemap node to asset detail
- Do NOT add a legend for the ROAS color scale (tooltip suffices)
