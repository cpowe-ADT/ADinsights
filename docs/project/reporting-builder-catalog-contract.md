# Reporting Builder Catalog Contract

Created: 2026-06-15
Status: v1 contract with initial backend/frontend runtime slices implemented
Timezone baseline: America/Jamaica

Purpose: define the first governed reporting catalog for ADinsights custom dashboards and reports.
This contract gives backend, frontend, dbt, integrations, and support a shared definition of which
datasets, metrics, dimensions, widgets, chart/table combinations, and historical fallback states are
valid. Initial runtime slices now include backend catalog validation, a read-only catalog endpoint,
a widget preview endpoint, frontend catalog consumption, and an SLB monthly report template action.

See also:

- `docs/project/reporting-builder-backend-data-structure-audit.md`
- `docs/project/reporting-builder-architecture-plan.md`
- `docs/project/dashthis-replacement-reporting-plan.md`
- `docs/project/integration-data-contract-matrix.md`
- `docs/project/meta-page-insights-metric-catalog.md`
- `docs/workstreams.md`
- `docs/project/api-contract-changelog.md`
- `docs/runbooks/meta-page-insights-operations.md`

## Contract Goals

This contract is designed to make the reporting builder flexible without making it unsafe.

The builder should support:

- SLB-style monthly reports.
- Saved dashboards with custom widgets.
- KPI, chart, table, and report narrative sections.
- X/y chart comparisons.
- Individual source dashboards.
- Combined paid/organic pages with explicit source labeling.
- Historical 90-day/monthly reports when providers are disconnected but data was already synced.
- Future SaaS users with tenant isolation, permissions, auditability, and supportable failure states.

The builder must not support:

- Arbitrary SQL.
- Arbitrary provider API calls at report-render time.
- Unsupported metric/dimension/chart combinations.
- Silent paid/organic metric blending.
- Cross-tenant/client/account/page references.
- Deprecated or unknown provider metrics unless explicitly marked as experimental and hidden from
  default user selection.

## Scope And Contract Advisory

Current doc change:

- Scope status: `PASS_SINGLE_SCOPE` because this artifact is docs-only.
- Contract status: `WARN_POSSIBLE_CONTRACT_CHANGE` because it defines future API/data behavior but
  does not change serializers, dbt models, integration schemas, or runtime endpoints yet.

Implementation follow-up:

- Backend validation touches `backend/analytics/` and is API-contract-sensitive.
- Catalog-backed frontend builder touches `frontend/`.
- Warehouse coverage and retention work touches `dbt/` and/or ingestion surfaces.
- Combined social semantics can touch `backend/`, `frontend/`, `dbt/`, `integrations/`, and docs.
- Cross-folder implementation must route through Raj. Architecture/schema changes must include Mira.

## Catalog Schema

The backend should eventually expose or own a registry with these top-level sections:

```json
{
  "schema_version": "reporting_catalog.v1",
  "datasets": [],
  "metrics": [],
  "dimensions": [],
  "widgets": [],
  "compatibility": [],
  "coverage_statuses": [],
  "report_templates": []
}
```

Recommended implementation shape:

- v1 backend source of truth: static Python registry plus tests.
- v1 frontend: consume `GET /api/dashboards/reporting-catalog/` for governed datasets, metrics,
  dimensions, widgets, compatibility, and coverage policies.
- v1 docs: this contract is the human-readable baseline.
- Later: database-backed tenant template catalog only after the static contract is stable.

## Dataset Catalog

### v1 Datasets

| Dataset key | Status | Source family | Product use | Source of truth | Notes |
| --- | --- | --- | --- | --- | --- |
| `paid_meta_ads` | active_v1 | Paid social | Meta Ads campaign/ad/creative dashboards and SLB paid pages | Airbyte/warehouse + Meta direct fallback where already supported | Do not confuse ad-account reporting with Page Insights. |
| `organic_facebook_page` | active_v1 | Organic social | Facebook Page overview, top posts, organic engagement sections | Meta Page/Post Insights stored rows and Page Insights APIs | Use only active, supported Page/Post metrics. |
| `content_ops` | active_v1 | Organic operations | Work completed, content counts, publishing activity, recommendations support | Content Ops stored app tables and aggregate snapshots | Aggregate-only; no user-level engagement or commenter data. |
| `combined_paid_media` | active_v1 | Paid media aggregate | Meta Ads + Google Ads paid dashboard summaries | Existing combined metrics path and warehouse marts | Only paid media metrics with matching semantics. |
| `csv_upload` | active_v1_support | Manual fallback | Manual backfill or proof fixtures for campaign/parish/budget data | `TenantMetricsSnapshot` source `upload` | Support path, not preferred live source. |

