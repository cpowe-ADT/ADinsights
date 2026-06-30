# Meta Page Insights Operations Runbook

Timezone baseline: `America/Jamaica`.

## Scope

Operate Facebook Page Insights + Page Post Insights ingestion, troubleshooting, and dashboard freshness for:

- `MetaConnection`, `MetaPage`, `MetaMetricRegistry`
- `MetaInsightPoint`, `MetaPost`, `MetaPostInsightPoint`
- Celery tasks `sync_meta_page_insights`, `sync_meta_post_insights`

## Required permissions

For the current Facebook Login flow, the Meta page connection should request:

- `pages_show_list`
- `pages_read_engagement`
- `pages_manage_metadata`

Runtime access for Page Insights depends on Page-scoped permissions, not `read_insights`. Do not add
`read_insights` to the Facebook Login scope list; Meta rejects it as an invalid scope for this flow.

Optional Instagram scopes (`instagram_basic`, `instagram_manage_insights`) are not part of the
current Page Insights Facebook Login authorize request. In ADinsights, Instagram linkage is optional
and derived from linked Page fields during asset selection.

Page must also be selectable with ANALYZE eligibility (`MetaPage.can_analyze=true`).

## Connection states

ADinsights now distinguishes these operational states:

- `page insights connected`: a `MetaConnection` and one or more `MetaPage` rows exist, and Page-scoped
  permissions are present.
- `orphaned marketing access`: Page Insights is still connected, but the tenant has lost the Meta
  marketing credential used for ad account provisioning/reporting. In this state, Page dashboards may
  still exist while Meta ad account reporting is broken.
- `marketing permissions missing`: the stored Meta token exists but is missing the ad-account scopes
  required to restore marketing reporting.

Use `GET /api/integrations/social/status/` as the source of truth. If `reason.code` is
`orphaned_marketing_access`, send the operator to `Connect socials` at
`/dashboards/data-sources?sources=social` and use the restore flow backed by
`POST /api/integrations/meta/recovery/preview/`.

The Meta row on `GET /api/integrations/social/status/` now also carries additive
`reporting_readiness` fields so operators can separate:

- Meta auth/setup state
- direct sync state
- warehouse snapshot readiness
- live reporting environment state

Use `GET /api/datasets/status/` as the source of truth for live dashboard readiness. Meta can be
connected while live reporting is still blocked by environment config or warehouse snapshot state.

## Required Diagnostic Sequence

Inspect these endpoints in order when triaging Page Insights or Meta dashboard issues:

1. `GET /api/integrations/social/status/`
2. `GET /api/datasets/status/`
3. `GET /api/meta/accounts/`
4. `GET /api/meta/pages/`
5. `GET /api/metrics/combined/`

Use exactly one primary diagnosis:

- `auth/setup failure`
- `permission failure`
- `asset discovery failure`
- `direct sync failure`
- `warehouse adapter disabled`
- `missing/stale/default snapshot`

Interpretation reminders:

- `GET /api/meta/accounts/` is ad-account state.
- `GET /api/meta/pages/` is Facebook Page state.
- Missing Instagram linkage is non-fatal unless the requested feature explicitly depends on Instagram data.
- Do not report a generic “Meta broken” diagnosis.

## Supported local OAuth recipe

Canonical local OAuth host: `http://localhost:5173`

Launcher-backed local Meta OAuth now sets `META_OAUTH_REDIRECT_URI` to the selected frontend URL
plus `/dashboards/data-sources`. `localhost` on launcher profile 1 still matches the default local
Meta app configuration. Other launcher profiles can work too, but only when the Facebook App Domain
and valid redirect URIs include that exact host/port/path. ADinsights keeps explicit redirect URIs
deterministic and rejects OAuth starts when the runtime origin does not match the configured
redirect origin.

Supported local launcher recipe for live Meta + warehouse reporting:

```bash
ENABLE_WAREHOUSE_ADAPTER=1 \
ENABLE_DEMO_ADAPTER=1 \
ENABLE_FAKE_ADAPTER=0 \
scripts/dev-launch.sh --profile 1 --strict-profile --non-interactive --no-update --no-pull --no-open
```

If you intentionally use another launcher profile/port, update the Meta app configuration first so
it includes the exact launcher frontend origin and `/dashboards/data-sources` redirect path. For
manual non-launcher runs, export `META_OAUTH_REDIRECT_URI` yourself before starting Django.

Instagram business linking remains optional and is completed inside the Meta asset-selection flow.
Do not expect a separate Instagram OAuth flow in local/dev.

## Schedules

Default beat entries:

