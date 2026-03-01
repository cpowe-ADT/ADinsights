# Meta Page Insights Operations Runbook

Timezone baseline: `America/Jamaica`.

## Scope

Operate Facebook Page Insights + Page Post Insights ingestion, troubleshooting, and dashboard freshness for:

- `MetaConnection`, `MetaPage`, `MetaMetricRegistry`
- `MetaInsightPoint`, `MetaPost`, `MetaPostInsightPoint`
- Celery tasks `sync_meta_page_insights`, `sync_meta_post_insights`

## Required permissions

OAuth token must include:

- `read_insights`
- `pages_read_engagement`

Page must be selectable with ANALYZE eligibility (`MetaPage.can_analyze=true`).

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

Run async refresh per page:

- `POST /api/metrics/meta/pages/{page_id}/refresh/`

Returns queued task IDs (`page_task_id`, `post_task_id`).

## Exports (CSV/PDF/PNG)

Generate export artifacts for the Facebook Pages dashboard (tenant-scoped; aggregated metrics only):

- Create export job: `POST /api/meta/pages/{page_id}/exports/`
  - Payload: `export_format` (`csv` | `pdf` | `png`) plus optional date range fields (`date_preset`, `since`, `until`) and widget selections (`trend_metric`, `trend_period`, `posts_metric`, `posts_sort`).
- List recent jobs: `GET /api/meta/pages/{page_id}/exports/`
- Download completed artifact: `GET /api/exports/{export_job_id}/download/`

## Metric catalog operations

Canonical source of metric definitions:

- `backend/integrations/data/meta_metric_catalog.json`

Sync catalog into registry:

- `cd backend && python manage.py sync_meta_metric_catalog`

Regenerate catalog documentation from source:

- `python3 scripts/render_meta_metric_catalog.py`

## Failure triage

### Error `#100` invalid metric

Signal:

- Graph error message contains invalid metric
- Metric status becomes `INVALID` in `MetaMetricRegistry`

Actions:

1. Confirm registry row status and replacement.
2. Verify UI hides INVALID metric in default picker.
3. If replacement metric is valid, continue ingestion with replacement key.

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

1. Confirm OAuth callback succeeds and page is selectable.
2. Confirm selected page has `can_analyze=true`.
3. Trigger refresh endpoint and capture task IDs.
4. Confirm new rows in `MetaInsightPoint` and `MetaPostInsightPoint`.
5. Verify dashboard endpoints return non-empty responses when data is available.