### Future-Gated Datasets

| Dataset key | Status | Gate before activation | Notes |
| --- | --- | --- | --- |
| `organic_instagram` | future_gated | Confirm scopes, source rows, metric definitions, and App Review readiness | Required for full SLB parity only if Instagram pages are mandatory. |
| `combined_social` | future_gated | Define approved blended metrics and source-label requirements | v1 may compose paid and organic widgets on one page but should not blend metrics silently. |
| `ga4_web` | future_gated | Product approval to bring web analytics into reporting builder | Existing pilot endpoint remains separate. |
| `search_console` | future_gated | Product approval and source semantic mapping | Existing pilot endpoint remains separate. |

## Metric Catalog

Metric fields:

| Field | Meaning |
| --- | --- |
| `key` | Product-facing stable key used by widget configs. |
| `source_metric` | Provider/dbt/API field or expression. |
| `dataset` | Dataset key where metric is valid. |
| `label` | UI/report label. |
| `value_type` | `currency`, `count`, `decimal`, `percent`, `ratio`, or `text`. |
| `aggregation` | `sum`, `avg`, `weighted_avg`, `latest`, `count_distinct`, `derived`, or `none`. |
| `format` | UI/export formatting hint. |
| `grains` | Supported grains: `day`, `week`, `month`, `lifetime`, `selected_range`. |
| `dimensions` | Allowed dimension keys. |
| `widgets` | Allowed widget types. |
| `required_status` | Required source/catalog status such as `active_v1` or `future_gated`. |
| `source_label_required` | Whether widgets must show source label. |

### Paid Meta Ads Metrics

| Key | Source metric | Type | Aggregation | Widgets | Notes |
| --- | --- | --- | --- | --- | --- |
| `spend` | `spend` | currency | sum | KPI, line, bar, table, map | Account currency preserved; do not mix with organic. |
| `impressions` | `impressions` | count | sum | KPI, line, bar, table, map | Paid impressions only. |
| `reach` | `reach` | count | sum or latest by source grain | KPI, line, bar, table, map | Paid reach semantics differ from Page reach. |
| `clicks` | `clicks` | count | sum | KPI, line, bar, table | Paid clicks. |
| `conversions` | `conversions` | decimal | sum | KPI, line, bar, table | Subject to attribution lag. |
| `conversion_value` | `conversions_value` or source equivalent | currency | sum | KPI, line, bar, table | Optional until source availability is proven. |
| `ctr` | `clicks / impressions` | percent | derived | KPI, line, bar, table, scatter | Weighted by impressions. |
| `cpc` | `spend / clicks` | currency | derived | KPI, line, bar, table, scatter | Block when denominator is zero. |
| `cpm` | `spend / impressions * 1000` | currency | derived | KPI, line, bar, table | Block when denominator is zero. |
| `cpa` | `spend / conversions` | currency | derived | KPI, line, bar, table | Block or null when conversions are zero. |
| `roas` | `conversion_value / spend` | ratio | derived | KPI, line, bar, table | Requires conversion value. |
| `frequency` | `impressions / reach` | decimal | derived | KPI, line, table | Block when reach is zero. |

Allowed dimensions: `date`, `client`, `platform`, `ad_account`, `campaign`, `adset`, `ad`, `creative`,
`placement`, `region`, `parish`, `objective`, `status`.

### Organic Facebook Page Metrics

Only active/supported Page and Post metrics from `docs/project/meta-page-insights-metric-catalog.md`
should be selectable by default. Deprecated metrics must be hidden. Unknown metrics must be hidden
unless explicitly enabled for internal validation.