- Page insights nightly: `integrations.tasks.sync_meta_page_insights` at `03:10`
- Post insights nightly: `integrations.tasks.sync_meta_post_insights` at `03:20`

Tune via:

- `META_PAGE_INSIGHTS_NIGHTLY_HOUR`
- `META_PAGE_INSIGHTS_NIGHTLY_MINUTE`
- `META_POST_INSIGHTS_NIGHTLY_HOUR`
- `META_POST_INSIGHTS_NIGHTLY_MINUTE`

## Manual refresh

For the Data Sources "Run Meta sync" action, trigger the combined reporting sync with:

- `POST /api/integrations/meta/sync/`

This still queues or runs paid Meta direct sync. It also returns additive `organic_sync` metadata
and attempts a bounded organic Facebook reporting bundle for selected analyzable Pages:

- `sync_page_posts`
- `discover_supported_metrics`
- `sync_page_insights`
- `sync_post_insights`

Expected `organic_sync.status` values:

- `queued`: organic Page/Post work was queued for background processing.
- `skipped`: no analyzable Facebook Page is selected for the tenant.
- `completed`: inline fallback ran and stored at least one Page/Post reporting row.
- `completed_no_rows`: inline fallback ran but Graph returned no Page/Post report rows.
- `partial`: one or more Page sync tasks failed or returned mixed states.

The reporting bundle uses existing Page-scoped permissions. Do not add `read_insights`, and do not
call live providers during report preview/export.

SLB monthly report behavior:

- Organic reach, impressions, and clicks remain unavailable unless Meta approves the required
  insights access or an approved manual import path is used.
- The governed SLB template uses available Page follows plus edge-sourced post reactions, comments,
  and shares. These are stored in the existing Page/Post aggregate tables and can render without
  `read_insights`.
- The report includes a client-facing availability note instead of hard-blocking on organic
  reach/impressions. Missing organic insight values must stay `null`/unavailable, never synthetic
  zeroes.
- Paid Meta widgets in the SLB report must carry an explicit `account_id` or `client_id` before
  preview/export. Do not let a fixed SLB report read all tenant Meta rows. If the scoped SLB account
  has no retained rows, export may proceed only as explicit warning-only no-data evidence; paid
  parity and cancellation readiness remain blocked until backfill/source repair or approved daily
  paid CSV import supplies real selected-account values.
- Use `GET /api/reports/data-availability/` before export handoff. The paid dataset applies
  `client_id` to linked Meta ad accounts and may return `scope_diagnostic` when the selected account
  or client scope has no retained rows even though other tenant Meta rows exist. Follow the
  diagnostic required action; do not clear the blocker with unrelated account data.
- The same data-availability response carries per-dataset `metric_availability` summaries. Use
  `available`, `callable_no_data`, `permission_gated`, and `unsupported` to decide which report
  metrics can render, which should stay null with a no-data warning, and which require Meta approval
  or a manual import path. Replacement rows such as media views must not be treated as approved
  reach/impression product metrics unless an approved manual import stores the explicit product
  metric key.
- If an account-scoped diagnostic includes `credential_status.status=missing`, the selected Meta ad
  account is not reconnected for paid reporting. Reconnect/select that account and run fixed-range
  paid backfill before claiming paid coverage completion; a warning-only export is still no-data
  evidence, not a substitute for paid parity.
- `GET /api/reports/<report-id>/diagnostics/` also carries redacted
  `source_health.report_scope.paid_meta_ads` and
  `source_health.report_scope.organic_facebook_page` for SLB reports. Use paid `backfill_status`,
  `credential_status.status`, and `scoped_rows.row_count` to confirm whether support should
  reconnect the selected account, run `slb_backfill_meta_reporting`, or proceed with export. Use
  organic `page_scope_present`, `matched_page_count`, `scoped_rows.row_count`, and
  `backfill_status` to confirm whether a tenant-owned SLB Facebook Page is selected before manual
  organic import/backfill. The matching `source_health.remediation_actions` commands use
  placeholders and must not expose tenant, Page, or ad-account IDs in support packets. When a
  remediation action includes `dry_run_command_template`, run that validation command before the
  write-capable `command_template`.
- Fixed-range `slb_backfill_meta_reporting --dispatch-mode dry-run` is plan-only. It reports the
  planned tasks, engagement-edge enrichment, and fallback commands, skips the redacted request audit
  event, and emits `audit_event.status=skipped`; inline or queued runs still record the audit event.
  Dry-run organic post backfill must report `engagement_edges[page_id].status=planned` and must not
  call Meta edge endpoints.
