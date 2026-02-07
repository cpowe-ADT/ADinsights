# Integration Data Contract Matrix (Phase 1)

Purpose: single contract map from source payloads to warehouse/dbt/API surfaces for Meta, Google Ads,
GA4, Search Console, and CSV ingestion.

Owners: Maya (Integrations), Priya (dbt), Sofia (Metrics API). Cross-stream review required from Raj and
Mira because this contract spans infrastructure + dbt + backend + frontend + docs.

Timezone baseline: `America/Jamaica`.

## Meta Ads (Facebook/Instagram via Marketing API)

| Source API object/report | Selected fields | Expected type/unit | Timezone semantics | Currency semantics | Primary key grain | Lookback/latency notes | Destination raw columns | dbt staging columns | `/api/metrics/combined/` usage | validated_on | evidence_link |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Airbyte Facebook Marketing `ads_insights` (`level=ad`, daily) + metadata streams (`ads`, `adsets`, `campaigns`) | `date_start`, `ad_account_id`/`account_id`, `campaign_id`, `adset_id`, `ad_id`, `region`, `spend`, `impressions`, `clicks`, `conversions`, `actions`, `action_values`, `updated_time` | Spend/cost numeric, counts numeric, IDs text, date/date-time strings | Source account timezone; orchestration schedule pinned to `America/Jamaica` | Account currency from source; preserved through staging, aggregated as configured dashboard currency | `(tenant_id, ad_account_id/account_id, campaign_id, adset_id, ad_id, date)` | Incremental sync with lookback replay; attribution windows can delay final conversions; token revocation/permission drift can stale syncs | `raw.meta_ads_insights`, `raw_meta.ad_insights`, `raw_meta.ads`, `raw_meta.adsets`, `raw_meta.campaigns` | `stg_meta_ads`, `stg_meta_insights`, `stg_meta_ads_metadata`, `stg_meta_adsets`, `stg_meta_campaigns` | Feeds `fact_performance` -> `vw_dashboard_aggregate_snapshot` sections: `campaign`, `creative`, `budget`, `parish` | 2026-02-06 | `docs/project/integration-api-validation-checklist.md` and `docs/project/evidence/phase1-closeout/external/meta-authenticated-validation-required-2026-02-06-est.md` |

## Google Ads

| Source API object/report | Selected fields | Expected type/unit | Timezone semantics | Currency semantics | Primary key grain | Lookback/latency notes | Destination raw columns | dbt staging columns | `/api/metrics/combined/` usage | validated_on | evidence_link |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Airbyte Google Ads custom GAQL query on `ad_group_ad` | `date_day`, `customer_id`, `campaign_id`, `campaign_name`, `ad_group_id`, `criterion_id`, `ad_name`, `geo_target_region`, `cost_micros`, `currency_code`, `impressions`, `clicks`, `conversions`, `conversions_value` | `cost_micros` integer micros, metrics numeric, IDs text, date string | Source account timezone; sync schedule in `America/Jamaica` | Canonical source field is `customer.currency_code`; spend normalized from micros in dbt | `(tenant_id, customer_id, campaign_id, ad_group_id, criterion_id, date_day)` | Incremental lookback replay for late conversions; manager/customer permission mismatches can block sync | `raw.google_ads_insights`, `raw_google_ads.campaign_daily`, `raw_google_ads.geographic_view` | `stg_google_ads`, `stg_google_campaign_daily`, `stg_google_geographic_view` | Feeds `fact_performance` -> `vw_dashboard_aggregate_snapshot` sections: `campaign`, `creative`, `parish` | 2026-02-06 | `infrastructure/airbyte/google_ads_source.yaml`, `infrastructure/airbyte/sources/google_ads_daily_metrics.sql`, `infrastructure/airbyte/scripts/check_data_contracts.py` |

## GA4 (Pilot Contract, Phase 2)