| Key | Source metric | Type | Aggregation | Widgets | Notes |
| --- | --- | --- | --- | --- | --- |
| `page_reach` | `page_total_media_view_unique` fallback `page_impressions_unique` | count | sum or latest by period | KPI, line, bar, table | Product alias for organic Page reach. |
| `page_impressions` | `page_media_view` fallback `page_impressions` | count | sum | KPI, line, bar, table | Organic Page impressions where source supports it. |
| `page_engagements` | `page_post_engagements` | count | sum | KPI, line, bar, table | Default Page engagement KPI. |
| `page_actions` | `page_total_actions` | count | sum | KPI, line, bar, table | Page actions total. |
| `page_follows` | `page_daily_follows_unique` | count | sum | KPI, line, bar, table | New follows over selected period. |
| `page_fans` | `page_follows` fallback `page_fans` | count | latest | KPI, line, table | Current/lifetime audience count. |
| `page_reactions_like` | `page_actions_post_reactions_like_total` | count | sum | KPI, bar, table | Reaction breakdown. |
| `page_reactions_love` | `page_actions_post_reactions_love_total` | count | sum | KPI, bar, table | Reaction breakdown. |
| `page_reactions_wow` | `page_actions_post_reactions_wow_total` | count | sum | KPI, bar, table | Reaction breakdown. |
| `post_impressions` | `post_media_view`; historical stored rows may still contain legacy `post_impressions` | count | sum | KPI, bar, table | Top post table metric. Do not request deprecated direct keys by default. |
| `post_clicks` | `post_clicks` | count | sum | KPI, bar, table | Top post table metric. |
| `post_reactions_like` | `post_reactions_by_type_total[like]` fallback `post_reactions_like_total` | count | sum | KPI, bar, table | Top post table metric. |
| `post_reactions_love` | `post_reactions_by_type_total[love]` fallback `post_reactions_love_total` | count | sum | KPI, bar, table | Top post table metric. |
| `post_activity` | `post_activity_by_action_type` | count/object | derived or exploded | table | Requires backend normalization before broad chart use. |

Allowed dimensions: `date`, `client`, `platform`, `page`, `post`, `content_type`, `reaction_type`,
`period`, `source`.

Backend source-of-truth: `backend/integrations/services/metric_registry.py`.
Saved reports and dashboards continue to use the stable ADinsights product metric keys above.
Graph provider keys are Graph-v24-aware, can include fallbacks for retained historical rows, and are
exposed additively from `GET /api/dashboards/reporting-catalog/` as `source_metric_semantics`.
When synced posts exist but Graph returns no Page/Post insight metric rows, top-post tables may
render stored post activity fields such as `date`, `content`, and `permalink`; metric cells remain
unavailable rather than zero, and coverage stays partial or blocked as appropriate.

### Content Ops Metrics

| Key | Source metric | Type | Aggregation | Widgets | Notes |
| --- | --- | --- | --- | --- | --- |
| `content_items_created` | app content/draft count | count | count_distinct | KPI, line, bar, table | Work completed metric. |
| `published_posts` | `PublishedPost` count | count | count_distinct | KPI, line, bar, table | Aggregate only. |
| `scheduled_posts` | schedule count | count | count_distinct | KPI, line, bar, table | Use schedule timezone baseline. |
| `approved_items` | approval decision count | count | count_distinct | KPI, line, bar, table | Monthly operations summary. |
| `content_ops_reach` | `OrganicPostMetricSnapshot.reach` | count | sum | KPI, line, bar, table | Only where aggregate snapshots exist. |
| `content_ops_engagements` | aggregate engagement snapshot | count | sum | KPI, line, bar, table | No user-level engagement details. |
| `content_ops_impressions` | aggregate impression snapshot | count | sum | KPI, line, bar, table | Optional based on available snapshots. |

Allowed dimensions: `date`, `client`, `workspace`, `channel`, `content_type`, `status`,
`published_post`, `source`.

### Combined Paid Media Metrics