- If the selected account cannot be API-backfilled because a retained credential is missing, and an
  approved Meta Ads UI/export file exists, use `import_meta_paid_csv` as a manual paid fallback. It
  requires daily rows and rejects multi-day aggregates so May 1-31 coverage cannot be faked with a
  single monthly total. `slb_backfill_meta_reporting` dry-runs now surface this as
  `fallback_actions[].code=manual_meta_paid_csv_import` and
  `post_backfill_commands.manual_paid_csv_import` when paid API backfill is credential-blocked, plus
  `post_backfill_commands.manual_paid_csv_import_dry_run` so the approved daily file can be
  validated before import.
- If the fixed SLB report has no selected-account paid rows and/or no retained organic
  Facebook/Page, organic post, or Content Ops rows, those sections export as visible warning-only
  "no retained rows" notes when no hard permission, unsupported-metric, or unscoped paid blocker is
  present. This is not a data substitute; operators should still import approved source values or
  rerun backfill before parity evidence.
- Partial paid Meta coverage is allowed to export only as a warning when the requested report has
  stored paid rows and all other required sources are available. Endpoint-only rows do not prove a
  full month; missing internal dates keep the dataset `partial` and must remain visible through
  `coverage_gap` plus a `coverage_note` that names the missing span. Keep the coverage note visible
  in report preview/export metadata.

## Manual paid CSV fallback import

When an approved Meta Ads UI/export file has selected-account daily paid rows but API backfill is
blocked by missing credentials, import those aggregate values into the same stored paid tables used
by report preview/export:

```bash
backend/.venv/bin/python backend/manage.py import_meta_paid_csv \
  --tenant-id <tenant_uuid> \
  --account-id <meta_ad_account_id> \
  --file /path/to/meta-paid-daily-export.csv
```

Validate an approved selected-account daily export before writing with:

```bash
backend/.venv/bin/python backend/manage.py import_meta_paid_csv \
  --tenant-id <tenant_uuid> \
  --account-id <meta_ad_account_id> \
  --file /path/to/meta-paid-daily-export.csv \
  --dry-run
```

CSV requirements:

- Required per row: `date` or `date_start`; `account_id` unless `--account-id` is provided.
- `date_stop`, if present, must equal the row date. Monthly aggregate rows are rejected.
- Optional campaign fields: `campaign_id`, `campaign_name`/`campaign`.
- Supported metrics: `spend`/`amount_spent`/`cost`, `impressions`, `reach`, `clicks`,
  `conversions`, `cpc`, and `cpm`.
- Blank metric cells are skipped on update and do not overwrite existing values with zero. Invalid
  non-finite, or negative numeric values abort the import.
- Blank metric cells on newly created manual paid rows are tracked in row metadata and must render
  as `null`/no-data in paid preview/export summaries and
  `GET /api/reports/data-availability/` metric states. Do not treat the model's numeric defaults as
  measured zeroes for manual import columns that were not supplied. Derived metrics such as `ctr`,
  `cpc`, and `frequency` are available only when their required base inputs exist.
- The target `AdAccount` must already exist for the tenant. The command may create campaign metadata
  for the tenant/account, but it will not create ad accounts or cross tenant boundaries.

The command emits `meta_paid_csv_import.v1` JSON with aggregate counts only and records a redacted
audit event unless `--dry-run` is used. Dry-run mode emits the same aggregate count summary with
`dry_run=true` but writes no paid records, creates no campaigns, and records no audit event. It does
not call Meta and does not import user-level data.

## Manual organic CSV fallback import

When Meta UI/export has organic Page or post reach/impression values that the Graph API cannot
return without `read_insights`, import those approved aggregate values into the same stored
reporting tables used by report preview/export:

```bash
backend/.venv/bin/python backend/manage.py import_meta_organic_csv \
  --tenant-id <tenant_uuid> \
  --page-id <facebook_page_id> \
  --file /path/to/meta-organic-export.csv
```

Validate an approved file and target Page before writing with:

```bash
backend/.venv/bin/python backend/manage.py import_meta_organic_csv \
  --tenant-id <tenant_uuid> \
  --page-id <facebook_page_id> \
  --file /path/to/meta-organic-export.csv \
  --dry-run
```

CSV requirements:

- Required per row: `date` or `end_time`; `page_id` unless `--page-id` is provided.
- Optional post grain: `post_id`, `post_message`/`message`, `permalink`/`permalink_url`,
  `created_time`.
- Supported product metric columns include `page_reach`, `page_impressions`, `page_follows`,
  `post_impressions`, `post_reach`, `post_clicks`, `post_reactions`, `post_comments`, and
  `post_shares`. The command also accepts the governed source keys from
  `source_metric_semantics`.
