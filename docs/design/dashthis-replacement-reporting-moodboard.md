# DashThis Replacement Reporting Moodboard

Timestamp: 2026-06-15T21:59:01-0500
Timezone: America/Jamaica
Related plan: `docs/project/dashthis-replacement-reporting-plan.md`
Related evidence: `docs/project/evidence/dashthis-replacement/2026-06-15-email-attachment-review.md`
Visual board: `docs/design/dashthis-replacement-reporting-moodboard.html`

## Design Goal

Make ADinsights feel strong enough to replace DashThis for client-facing monthly reporting while
also giving operators a live dashboard they can trust day to day.

The visual direction is:

- Executive clear.
- Agency polished.
- Data-dense without feeling crowded.
- Narrative enough for client reporting.
- Built from ADinsights tokens and existing dashboard patterns.

## Reference Board

These references should guide structure and interaction patterns, not be copied directly.

| Reference | Use it for | What to adapt |
| --------- | ---------- | ------------- |
| Whatagraph social media report template: `https://whatagraph.com/templates/social-media-report` | Monthly report/deck flow | Cover, overview, channel breakdown, top content, recommendations. |
| DashThis social media report template: `https://dashthis.com/social-media-report-template/` | Replacement parity | KPI widgets, client-friendly dashboard layout, report simplicity. |
| DashThis client report guide: `https://dashthis.com/blog/client-social-media-report/` | Client storytelling | Performance summary plus next-campaign recommendations. |
| Supermetrics organic social Looker template: `https://supermetrics.com/template-gallery/looker-studio-organic-social-report-template` | Organic dashboard structure | Multi-platform engagement, growth, and performance sections. |
| Porter Metrics social templates: `https://portermetrics.com/en/templates/social-media/` | Looker-style density | Instagram Insights, Facebook + Instagram, content performance, client presentation layouts. |
| Coupler social media examples: `https://www.coupler.io/dashboard-examples/social-media-dashboard` | Analytical widgets | Geography, content-type breakdowns, reach, engagement, platform comparisons. |
| Sprout Social reporting guide: `https://sproutsocial.com/insights/social-media-reporting/` | Strategic commentary | Explain what happened and what to do next. |
| HubSpot social media report template: `https://www.hubspot.com/resources/templates/social-media-report` | Simple stakeholder decks | Report sections that non-technical stakeholders can follow. |

## Visual Direction

Use a restrained analytics base with sharp accents:

| Role | Color | Usage |
| ---- | ----- | ----- |
| Canvas | `#f8fafc` | App background and report margin. |
| Paper | `#ffffff` | Report pages and cards. |
| Ink | `#0f172a` | Headings and high-priority text. |
| Muted text | `#64748b` | Captions, helper text, table metadata. |
| Primary blue | `#2563eb` | Active filters, primary series, Meta/paid emphasis. |
| Teal | `#0f766e` | Organic social, secondary series, positive engagement. |
| Amber | `#d97706` | Caution, underperformance, attention callouts. |
| Coral | `#e11d48` | Negative deltas and urgent exceptions. |
| Green | `#16a34a` | Growth and positive variance. |
| Violet | `#7c3aed` | Creative/content-performance accent only. |

Rules:

- Do not make the UI mostly blue or mostly purple.
- Keep cards at 8px radius or the existing `--radius-md`.
- Prefer white and light neutral surfaces with strong typography.
- Use small, meaningful color accents instead of decorative backgrounds.
- Use sparklines, deltas, and badges as scanning aids.
- Keep report pages print-friendly and readable as PDFs.

## Live Dashboard Mood

The dashboard is for operator decisions. It should feel more like a control room than a slide deck.

Primary view:

```text
Client / SLB              May 2026            Live data     Last sync 06:18
---------------------------------------------------------------------------
Performance Summary
[Views] [Reach] [Link Clicks] [Interactions] [Follows] [Spend]

Trend line: views/reach/clicks over time          Platform split
Paid vs organic contribution                      Facebook vs Instagram

Top content and ads table                         Data quality / blockers
Creative thumbnail | Type | Views | Interactions | Clicks | Delta | Notes
```

Required dashboard modules:

