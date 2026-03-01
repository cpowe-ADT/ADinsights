# Meta Page Insights Data Dictionary

Timezone baseline: `America/Jamaica` for schedules, UTC-aware timestamps in storage.

Full metric catalog: `docs/project/meta-page-insights-metric-catalog.md` (generated from `backend/integrations/data/meta_metric_catalog.json`).

## `integrations_metaconnection`

- Purpose: tenant/user OAuth session for Meta Page Insights.
- Key fields:
  - `tenant_id`, `user_id`
  - `app_scoped_user_id`
  - `token_enc`/`token_nonce`/`token_tag` (encrypted token)
  - `token_expires_at`
  - `scopes` (granted permissions)
  - `is_active`

## `integrations_metapage`

- Purpose: selected Facebook pages available for insights ingestion.
- Key fields:
  - `tenant_id`, `connection_id`
  - `page_id`, `name`
  - `page_token_enc`/`page_token_nonce`/`page_token_tag`
  - `page_token_expires_at`
  - `can_analyze`
  - `tasks`, `perms`
  - `is_default` (single default page per tenant)

## `integrations_metametricregistry`

- Purpose: canonical metric registry with status, periods, and replacement mapping.
- Key fields:
  - `metric_key`
  - `level` (`PAGE` | `POST`)
  - `supported_periods`
  - `supports_breakdowns`
  - `status` (`ACTIVE` | `DEPRECATED` | `INVALID` | `UNKNOWN`)
  - `replacement_metric_key`
  - `title`, `description`
  - `is_default`

## `integrations_metainsightpoint`

- Purpose: page-level timeseries points.
- Grain:
  - `(tenant_id, page_id, metric_key, period, end_time, breakdown_key_normalized)`
- Key fields:
  - `value_num` for numeric metrics
  - `value_json` for object/list payload preservation
  - `breakdown_key`, `breakdown_json`

## `integrations_metapost`

- Purpose: page post dimension for post-level insights.
- Grain:
  - `(tenant_id, page_id, post_id)`
- Key fields:
  - `message`, `permalink_url`
  - `created_time`, `updated_time`
  - `metadata` (raw source row)

## `integrations_metapostinsightpoint`

- Purpose: post-level timeseries points.
- Grain:
  - `(tenant_id, post_id, metric_key, period, end_time, breakdown_key_normalized)`
- Key fields mirror page point table:
  - `value_num`, `value_json`, `breakdown_key`, `breakdown_json`

## Metric periods & breakdown behavior

- Page metrics usually use `day`, `week`, `days_28`.
- Post metrics commonly use `lifetime`.
- For object-valued metrics, ingestion explodes each object key into one row while preserving the original object in `value_json`.

## Default KPI metrics

- `page_post_engagements`
- `page_daily_follows_unique`
- `page_impressions_unique` (replacement fallback via registry)
- `page_total_actions`
