ADinsights — Figma Component Checklist

Purpose: Track design system coverage and screen readiness for ADinsights. Use this as an issue checklist or Figma page notes. UI copy should say “Client”; backend concept remains “tenant.” Timezone everywhere: America/Jamaica. No PII or secrets.

Design Tokens & Themes

- [x] Global tokens (colors, spacing, radius, shadows, motion) created from docs/design/figma-variables.json — see `frontend/src/styles/foundations.css`
- [x] Light theme mappings (bg/fg/border/accent) applied across components — dashboard shell + analytics cards use semantic tokens
- [x] Dark theme mappings with AA/AAA contrast verified — ThemeProvider stories exercise both themes
- [ ] Typography styles (Body, Title, Caption) applied

Navigation & Shell

- [x] SidebarNav (sections: Overview, Campaigns, Ad Sets, Ads, Geography, Dimensions, Data Health, Settings) — nav pills share `--shell-nav-*`
- [~] TopBar with: ClientSwitcher, DateRangePicker, CompareToggle, TimezoneBadge, ChannelFilter, CurrencySelect, SearchField — ClientSwitcher listbox + aria-live complete; remaining controls pending
- [x] StatusStrip showing Last Sync + Data Freshness with link to Data Health — status banners rely on `--shell-status-*`

Core Components

- [ ] Button (sizes: sm/md/lg; tones: primary/secondary/tertiary/destructive; states: rest/hover/focus/pressed/loading/disabled)
- [ ] TextField (sizes: sm/md; states: rest/focus/error/disabled; adornments: none/leading/trailing)
- [ ] Select / MultiSelect (sizes: sm/md; withSearch variants)
- [ ] Badge (tones: success/warning/danger/info/neutral)
- [ ] Alert/Toast (tones: success/warning/danger/info; with/without actions)
- [ ] Modal / Drawer / Sheet (sizes: sm/md/lg)
- [ ] Skeleton (kpi/chart/table-row/map)
- [ ] Pagination (simple/full)
- [ ] Tabs (sizes: sm/md)

Analytics Components

- [ ] KPI.Card (metrics: Spend, Impressions, Clicks, Conversions, Revenue, CTR, CPC, CPM, CPA, ROAS; delta: up/down/neutral/none; sparkline on/off)
- [ ] Chart.Line & Chart.Area (single vs compare series; channel coloring: Meta blue, Google green)
- [ ] Chart.StackedBar (channel breakdown)
- [ ] Chart.Donut (share breakdown; accessible legend)
- [ ] Map.Choropleth (metric selector; buckets: quantile/jenks; null bucket; legend compact/full; accessible tooltips)

Table System (TanStack-inspired)

- [ ] Table primitives: HeaderCell, Cell, Row, Toolbar (filters, column chooser, export), Pagination
- [ ] States: loading (row placeholders), empty, error
- [ ] Features: column resize/reorder, visibility (column chooser), pinned columns (left/right), selection (single/multi), saved views
- [ ] Server-driven: controlled sorting (state.sorting + onSortingChange), filtered query indicators
- [ ] CSV export flow and confirmation

Details & Panels

- [ ] Details.Panel (tabs: performance, geo, metadata); open/closed states
- [ ] Right-side drawer pattern for row details from tables

Screens & Templates

- [ ] Overview: KPI row → Trend chart → Channel breakdown → Geo map → Top campaigns table → Alerts panel
- [ ] Campaigns: Toolbar (filters/search/saved views) → Table → Details.Panel
- [ ] Ad Sets: same as Campaigns
- [ ] Ads: same as Campaigns
- [ ] Geography: Map-first layout; right table panel; metric + region filters
- [ ] Dimensions: Read-only lightweight tables (active flag, last modified); SCD hint copy
- [ ] Data Health: Airbyte + dbt cards (last run, duration, success rate, rows, cost units) → Runs timeline (24h/7d) → filters → guidance
- [ ] Settings: Client profile, timezone display, currency, daily summary recipients, connection status badges (no tokens)
- [ ] AI Daily Summary Email (06:10): KPIs, 7-day sparkline, channel comparison, top 5 campaigns, CTA; footer with updated time and TZ

Copy & Definitions

- [ ] Metric tooltips with formulas (CTR, CPC, CPM, CPA, ROAS) and plain-language descriptions
- [ ] Freshness copy: “Last sync HH:MM America/Jamaica”; “Insights window lookback: 3 days (Meta)”
- [ ] Error/empty copy: human-readable, no technical jargon; guidance + next steps

Accessibility

- [~] Keyboard navigation for tables, filters, map focusable features — tenant switcher supports full keyboard flow
- [~] Focus-visible styles consistent and obvious — header tenant menu reuses global focus ring and AA tokens
- [ ] ARIA/alt text guidance for charts (summary table or description)
- [ ] Color contrast passes AA/AAA for key text and UI

Responsive

- [ ] Breakpoints: 360, 768, 1024, 1280+
- [ ] Mobile: KPI stack; filter sheet; tables collapse to cards; map full-bleed with list toggle
- [ ] Tablet/Desktop: density variants and grid behavior verified

Performance-minded Patterns

- [ ] Table virtualization guidance (large lists)
- [ ] Debounced search; sensible default date range
- [ ] Memoized filters/pills pattern

Integration & Health

- [ ] Health endpoints represented: /api/health/, /api/health/airbyte/, /api/health/dbt/, /api/timezone/
- [ ] Status badges and alerts for sync failures, empty syncs, secret expiry (no secrets shown)

QA Checklist (Design → Build)

- [ ] All components mapped to code counterparts (React + Vite, TanStack Table, Leaflet)
- [ ] Theme variables used; no hard-coded colors
- [ ] Compare toggle updates charts and KPIs with deltas and ghost series
- [ ] CSV export reflects applied filters and visible columns
- [ ] Geography tooltips handle missing values without breaking layout