- Product metric columns are stored under their product keys and can satisfy runtime
  `metric_availability` after the approved import. Source-key columns such as `page_media_view` and
  `post_media_view` are stored as source rows for diagnostics/compatibility and do not by themselves
  clear `permission_gated` reach/impression product metrics.
- Blank metric cells are skipped and do not overwrite existing values with zero. Invalid or
  non-finite, or negative numeric values abort the import.
- The target `MetaPage` must already exist for the tenant. The command may create missing
  `MetaPost` rows under that Page, but it will not create Pages or cross tenant boundaries.

The command emits `meta_organic_csv_import.v1` JSON with aggregate counts only and records a
redacted audit event unless `--dry-run` is used. Dry-run mode emits the same aggregate count summary
with `dry_run=true` but writes no reporting rows, creates no posts, and records no audit event. It
does not call Meta, does not require `read_insights`, and does not import user-level engagement,
viewer, commenter, or reaction identity data.

For the current Page Insights dashboard, trigger a sync per page with:

- `POST /api/meta/pages/{page_id}/sync/`

Response includes `task_dispatch_mode`:

- `queued` when Celery successfully dispatches background work
- `inline` when local/dev runtime falls back because the broker is unavailable

Legacy dashboard refresh remains available at:

- `POST /api/metrics/meta/pages/{page_id}/refresh/`

## Exports (CSV/PDF/PNG)

Generate export artifacts for the Facebook Pages dashboard (tenant-scoped; aggregated metrics only):

- Create export job: `POST /api/meta/pages/{page_id}/exports/`
  - Payload: `export_format` (`csv` | `pdf` | `png`) plus optional date range fields (`date_preset`, `since`, `until`) and widget selections (`trend_metric`, `trend_period`, `posts_metric`, `posts_sort`).
- List recent jobs: `GET /api/meta/pages/{page_id}/exports/`
- Download completed artifact: `GET /api/exports/{export_job_id}/download/`

## Metric catalog operations

Canonical source of metric definitions:

- `backend/integrations/data/meta_metric_catalog.json`

Runtime source of truth:

- `backend/integrations/services/metric_registry.py`

The runtime registry should refresh from the canonical catalog before falling back to the legacy
metric pack. This is required because local/dev databases can keep stale registry rows after
catalog updates; relying only on "registry is non-empty" can leave deprecated Graph metric names in
default sync sets.

Sync catalog into registry:

- `cd backend && python manage.py sync_meta_metric_catalog`

Regenerate catalog documentation from source:

- `python3 scripts/render_meta_metric_catalog.py`

Graph v24 organic reporting defaults:

- Page reach/impression product aliases use current v24 source keys such as
  `page_total_media_view_unique` and `page_media_view`.
- Post impression aliases use `post_media_view`; unique post reach aliases use
  `post_total_media_view_unique`.
- Legacy direct post keys such as `post_impressions` and `post_impressions_unique` are retained for
  historical stored rows only and must not be requested by default.
- If Graph returns synced posts but zero Page/Post insight metric rows, reports may show stored post
  activity (`date`, `content`, `permalink`) with `null` metric values and partial coverage. Do not
  convert missing metrics to zero, and do not mark exports ready until required coverage is present.
  This applies to grouped/chart previews as well as tables: a missing metric for a displayed post or
  Page group must remain `null`, not an aggregated `0`.
- `GET /api/dashboards/reporting-catalog/` exposes `availability_state` for governed product
  metrics. Treat `permission_gated` organic metrics as unavailable for default report-builder
  selection until Meta approval or a manual import path exists.
- Canonical `/api/meta/pages/*` and `/api/meta/posts/*` `metric_availability` entries also expose
  additive `availability_state` and `availability_note` fields:
  - `available`: the metric is supported and stored rows exist for the selected Page/Post scope.
  - `callable_no_data`: the metric is supported/callable, but no retained rows exist for the
    selected range. Keep values null; do not show zero.
  - `permission_gated`: Page permissions or an auth/permission support error blocks metric access.
  - `unsupported`: the metric is invalid, deprecated, blocked, or failed support discovery for a
    non-permission reason.
    Existing `supported` remains for backward compatibility; use `availability_state` for new
    operator and builder UX because `supported=true` can still mean callable with no stored rows.

## Failure triage

### Orphaned marketing access

Signal:

- `GET /api/integrations/social/status/` returns Meta `reason.code=orphaned_marketing_access`
- `GET /api/meta/accounts/` is empty even though the stored Meta token can still discover ad accounts

Actions:

