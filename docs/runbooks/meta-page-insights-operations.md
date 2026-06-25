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
