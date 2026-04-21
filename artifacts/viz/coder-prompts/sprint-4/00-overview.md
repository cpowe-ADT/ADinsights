# Sprint 4 Overview — Combined + Map + Web

**Sprint:** 4
**Prerequisites:** Sprint 1 (all), Sprint 2 (for Meta-originated bugs), Sprint 3 (for Google Ads tab components).

## What this sprint does

Upgrades the combined/cross-platform dashboard pages, the parish map, web analytics pages (GA4 + Search Console), and the saved dashboards builder. B-PLAT-01 (stale cross-platform row flash) is already fixed by A4. B-SAVED-01/02 (filter platform restore) already fixed.

## Key deliverables

| Deliverable | File | Can parallel? |
|-------------|------|---------------|
| PlatformDashboard viz | `platforms.md` | Yes |
| CampaignDashboard viz | `campaigns.md` | Yes |
| CreativeDashboard viz | `creatives.md` | Yes |
| BudgetDashboard viz | `budget.md` | Yes |
| AudienceDashboard viz | `audience.md` | Yes |
| ParishMapDetail viz | `map.md` | Yes — Leaflet work separate from Recharts |
| GA4 Dashboard viz | `web-ga4.md` | Yes |
| Search Console viz | `web-search-console.md` | Yes |
| Saved Dashboards builder | `saved-dashboards.md` | After other Sprint 4 components complete |

## Key constraints

- `platforms`, `campaigns`, `creatives`, `budget`, `audience` pages use `useDashboardStore` and call `/api/metrics/combined/`
- `web/ga4` and `web/search-console` have their OWN stores and must NEVER call `/api/metrics/combined/`
- B-PLAT-03 fix (platform label normalization): add a `platformLabels.ts` helper file in Sprint 4
- `byAgeGender[]` grouped bar: expect 12+ bars per group (3 age ranges × 4 gender categories approx). Use `DistributionBar` with `series` for paired mode; if too wide, add horizontal scroll wrapper.

## Sprint 4 Definition of Done

- [ ] `platforms` page shows both platforms, no cross-platform row leakage
- [ ] `map` page renders choropleth with parish data from `payload.parish[]`
- [ ] `web/ga4` and `web/search-console` make no `/combined/` calls
- [ ] All combined pages have correct `EmptyState` variants
- [ ] Saved dashboards builder wires kit components to slot types
- [ ] `cd frontend && npm test -- --run` green
- [ ] `cd frontend && npm run lint` clean
- [ ] `cd frontend && npm run build` clean