`combined_paid_media` may use these product metrics only when each source maps to the same paid-media
meaning.

Allowed metrics: `spend`, `impressions`, `clicks`, `conversions`, `conversion_value`, `ctr`, `cpc`,
`cpm`, `cpa`, `roas`.

Rules:

- `reach` is source-specific unless semantics are explicitly documented.
- Currency must be normalized or source-labeled.
- Derived ratios must be recomputed from summed numerator/denominator, not averaged across rows.
- The widget must show source labels when grouped by platform.

### Future Organic Instagram Metrics

Use these as planning placeholders only. Do not expose in user-facing selection until source
readiness and permission status are proven.

Candidate keys: `instagram_reach`, `instagram_impressions`, `instagram_profile_views`,
`instagram_follower_count`, `instagram_media_interactions`, `instagram_likes`,
`instagram_comments`, `instagram_saves`, `instagram_shares`, `instagram_video_views`.

## Dimension Catalog

| Key | Type | Valid datasets | Notes |
| --- | --- | --- | --- |
| `date` | time | all time-series datasets | Required x-axis for trend lines. |
| `week` | time | all time-series datasets | Derived from `date`; use America/Jamaica reporting baseline unless source forces UTC. |
| `month` | time | all time-series datasets | Derived from `date`; required for monthly reports. |
| `client` | entity | all tenant-scoped datasets | Must be tenant-scoped. |
| `platform` | category | all multi-source datasets | Examples: Meta Ads, Google Ads, Facebook Page, Instagram, Content Ops. |
| `source` | category | all combined dashboards | Required for paid/organic source labels. |
| `ad_account` | entity | `paid_meta_ads`, `combined_paid_media` | Must not be confused with Facebook Page. |
| `campaign` | entity | `paid_meta_ads`, `combined_paid_media` | Paid-only campaign dimension. |
| `adset` | entity | `paid_meta_ads` | Meta Ads only. |
| `ad` | entity | `paid_meta_ads` | Meta Ads only. |
| `creative` | entity | `paid_meta_ads` | Creative leaderboard/table. |
| `placement` | category | `paid_meta_ads` | Use only where source provides trustworthy placement. |
| `region` | geography | `paid_meta_ads` | Map/table only with coverage proof. |
| `parish` | geography | `paid_meta_ads` | Jamaica map/table only with coverage proof. |
| `page` | entity | `organic_facebook_page` | Facebook Page dimension. |
| `post` | entity | `organic_facebook_page`, `content_ops` | Top post/content table. |
| `content_type` | category | `organic_facebook_page`, `content_ops` | Post/content classification. |
| `reaction_type` | category | `organic_facebook_page` | Reaction breakdowns. |
| `workspace` | entity | `content_ops` | Tenant-scoped Content Ops workspace. |
| `status` | category | `paid_meta_ads`, `content_ops` | Campaign/content workflow state. |

## Widget Types

| Widget type | Purpose | Required config | v1 status |
| --- | --- | --- | --- |
| `kpi` | Single or grouped top-line metric tiles | `dataset`, `metrics`, filters, optional compare | active_v1 |
| `line_chart` | Trend over time | `x_dimension=date`, one or more y metrics | active_v1 |
| `bar_chart` | Category comparison | categorical x dimension, one or more y metrics | active_v1 |
| `stacked_bar_chart` | Category comparison with breakdown | x dimension, y metric, breakdown dimension | active_v1_guarded |
| `donut_chart` | Share of total | category dimension, one metric | active_v1_guarded |
| `data_table` | Detailed rows | columns, sort, row limit | active_v1 |
| `report_section` | Narrative report block | section type, title, optional data bindings | active_v1 |
| `map` | Geography view | geography dimension, one numeric metric | active_v1_guarded |
| `scatter_chart` | X/y metric comparison | x metric, y metric, optional size metric | future_gated |

Required shared widget fields:

```json
{
  "id": "stable_widget_id",
  "type": "line_chart",
  "dataset": "paid_meta_ads",
  "metrics": ["spend"],
  "dimensions": ["date"],
  "filters": {
    "date_range": "last_90d",
    "client_id": "tenant-scoped-client-id"
  },
  "compare": {
    "mode": "previous_period"
  },
  "coverage_policy": "render_with_warning",
  "visual": {
    "title": "Spend trend",
    "source_labels": true
  }
}
```

