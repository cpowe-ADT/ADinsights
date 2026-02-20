# Meta Page Insights Module

This module manages Facebook Page Insights and Page Post Insights sync for ADinsights.

## Setup

Required env vars (see `backend/.env.sample`):

- `META_APP_ID`
- `META_APP_SECRET`
- `META_GRAPH_API_VERSION`
- `META_PAGE_INSIGHTS_OAUTH_SCOPES` (for `POST /api/meta/connect/start/`)
- `META_PAGE_INSIGHTS_ENABLED`
- `META_PAGE_INSIGHTS_METRIC_PACK_PATH`
- `META_PAGE_INSIGHTS_BACKFILL_DAYS`
- `META_PAGE_INSIGHTS_INCREMENTAL_LOOKBACK_DAYS`
- `META_PAGE_INSIGHTS_POST_RECENCY_DAYS`

## Local Sync Commands

Run from `backend/`:

```bash
python manage.py shell -c "from integrations.tasks import sync_meta_pages; sync_meta_pages.delay('<connection_id>')"
python manage.py shell -c "from integrations.tasks import discover_supported_metrics; discover_supported_metrics.delay('<page_id>')"
python manage.py shell -c "from integrations.tasks import sync_page_insights; sync_page_insights.delay('<page_id>')"
python manage.py shell -c "from integrations.tasks import sync_page_posts; sync_page_posts.delay('<page_id>')"
python manage.py shell -c "from integrations.tasks import sync_post_insights; sync_post_insights.delay('<page_id>')"
```

## Troubleshooting

- `#100`: invalid metric; discovery isolates bad metrics and marks them unsupported.
- `3001 / 1504028`: missing metric payload from Graph; sync continues without failing the job.
- `80001`: rate limiting; retries use exponential backoff with jitter up to 5 attempts.
- `No Pages available`: ensure the connected Meta user has Page Insights capability on at least one Page (`ANALYZE` task or admin page role fallback).
- `wrong_oauth_flow`: OAuth callback state and endpoint mismatch. For page dashboard flow use:
  - start: `POST /api/meta/connect/start/`
  - callback: `POST /api/meta/connect/callback/`
  and do not send that state to `POST /api/integrations/meta/oauth/exchange/`.

## Page-Only Connect Runbook

Use this flow when onboarding only Facebook Page Insights (no ad-account requirement):

1. Start OAuth via page flow endpoint:
   - `POST /api/meta/connect/start/`
2. Complete Meta consent and capture `code` + `state`.
3. Complete callback via page flow endpoint:
   - `POST /api/meta/connect/callback/` with `{ "code": "...", "state": "..." }`
4. Confirm pages are persisted:
   - `GET /api/meta/pages/`
5. Trigger sync for default/selected page:
   - `POST /api/meta/pages/{page_id}/sync/`
6. Verify dashboard APIs return data:
   - `GET /api/meta/pages/{page_id}/overview/?date_preset=last_28d`
   - `GET /api/meta/pages/{page_id}/posts/?date_preset=last_28d`

## Local Schema Recovery

If local APIs fail with `no such column` or `no such table`, your sqlite schema is behind code.

```bash
cp /Users/thristannewman/ADinsights/backend/db.sqlite3 /Users/thristannewman/ADinsights/backend/db.sqlite3.bak.$(date +%Y%m%d%H%M%S)
export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-dev-local-key}"
cd /Users/thristannewman/ADinsights/backend && ./.venv/bin/python manage.py migrate
./.venv/bin/python manage.py showmigrations integrations analytics
```

Expected migration state:

- `integrations` shows `0001` through `0012` applied.
- `analytics` shows `0001` through `0004` applied.