1. Open `Connect socials` at `/dashboards/data-sources?sources=social`.
2. Run the recovery preview using the existing stored `MetaConnection` token.
3. Re-save the selected page, ad account, and optional Instagram account.
4. Let the UI run the default restore chain:
   - save selected assets
   - best-effort Meta provision
   - direct Meta sync
   - warehouse snapshot refresh
   - refresh Meta status, pages, and accounts
5. Confirm `GET /api/integrations/social/status/` no longer reports `orphaned_marketing_access`.
6. Confirm `GET /api/meta/accounts/` now returns persisted ad accounts.
7. Confirm `GET /api/datasets/status/` progresses through one of:
   - `ready`
   - `missing_snapshot`
   - `stale_snapshot`
   - `default_snapshot`
   - `adapter_disabled`

## Dashboard readiness stages

After a successful Meta restore or reconnect, dashboard availability progresses in this order:

1. `Meta connected`
2. `Direct sync complete`
3. `Waiting for warehouse snapshot` or `Live data refreshing`
4. `Live reporting ready`

If `/api/datasets/status/` returns `adapter_disabled`, the Meta connection is healthy but the
environment is not configured to serve live warehouse dashboards yet.

### Error `#100` invalid metric

Signal:

- Graph error message contains invalid metric
- Metric status becomes `INVALID` in `MetaMetricRegistry`

Actions:

1. Confirm registry row status and replacement.
2. Verify UI hides INVALID metric in default picker.
3. If replacement metric is valid, continue ingestion with replacement key.

For Graph v24 Page/Post reporting, specifically confirm that default sync keys come from
`get_default_metric_keys()` after `seed_default_metrics()` and do not include deprecated direct post
impression keys. If a local database still contains old defaults, run `sync_meta_metric_catalog` or
restart the backend so the runtime seed refresh can update existing rows.

### Graph returns posts but no Page/Post insight rows

Signal:

- `sync_meta_page_posts` stores `MetaPost` rows for the selected Page/range.
- `sync_meta_page_insights` or `sync_meta_post_insights` completes with zero insight rows.
- Report preview shows stored top-post/activity rows but organic metric widgets have partial or
  missing coverage.

Actions:

1. Confirm the Page token and Page `can_analyze=true` state through `GET /api/meta/pages/`.
2. Confirm the selected date range is inside Graph's supported lookback window for the chosen
   metric and period.
3. Probe current v24 metric keys from the catalog; do not retry deprecated direct keys such as
   `post_impressions` or `post_impressions_unique` by default.
4. Keep report metrics unavailable (`null`) when Graph returns no metric values. Showing zero would
   imply a measured value when the provider returned no retained history.
5. If client-ready reporting is required, use a real backfill/source export/upload fallback and
   record the fallback source in coverage notes before enabling export readiness.

### Error `3001` + subcode `1504028` (missing metric parameter)

Signal:

- Graph error indicates no metric specified.

Actions:

1. Validate task payload includes at least one metric.
2. Validate metric chunking did not pass empty set.
3. Re-run task after correcting metric set.

### Error `80001` throttling

Signal:

- Graph reports too many calls to page/account.

Actions:

1. Verify retry handling (exponential backoff base 2, jitter, max 5 attempts).
2. Reduce manual refresh frequency.
3. Re-run in next schedule window.

## Observability expectations

Each sync emits structured observability events with:

- `tenant_id`
- `task_id`
- `correlation_id`
- `rows_processed`
- `page_id` where applicable

Alert conditions:

- Consecutive sync failures
- Unexpected empty datasets after previously non-empty syncs
- Permission regressions (`missing_required_permissions`)

## Registry invalidation & replacement

- Registry defaults are initially seeded by migration `0010_meta_page_post_insights.py`.
- Full catalog sync is applied by migration `0012_sync_meta_metric_catalog.py`.
- Ongoing catalog updates should use `sync_meta_metric_catalog`.
- Runtime invalid metric handling updates `status=INVALID`.
- Replacement mapping is stored in `replacement_metric_key`.
- Frontend default metric picker excludes `INVALID`/`DEPRECATED` by default.

## Operational checklist

1. Confirm Page OAuth callback succeeds and the selected page has `can_analyze=true`.
2. Confirm `GET /api/meta/pages/` returns `missing_required_permissions: []`.
3. If Meta ad reporting is also expected, confirm `GET /api/integrations/social/status/` does not report `orphaned_marketing_access`.
4. Confirm `GET /api/datasets/status/` is truthful for the current environment and snapshot state.
5. Trigger `POST /api/meta/pages/{page_id}/sync/` and capture `task_dispatch_mode`.
6. Confirm new rows in `MetaInsightPoint` and `MetaPostInsightPoint`.
7. Verify page overview/posts endpoints return data when the selected date range includes synced rows.