## Chart And Table Compatibility

| Widget | Valid x | Valid y | Valid breakdown | Required coverage rule |
| --- | --- | --- | --- | --- |
| `kpi` | none | one or more metrics from one dataset | source/platform optional | Must show stale/partial note when not fresh. |
| `line_chart` | `date`, `week`, `month` | numeric metrics | platform/source allowed | Must show covered date range. |
| `bar_chart` | category/entity dimension | numeric metrics | source/platform/content type optional | Must cap categories or require top-N. |
| `stacked_bar_chart` | category/time dimension | one numeric metric | one category breakdown | Must reject high-cardinality breakdowns. |
| `donut_chart` | one category dimension | one numeric metric | none | Must reject negative or non-additive metrics. |
| `data_table` | row dimensions | metric and dimension columns | none | Must enforce row limit and sort rules. |
| `report_section` | none | optional bound metrics | none | Must inherit coverage notes from bound widgets. |
| `map` | `parish` or `region` | one numeric paid metric | none | Must require geography coverage proof. |

## X/Y Rules

Allowed examples:

| Use case | Dataset | x | y | Widget |
| --- | --- | --- | --- | --- |
| Spend trend | `paid_meta_ads` | `date` | `spend` | `line_chart` |
| Campaign performance | `paid_meta_ads` | `campaign` | `spend`, `clicks`, `ctr` | `bar_chart` or `data_table` |
| Creative efficiency | `paid_meta_ads` | `creative` | `ctr`, `cpc`, `conversions` | `data_table`; scatter later |
| Parish performance | `paid_meta_ads` | `parish` | `spend`, `reach`, `conversions` | `map` or `data_table` |
| Page engagement trend | `organic_facebook_page` | `date` | `page_engagements` | `line_chart` |
| Top posts | `organic_facebook_page` | `post` | `post_impressions`, `post_clicks`, reactions | `data_table` |
| Content production | `content_ops` | `date` or `content_type` | `published_posts`, `content_items_created` | `line_chart`, `bar_chart`, `data_table` |
| Paid platform split | `combined_paid_media` | `platform` | `spend`, `clicks`, `conversions` | `bar_chart`, `data_table` |

General rules:

- Time-series charts require `date`, `week`, or `month` on x.
- Derived percentage/cost metrics need their denominator metrics available in the dataset.
- High-cardinality dimensions such as `post`, `ad`, and `creative` require top-N or table mode.
- `map` widgets require `region` or `parish` plus a metric with trustworthy geography coverage.
- Organic and paid metrics can appear on the same dashboard page, but not in the same blended KPI
  unless `combined_social` explicitly approves that metric.

## Invalid Combinations To Reject

Backend validation must reject these examples even if the frontend sends them:

| Invalid config | Reason |
| --- | --- |
| `organic_facebook_page` metric `page_engagements` grouped by `campaign` | Page metrics do not have paid campaign grain. |
| `paid_meta_ads` metric `spend` grouped by `page` | Paid ad spend is ad-account/campaign grain, not Page grain. |
| `combined_social` KPI `reach` without source labels or approved blend definition | Paid reach and organic reach have different semantics. |
| `donut_chart` with `cpc` | Cost-per-click is non-additive and not a share-of-total metric. |
| `line_chart` with x=`campaign` | Line charts require time x-axis. |
| `map` using `organic_facebook_page` without geography coverage | Organic Page geo coverage is not approved for v1 maps. |
| `scatter_chart` in v1 user-facing builder | Future-gated until backend validation and UX are ready. |
| Deprecated Page metrics such as `page_video_views_10s` | Deprecated in current Meta Page metric catalog. |
| Unknown Page metrics such as `page_views_total` by default | Unknown status must not be exposed by default. |
| Table without row limit | Report builder must prevent unbounded queries/exports. |
| Cross-tenant `client_id`, `page_id`, `ad_account`, or `workspace` | Violates tenant isolation. |
| `last_90d` report when only 47 days are retained and policy=`require_full_coverage` | Must block or switch to warning policy explicitly. |

