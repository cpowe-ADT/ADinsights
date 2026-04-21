# Google Ads Conversions Tab — Visualization Upgrade

**Sprint:** 3
**Estimated size:** S
**Depends on:** sprint-1/* (all kit components), sprint-3/google-ads-campaigns.md (for funnel source data)
**Blocks:** none
**Role needed:** frontend-engineer

## Context

The Conversions tab in the Google Ads workspace. Primary endpoint: `GET /api/google-ads/conversions-by-action/`. The funnel (Impressions → Clicks → Conversions) uses aggregated totals from `GET /api/google-ads/campaigns/` — no new endpoint required. Note: Recharts 3.8.1 does NOT have FunnelChart — use the same stepped-bar fallback as `meta-campaigns.md`.

## Inputs already in the repo (do not re-invent)

- Conversion action row fields: `conversion_action_name, conversions, conversion_value, cost_per_conversion`
- Campaign list endpoint (already used in campaigns tab): provides total impressions, clicks, conversions for funnel.
- All Sprint 1 viz components.

## Deliverable

- **File(s) to create/modify**: identify the Conversions tab component and modify it.

- **Data binding**:
  - KPI strip (3 tiles): Total Conversions = sum(conversions); Total Conv Value = sum(conversion_value); Avg CPA = sum(cost_per_conversion * conversions) / sum(conversions) or simply mean(cost_per_conversion).
  - Funnel (stepped-bar fallback): aggregate from campaigns endpoint — `{ impressions: sum, clicks: sum, conversions: sum }`. Same implementation as `meta-campaigns.md`:
    ```typescript
    const funnelData = [
      { label: 'Impressions', value: totals.impressions, color: chartPalette[1] },
      { label: `Clicks (${clickRate}%)`, value: totals.clicks, color: chartPalette[2] },
      { label: `Conversions (${convRate}%)`, value: totals.conversions, color: chartPalette[3] },
    ]
    ```
    Render as `DistributionBar` with 3 bars. Drop-off annotations between bars.
  - PieComposition (source mix): conversion action rows mapped to `[{ label: row.conversion_action_name, value: row.conversions }]`. Top 8 actions; aggregate rest as "Other".
  - DataTable: Action Name, Conversions, Value, CPA. CSV export filename `google-ads-conversions`.

- **Funnel source data**: the campaigns tab already fetches `/api/google-ads/campaigns/`. If the conversions tab is in the same workspace context and the campaigns data is available in the workspace hook's cache, reuse it. Otherwise, fire a separate fetch.

## Design

```
┌────────────────────────────────────────────────────────┐
│ [Total Conv] [Conv Value] [Avg CPA]                    │  ← 3 KpiTiles
├──────────────────────────────┬─────────────────────────┤
│ Funnel (stepped DistBar)     │ Source Mix Pie          │  ← 50/50
│ Impressions → Clicks → Conv  │ by action_name          │
├──────────────────────────────┴─────────────────────────┤
│ DataTable: Action | Conv | Value | CPA                 │  ← CSV: google-ads-conversions
└────────────────────────────────────────────────────────┘
```

## Definition of Done

- [ ] 3 KpiTiles
- [ ] Funnel stepped-bar shows Impressions → Clicks → Conversions with drop-off %
- [ ] PieComposition for conversion action mix
- [ ] DataTable with conversion actions
- [ ] FunnelChart not used (no FunnelChart in Recharts 3.8.1)
- [ ] Loading and empty states
- [ ] Tests green
- [ ] Lint clean and build clean

## Test deltas

```typescript
it('renders 3 KpiTiles', () => { ... })
it('renders funnel as DistributionBar with 3 steps', () => { ... })
it('renders PieComposition for conversion action mix', () => { ... })
it('DataTable shows action rows', () => { ... })
```

## Out of scope

- Do NOT use FunnelChart (not in Recharts 3.8.1)
- Do NOT add conversion path analysis