| Source API object/report | Selected fields | Expected type/unit | Timezone semantics | Currency semantics | Primary key grain | Lookback/latency notes | Destination raw columns | dbt staging columns | `/api/metrics/combined/` usage | validated_on | evidence_link |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Google Analytics Data API `properties.runReport` + metadata preflight `properties.getMetadata` via Airbyte GA4 source template | Initial set: dimensions `date`, `sessionDefaultChannelGroup`, `country`, `city`, `campaignName`; metrics `sessions`, `engagedSessions`, `conversions`, `purchaseRevenue` | Sessions/conversions integer, revenue numeric, dimensions text | Property timezone authoritative; orchestration/runbook baseline remains `America/Jamaica` | Revenue/currency semantics depend on property/ecommerce settings; currency code carried in raw stream | `(tenant_id, property_id, date, channel/campaign dimensions)` | Sampling/thresholding and retention windows depend on property config; metadata validation required before production rollout | `raw.ga4_reports` | `stg_ga4_reports` -> `agg_ga4_daily` | Exposed through `/api/analytics/web/ga4/` (Phase 2 pilot endpoint); not yet merged into `/api/metrics/combined/` | 2026-02-06 (pilot) | `infrastructure/airbyte/ga4_source.yaml`, `dbt/models/staging/stg_ga4_reports.sql`, `dbt/models/marts/agg_ga4_daily.sql`, `backend/analytics/web_views.py` |

## Google Search Console (Pilot Contract, Phase 2)

| Source API object/report | Selected fields | Expected type/unit | Timezone semantics | Currency semantics | Primary key grain | Lookback/latency notes | Destination raw columns | dbt staging columns | `/api/metrics/combined/` usage | validated_on | evidence_link |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Search Console API `searchanalytics.query` via Airbyte Search Console source template | Dimensions `date`, `country`, `device`, `query`, `page`; metrics `clicks`, `impressions`, `ctr`, `position` | Clicks/impressions integers, ctr/position numeric, dimensions text | Date anchored by Search Console source timezone; operational schedule references `America/Jamaica` | No spend/revenue currency | `(tenant_id, site_url, date, dimension tuple)` | Data is delayed and top-row limited; pagination/batching must be tuned per property prior to production rollout | `raw.search_console_performance` | `stg_search_console` -> `agg_search_console_daily` | Exposed through `/api/analytics/web/search-console/` (Phase 2 pilot endpoint); not yet merged into `/api/metrics/combined/` | 2026-02-06 (pilot) | `infrastructure/airbyte/search_console_source.yaml`, `dbt/models/staging/stg_search_console.sql`, `dbt/models/marts/agg_search_console_daily.sql`, `backend/analytics/web_views.py` |

## CSV Upload Pipeline

| Source API object/report | Selected fields | Expected type/unit | Timezone semantics | Currency semantics | Primary key grain | Lookback/latency notes | Destination raw columns | dbt staging columns | `/api/metrics/combined/` usage | validated_on | evidence_link |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Upload API multipart files (`campaign_csv`, optional `parish_csv`, optional `budget_csv`) | Campaign required: `date`, `campaign_id`, `campaign_name`, `platform`, `spend`, `impressions`, `clicks`, `conversions`; Parish required: `parish`, `spend`, `impressions`, `clicks`, `conversions`; Budget required: `month`, `campaign_name`, `planned_budget` | Date/month string normalized to ISO, numeric coercion for spend/metrics, optional revenue/roas/pacing fields | Upload records treated as day/month values; operational schedule/reporting timezone remains `America/Jamaica` | Currency optional per row; fallback/default handled during payload build | Upload snapshot grain by campaign/date and parish/date | Immediate validation at upload; no API lookback | Stored in `TenantMetricsSnapshot` source `upload` (no Airbyte raw table) | Not modeled in dbt for Phase 1 | Directly serves `source=upload` on `/api/metrics/combined/` and can backfill campaign/parish/budget sections | 2026-02-06 | `docs/runbooks/csv-uploads.md`, `backend/analytics/uploads.py`, `frontend/src/lib/uploadedMetrics.ts` |

## Open Validation Actions

1. Meta authenticated portal validation remains a manual external step because Meta developer docs are crawler-restricted.
2. GA4 and Search Console are now Phase 2 pilot contracts with raw/staging/mart + API exposure; production rollout still requires real OAuth credentials and external connector validation.
3. Contract drift gate is enforced by:
   - `python3 infrastructure/airbyte/scripts/check_data_contracts.py`
   - `pytest -q backend/tests/test_data_contract_checks.py`