## Historical Fallback And Coverage States

Every dataset response used by dashboards or report exports should eventually include coverage
metadata. The builder should not need to infer freshness from chart data.

Coverage status values:

| Status | Meaning | Render rule |
| --- | --- | --- |
| `fresh` | Source connected and data covers requested range within freshness SLA. | Render normally. |
| `stale` | Historical data exists, but latest sync is outside freshness SLA. | Render with freshness note. |
| `partial` | Some requested dates are available, but not the full range. | Render with warning or block based on widget/report policy. |
| `source_disconnected` | Provider/OAuth/connector cannot fetch fresh data, but retained data may exist. | Render only if `history_status=available`; show clear note. |
| `missing_history` | Source may be connected, but requested range is not retained in ADinsights. | Block or require smaller date range. |
| `not_previously_synced` | The source/account/page was never synced for the requested range. | Block and show setup/backfill action. |
| `permission_missing` | Required provider scope/permission is missing. | Block fresh sync; render retained data only if policy permits. |
| `unsupported_metric` | Metric is not valid for dataset/source status. | Block. |

Recommended coverage payload shape:

```json
{
  "dataset": "organic_facebook_page",
  "requested_start_date": "2026-03-17",
  "requested_end_date": "2026-06-15",
  "covered_start_date": "2026-03-17",
  "covered_end_date": "2026-06-14",
  "coverage_status": "source_disconnected",
  "history_status": "available",
  "freshness_status": "stale",
  "last_successful_sync_at": "2026-06-15T06:04:00-05:00",
  "row_count": 180,
  "source_label": "Facebook Page Insights",
  "coverage_note": "Facebook Page Insights is disconnected. This report uses stored data through 2026-06-14."
}
```

Coverage policies:

| Policy | Behavior |
| --- | --- |
| `require_full_coverage` | Block if `covered_start_date` or `covered_end_date` does not fully match requested range. |
| `render_with_warning` | Render available data with visible coverage note. |
| `render_snapshot_only` | Use the saved/generated report snapshot only; do not attempt fresh source pull. |
| `block_if_stale` | Block when outside freshness SLA even if history exists. |

Default v1 policy:

- Dashboards: `render_with_warning`.
- Scheduled monthly reports: `render_with_warning` unless stakeholder requires strict parity.
- Cancellation/parity proof reports: `require_full_coverage`.
- Compliance/audit exports: `render_snapshot_only` after generation.

## Dashboard Config Contract

`DashboardDefinition.layout` should eventually validate this shape:

```json
{
  "schema_version": "dashboard.v1",
  "layout": {
    "columns": 12,
    "slots": [
      {
        "id": "slot_paid_spend_trend",
        "widget_id": "paid_spend_trend",
        "cols": 8,
        "rows": 2
      }
    ]
  },
  "widgets": [
    {
      "id": "paid_spend_trend",
      "type": "line_chart",
      "dataset": "paid_meta_ads",
      "metrics": ["spend"],
      "dimensions": ["date"],
      "filters": {
        "date_range": "last_90d"
      },
      "coverage_policy": "render_with_warning",
      "visual": {
        "title": "Paid spend trend",
        "source_labels": true
      }
    }
  ]
}
```

Backend validation should keep legacy template dashboards valid while rejecting malformed
`dashboard.v1` configs.

## Report Layout Contract

`ReportDefinition.layout` should use the same catalog language, with page/section wrappers:

```json
{
  "schema_version": "report.v1",
  "template_key": "slb_monthly_social_report",
  "pages": [
    {
      "id": "paid_media",
      "title": "Paid media performance",
      "sections": [
        {
          "id": "paid_summary",
          "type": "widget_group",
          "widget_ids": ["paid_kpis", "paid_spend_trend", "paid_campaign_table"]
        }
      ]
    }
  ],
  "widgets": []
}
```

Rules:

- Report pages can reference dashboard widgets.
- Report sections inherit widget coverage notes.
- Narrative sections may include manual text, AI-assisted summaries, or structured
  recommendations, but must never hide stale/partial data states.