- Sticky filter row: client, date range, compare period, source, platform, campaign.
- KPI strip: views, reach, link clicks, interactions, follows, spend, CTR where paid data exists.
- Source split: paid Meta Ads vs organic Facebook/Instagram.
- Platform comparison: Instagram and Facebook side by side.
- Trend chart: current period with prior-period ghost line.
- Top performers: static posts, carousels, reels, and digital ads in one sortable table.
- Data quality panel: last sync, missing scopes, empty source warnings, attribution notes.
- Export actions: PDF, CSV, PNG, schedule email.

## Monthly Client Report Mood

The monthly report is for client confidence and decision-making. It should feel composed, not like a
raw dashboard screenshot.

Recommended SLB report sequence:

| Page | Purpose | Main content |
| ---- | ------- | ------------ |
| 1 | Cover | Client, month, campaign theme, prepared-by line. |
| 2 | Executive summary | 3-5 highlights, key wins, key declines, next focus. |
| 3 | Performance scorecard | Views, reach, clicks, interactions, follows, spend if available. |
| 4 | Instagram performance | Metrics, MoM deltas, top insight, content count. |
| 5 | Facebook performance | Metrics, MoM deltas, top insight, content count. |
| 6 | Paid digital ads | Reach, impressions, clicks/conversions, best campaigns/ads. |
| 7 | Top performers | Best static, carousel, reel, and ad creative with metrics. |
| 8 | Work completed | Campaign/content development, creative support, production support. |
| 9 | Recommendations | Next month priorities, experiments, content themes, CTA focus. |
| 10 | Appendix | Source notes, definitions, data freshness, caveats. |

Page layout rules:

- Keep one primary story per page.
- Put KPI cards in compact rows; do not stretch them into hero blocks.
- Use short narrative callouts beside charts.
- Use platform icons or labels sparingly for scanability.
- Keep tables narrow enough for PDF export.
- Include data freshness and timezone in footer.

## Component Moodboard

| Component | Visual treatment | Notes |
| --------- | ---------------- | ----- |
| KPI card | White surface, thin border, 8px radius, large value, compact delta chip, optional sparkline. | Use for both dashboard and report pages. |
| Delta chip | Green, coral, or neutral chip with arrow icon and period label. | Always show compare period. |
| Insight callout | Left accent border, concise headline, 1-2 sentence interpretation. | Use in reports, not every dashboard card. |
| Top performer tile | Thumbnail/creative placeholder, format badge, title, metric row, why-it-worked note. | Needed for SLB parity. |
| Source badge | Paid, Organic, Instagram, Facebook, Search, Analytics. | Prevent paid/organic confusion. |
| Data quality banner | Amber for missing data, coral for failed sync, neutral for caveats. | Never hide missing scopes. |
| Report footer | Client, period, timezone, generated timestamp, source labels. | Must appear on every PDF page. |

## Data Story Rules

Every client report should answer:

1. What changed this month?
2. Which platform drove the change?
3. Which content or ad performed best?
4. What work did Adtelligent complete?
5. What should happen next month?
6. What data caveats should the client know?

## SLB First Build Direction

Build the first design around SLB full-report parity:

- Dashboard tab: `SLB Monthly Performance`.
- Report template: `SLB Monthly Campaign Status Report`.
- Primary month: May 2026.
- Compare period: March-April 2026 baseline or April 2026 when source data supports exact MoM.
- Data sources: Meta Ads, Facebook Page Insights, Instagram Insights.
- Manual/narrative fields: account activity, creative support, production support, next steps.

## Do Not Copy

- Do not use a marketing landing page layout for the dashboard.
- Do not use huge hero typography inside dashboard cards.
- Do not bury filters below content.
- Do not use decorative gradient blobs or dark atmospheric backgrounds.
- Do not mix paid and organic metrics without labels.
- Do not generate a client report that is only screenshots of the live dashboard.

## Implementation Notes

When this moves from design to frontend:

- Reuse `frontend/src/styles/theme.css` and `frontend/src/styles/dashboard.css` tokens.
- Keep `TanStack Table` controlled sorting for top performers.
- Use explicit source labels in API payloads and UI.
- Add visual tests for desktop and mobile report/dashboard layouts.
- Add PDF render checks for footer, page breaks, table overflow, and text clipping.
