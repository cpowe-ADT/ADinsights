# Google Ads Search Tab — Visualization Upgrade

**Sprint:** 3
**Estimated size:** M
**Depends on:** sprint-1/\* (all kit components)
**Blocks:** none
**Role needed:** frontend-engineer

## Context

The Search tab covers both keywords and search terms for the Google Ads workspace. Two endpoints: `GET /api/google-ads/keywords/` and `GET /api/google-ads/search-terms/`. Shows a KPI strip, quality score vs CPC scatter, top search terms bar, keywords DataTable, and search terms DataTable.

## Inputs already in the repo (do not re-invent)

- Keyword row fields (from sprint plan): `keyword_text, match_type, criterion_status, quality_score, impressions, clicks, conversions, cpa, ctr, cpm`
- Search term row fields: `search_term, impressions, clicks, conversions, cpa, ctr`
- All Sprint 1 viz components.

## Deliverable

- **File(s) to create/modify**: identify the Search tab component inside `frontend/src/routes/google-ads/` and modify it.
- Create corresponding test file.

- **Data binding**:
  - KPI strip (3 tiles): Total Keywords = count of keyword rows; Avg Quality Score = mean of `quality_score` (filter null/0 values); Top Keyword Conv = max(conversions) across keyword rows + the keyword name in a subtitle.
  - BubbleScatter (quality score scatter): keyword rows mapped to `{ id: keyword_text + match_type, label: keyword_text, x: quality_score, y: spend/clicks (CPC — if spend field available, else avg_cpc), z: impressions, shape: match_type === 'EXACT' ? 'circle' : 'triangle' }`. Note: `quality_score` is an integer 1–10. X axis range: 0–10.
  - DistributionBar (top 10 search terms by conversions): search term rows sorted by conversions, top 10. `data = topTerms.map(r => ({ label: r.search_term, value: r.conversions }))`.
  - DataTable (keywords): Keyword, Match Type, Status, QS (quality_score), Impressions, Clicks, Conv, CPA. CSV export filename `google-ads-keywords`.
  - DataTable (search terms): Search Term, Impressions, Clicks, Conv, CPA. CSV export filename `google-ads-search-terms`.

- **Interactions**: keyword table row click → no-op for Sprint 3.

- **Empty/loading/error states**: standard ChartSkeleton + EmptyState per block.

## Design

```
┌────────────────────────────────────────────────────────┐
│ [Total Keywords] [Avg QS] [Top Keyword Conv]           │  ← 3 KpiTiles
├────────────────────────────────────────────────────────┤
│ BubbleScatter: x=QS, y=CPC, z=Impressions             │  ← height=280
├────────────────────────────────────────────────────────┤
│ DistributionBar: Top 10 Search Terms by Conversions    │  ← height=200
├────────────────────────────────────────────────────────┤
│ DataTable: Keywords (sortable, CSV export)             │
├────────────────────────────────────────────────────────┤
│ DataTable: Search Terms (sortable, CSV export)         │
└────────────────────────────────────────────────────────┘
```

## Definition of Done

- [ ] 3 KpiTiles (Total Keywords, Avg QS, Top Keyword Conv)
- [ ] BubbleScatter with QS vs CPC (circle=EXACT, triangle=BROAD/PHRASE)
- [ ] DistributionBar for top 10 search terms by conversions
- [ ] Two DataTables: keywords + search terms
- [ ] Loading and empty states for all blocks
- [ ] Tests green
- [ ] Lint clean and build clean

## Test deltas

```typescript
it('renders 3 KpiTiles', () => { ... })
it('BubbleScatter renders keyword points', () => { ... })
it('DistributionBar renders top search terms', () => { ... })
it('Keywords DataTable renders with QS column', () => { ... })
it('Search Terms DataTable renders', () => { ... })
it('shows EmptyState when keywords empty', () => { ... })
```

## Out of scope

- Do NOT add keyword bid adjustment controls
- Do NOT add negative keyword management
- Do NOT link keywords to campaign detail in Sprint 3