- Exported artifacts should record the catalog schema version and data coverage metadata used at
  generation time.

## SLB Monthly Report Mapping

Use SLB as the first proof template because it exercises paid, organic, top-content, and narrative
report needs.

| Report page | Dataset | Widgets | Required metrics | Coverage policy |
| --- | --- | --- | --- | --- |
| Cover + period | all bound datasets | `report_section` | reporting period, client, source coverage summary | `render_with_warning` |
| Executive summary | `paid_meta_ads`, `organic_facebook_page`, `content_ops` | KPI group, narrative section | spend, reach, clicks, page engagements, published posts | `render_with_warning` |
| Paid Meta Ads performance | `paid_meta_ads` | KPI, line, bar, table | spend, impressions, reach, clicks, ctr, cpc, cpm, conversions | `require_full_coverage` for cancellation proof; otherwise warning |
| Organic Facebook/Page performance | `organic_facebook_page` | KPI, line, table | page reach, impressions, engagements, actions, follows, fans | `render_with_warning` |
| Top posts | `organic_facebook_page` | data table | post impressions, clicks, reactions, activity | `render_with_warning` |
| Content activity/work completed | `content_ops` | KPI, bar/table, narrative section | content items created, published posts, scheduled posts, approvals | `render_with_warning` |
| Instagram performance | `organic_instagram` | KPI, line, table | future-gated Instagram metrics | Block until dataset is active. |
| Recommendations | bound source datasets | `report_section` | data-backed highlights and next actions | Must disclose source coverage. |
| Appendix/data notes | all bound datasets | coverage table | source status, freshness, retained range, row counts | Always required for v1 exports. |

Minimum SLB v1 without Instagram:

- Paid Meta Ads page.
- Organic Facebook/Page page.
- Top posts table.
- Content activity/work completed section.
- Recommendations section with data coverage notes.

## Backend Validation Acceptance Criteria

Future backend implementation must satisfy these criteria:

1. `schema_version` is required for catalog-driven configs.
2. Unknown datasets, metrics, dimensions, widget types, compare modes, and coverage policies are rejected.
3. Metrics must belong to the selected dataset.
4. Dimensions must be valid for the selected dataset and widget type.
5. Derived metrics must have valid denominator rules.
6. Combined datasets must require source labels unless the metric is explicitly approved as blended.
7. Deprecated and unknown Meta Page metrics are hidden by default and rejected for user-created widgets.
8. Cross-tenant/client/account/page/workspace references are rejected.
9. Row limits are required for tables and high-cardinality dimensions.
10. Date ranges must be bounded. Recommended v1 max is 13 months unless an admin export path
    explicitly allows more.
11. Coverage metadata must be computed or attached before report preview/export.
12. `require_full_coverage` blocks partial or missing history at widget preview time.
13. For `report.v1` export readiness, `missing_history`, `not_previously_synced`,
    `permission_missing`, and `unsupported_metric` are hard blockers even when widget preview uses
    `render_with_warning`; preview may still render available stored data with notes.
14. `render_with_warning` must return visible coverage notes to the frontend/export renderer.
15. Existing template dashboards remain backward-compatible.
16. Dashboard/report create, update, duplicate, export, and schedule actions continue to audit
    redacted metadata only.

## Required Tests

Docs-only v1 contract:

- Verify this document is indexed in `docs/ops/doc-index.md`.
- Verify activity log entry exists.
- Run a sensitive-string scan before handoff.

Backend implementation tests:

- Serializer validation accepts valid `dashboard.v1` configs.
- Serializer validation rejects invalid dataset/metric/dimension/widget combinations.
- Validation rejects cross-tenant references.
- Validation rejects deprecated/unknown Meta Page metrics by default.
- Validation enforces table row limits.
- Validation enforces coverage policies.
- Existing saved dashboard CRUD tests still pass.
- Report export jobs preserve data coverage metadata.

dbt/data quality tests:

- Required mart/source fields exist for active v1 metrics.
- Tenant IDs are present and tested on reporting marts.
- Freshness tests cover active datasets.
- Row-count and date-coverage checks can distinguish empty sync from missing history.

Frontend tests:

- Dataset selector filters metric/dimension options.
- Widget builder prevents invalid x/y combinations.
- Preview displays `fresh`, `stale`, `partial`, `source_disconnected`, `missing_history`, and
  `not_previously_synced` states.
- Report preview/export surfaces coverage notes.
- Mobile and desktop layouts do not overlap with long metric labels.

Contract/preflight tests:

- `make adinsights-preflight PROMPT="Assess reporting builder catalog and dashboard schema changes"`
- Backend: `make backend-lint && make backend-test`
- Frontend: `make frontend-guardrails && make frontend-lint && make frontend-test && make frontend-build`
- dbt when marts change: AGENTS dbt validation commands.

## Reviewer Route By Persona

| Area | Primary | Backup | Review focus |
| --- | --- | --- | --- |
| Source ingestion, disconnects, backfill | Maya | Leo | Retry behavior, source telemetry, disconnected-source states, raw landing. |
| Warehouse retention and marts | Priya | Martin | Metric grain, freshness, retention, rebuildability, dbt tests. |
| Backend catalog/API validation | Sofia | Andre | Serializer validation, metrics API compatibility, snapshots, coverage payloads. |
| Frontend builder/report UX | Lina | Joel | Builder controls, x/y rules, source labels, stale/partial states, responsive layout. |
| Secrets/data retention safety | Nina | Victor | No secrets, token, or user-level PII retention or logs. |
| Observability/support | Omar | Hannah | Alert states, support runbooks, freshness diagnostics. |
| BI/deployment/export operations | Carlos | Mei | Artifact retention, export reproducibility, deployment/runbook fit. |
| Cross-stream integration | Raj | Mira | Multi-folder sequencing, architecture consistency, contract review. |

## Implementation Slices

Recommended safe order:

1. Docs-only contract approval for this artifact.
2. Backend-only catalog registry and validation module.
3. Backend-only `DashboardDefinition.layout` validation for `dashboard.v1`.
4. Backend-only report coverage metadata prototype.
5. Frontend-only builder using backend catalog.
6. Frontend-only report preview states and coverage notes.
7. SLB report template using existing `ReportDefinition`/export scaffolding.
8. dbt/integration retention and coverage improvements if the backend cannot prove 90-day history
   from existing warehouse/mart state.
9. Combined social dashboard semantics after source-label and blended-metric rules are proven.

## Open Decisions

- Confirm whether SLB cancellation requires Instagram in v1 or whether Facebook Page + paid Meta Ads
  + Content Ops is acceptable for the first proof.
- Confirm v1 retention targets for raw rows, marts, report artifacts, and sync telemetry.
- Decide whether `combined_paid_media` should include Google Ads in the first SLB template or remain
  paid Meta-only for that client.
- Decide whether report snapshots should store rendered aggregate payloads, source row references, or
  both.
- Decide whether AI-written recommendations are v1, or whether recommendations remain manually
  editable text bound to metric highlights.

## Next Prompt

Use this prompt for the first implementation planning slice:

```text
Implement the backend reporting catalog registry and dashboard.v1 validation for ADinsights.

Read:
- docs/project/reporting-builder-catalog-contract.md
- docs/project/reporting-builder-architecture-plan.md
- docs/workstreams.md
- backend/analytics/models.py
- backend/analytics/phase2_serializers.py
- backend/analytics/phase2_views.py

Scope:
- backend/ only unless Raj/Mira approve a cross-stream change.

Requirements:
- Preserve legacy saved dashboard templates.
- Add a backend source of truth for v1 datasets, metrics, dimensions, widgets, and compatibility.
- Validate DashboardDefinition.layout when schema_version is dashboard.v1.
- Reject invalid combinations listed in the catalog contract.
- Add tests for valid config, invalid metrics/dimensions, row limits, source labels, and coverage policies.

Run:
- make backend-lint
- make backend-test
- make adinsights-preflight PROMPT="Assess backend reporting catalog and dashboard.v1 validation"
```
