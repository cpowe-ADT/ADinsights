# Google Ads Operations Runbook

Timezone baseline: `America/Jamaica`.

Companion doc: `docs/runbooks/google-ads-sdk-migration.md` (OAuth flow, secret rotation, initial migration context). This runbook covers **ongoing operation** of the Google Ads surface after the SDK-with-Airbyte-fallback migration shipped.

## Scope

Operate the Google Ads workspace and its ten tab sections for all tenants:

- `integrations.models.GoogleAdsSdkAccount` / `GoogleAdsSdkCampaign` / `GoogleAdsSdkCampaignDaily` / `GoogleAdsSdkAdGroup` / `GoogleAdsSdkKeyword` / `GoogleAdsSdkConversion` / `GoogleAdsSdkAsset` / `GoogleAdsSdkAssetGroup` / `GoogleAdsSdkChangeEvent` / `GoogleAdsSdkRecommendation` — tenant-scoped ORM tables populated by the direct-SDK ingestion worker.
- `integrations.models.CampaignBudget` — manually-entered budget targets used by the pacing tab. Keyed `(tenant, name)` — **no FK to campaign** (see §Known quirks).
- `analytics.models.GoogleAdsSavedView` — user-authored filter/column presets powering the Reports tab.
- `backend.analytics.google_ads_views` — the DRF view layer exposing `/api/analytics/google-ads/…` endpoints consumed by the frontend workspace.
- `frontend/src/routes/google-ads/GoogleAdsWorkspacePage.tsx` — the workspace shell that mounts the ten tab sections.

## SDK-vs-Airbyte hybrid architecture

Two ingestion paths coexist by design:

1. **Direct SDK** — `backend.integrations.google_ads` uses the pinned `google-ads-python v23` SDK to fetch campaign/keyword/asset/conversion rows per-tenant. This is the primary path; it populates all `GoogleAdsSdk*` ORM tables. The SDK call is tenant-scoped using the tenant's refresh token. Rate-limit caps are enforced per customer-id by Google.
2. **Airbyte fallback** — `infrastructure/airbyte/google_ads_source.yaml` + dbt marts (`stg_google_ads_*`, `agg_google_ads_daily`). This path exists for tenants whose SDK connection is degraded, or for post-migration backfills. The `ENABLE_WAREHOUSE_ADAPTER` env flag routes combined-metrics reads through the Airbyte marts.

The frontend workspace (`GoogleAdsWorkspacePage`) always reads from the SDK tables via `/api/analytics/google-ads/…` endpoints. The Airbyte/warehouse path only serves the cross-platform combined-metrics endpoint.

## Endpoint register

| Tab                        | Endpoint                                                      | View class                           | Notes                                                                                                            |
| -------------------------- | ------------------------------------------------------------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| Overview                   | `GET /analytics/google-ads/summary/`                          | `GoogleAdsSummaryView`               | Aggregate KPIs across selected customer_ids                                                                      |
| Campaigns                  | `GET /analytics/google-ads/campaigns/`                        | `GoogleAdsCampaignsView`             | Per-campaign performance rows                                                                                    |
| Search (keywords mode)     | `GET /analytics/google-ads/keywords/`                         | `GoogleAdsKeywordsView`              | Filters via `GoogleAdsListQuerySerializer`                                                                       |
| Search (search_terms mode) | `GET /analytics/google-ads/search-terms/`                     | `GoogleAdsSearchTermsView`           | Prefetched alongside keywords for the top-10 chart                                                               |
| Assets                     | `GET /analytics/google-ads/assets/`                           | `GoogleAdsAssetsView`                | Text/image/video asset inventory                                                                                 |
| PMax                       | `GET /analytics/google-ads/asset-groups/`                     | `GoogleAdsAssetGroupsView`           | Performance Max treemap + ROAS palette                                                                           |
| Conversions                | `GET /analytics/google-ads/conversions/`                      | `GoogleAdsConversionsView`           | Conversion actions + daily series                                                                                |
| Pacing                     | `GET /analytics/google-ads/budgets/pacing/`                   | `GoogleAdsBudgetPacingView`          | Tenant rollup + per-campaign rows (Phase A). Response cached 15 min per `(tenant, customer_ids_hash, end_date)`. |
| Changes                    | `GET /analytics/google-ads/change-events/`                    | `GoogleAdsChangeEventsView`          | Paginated via `?page=N&page_size=K`; response includes `next_cursor` (Phase B)                                   |
| Recommendations (list)     | `GET /analytics/google-ads/recommendations/`                  | `GoogleAdsRecommendationsView`       | Includes `id`, `dismissed_at`, `dismissed_by_user_id`                                                            |
| Recommendations (dismiss)  | `POST /analytics/google-ads/recommendations/<pk>/dismiss/`    | `GoogleAdsRecommendationDismissView` | **LOCAL ONLY** — no upstream SDK `DismissRecommendation` call. Writes AuditLog.                                  |
| Reports (list)             | `GET /analytics/google-ads/saved-views/`                      | `GoogleAdsSavedViewViewSet` (list)   | Tenant-scoped; honors `is_shared`                                                                                |
| Reports (verify)           | `GET /analytics/google-ads/saved-views/<pk>/verify/`          | `GoogleAdsSavedViewViewSet.verify`   | Schema-drift check against v23 whitelist (Phase B)                                                               |
| Reports (export create)    | `POST /analytics/google-ads/reports/export/`                  | `GoogleAdsReportExportCreateView`    | Creates `ReportExportJob`                                                                                        |
| Reports (export status)    | `GET /analytics/google-ads/reports/export/<job_id>/status/`   | `GoogleAdsReportExportStatusView`    | Polled by frontend 3s→60s exp-backoff                                                                            |
| Reports (export download)  | `GET /analytics/google-ads/reports/export/<job_id>/download/` | `GoogleAdsReportExportDownloadView`  | Returns pre-signed URL                                                                                           |

All endpoints require `Authorization: Bearer <JWT>` and enforce tenant isolation via `TenantAwareManager` + `request.user.tenant_id` filter.

## Day-2 operations

### Tenant onboarding triage order

Use this order when a tenant reports "Google Ads dashboard is empty":

1. `GET /api/integrations/social/status/` — is Google Ads OAuth complete? If `not_connected` / `started_not_complete`, direct user to Data Sources page to finish OAuth.
2. `GET /api/datasets/status/` — does the dataset report live-ready? If not, inspect `live_reason`.
3. `GET /api/integrations/google-ads/accounts/` — does the tenant have any linked customer_ids? If empty, user needs to pick accounts.
4. Direct-SDK sync worker logs (`backend.integrations.google_ads.tasks`) — is the last sync recent and successful?
5. For any 500s on `/analytics/google-ads/…`, check Django logs for `TenantAwareManager` filtering — a missing `tenant_id` on `request.user` is the typical root cause in dev.

### Pacing tab cache invalidation

Pacing endpoint caches its payload 15 minutes under cache key `ga_pacing_v1:<tenant_id>:<sha1(customer_ids)>:<end_date>`. To force a refresh without waiting:

```python
from django.core.cache import cache
cache.delete_pattern("ga_pacing_v1:*")  # if django-redis
# or more targeted:
cache.delete("ga_pacing_v1:<tenant>:<hash>:<end_date>")
```

The UI always surfaces `cache.served_from_cache` so operators can confirm whether a given page load hit the cache.

### Recommendation dismiss posture

Dismiss is **LOCAL ONLY** by design (v2 prompt decision, April 2026). Dismissing a recommendation sets `dismissed_at` + `dismissed_by` on the `GoogleAdsSdkRecommendation` row and writes an `AuditLog` event (`action="google_ads_recommendation_dismissed"`). It **does not** call Google's `RecommendationService.DismissRecommendation` upstream — that mutation has a different risk profile (mutates the customer's live Google Ads account) and requires a separate product review.

A regression test (`test_dismiss_has_no_sdk_call`) enforces this: the backend grep of production `.py` files excluding the vendored SDK must return zero hits for `DismissRecommendation`.

### Saved-view drift banner

Phase B added a banner in the Reports tab that surfaces when any saved view references a filter key or column name not in the current backend's v23 whitelist. The whitelists (`KNOWN_FILTER_KEYS`, `KNOWN_COLUMN_KEYS` in `backend/analytics/google_ads_views.py`) are **manually maintained**. When a PR adds a new filter key or column to the saved-view persistence path, the whitelist must be updated in the same PR — otherwise every new saved view using that key will trigger the drift banner.

## Known quirks

- **`CampaignBudget` keyed by name, not campaign id.** The model's unique key is `(tenant, name)`, not a FK to `GoogleAdsSdkCampaign`. The Pacing endpoint's per-campaign budget match is therefore best-effort by case-insensitive name. Unmatched campaigns surface `budget_amount=null` and render `"—"` in the UI's pace/variance cells. A future `CampaignBudget.campaign_id` FK migration would let us match 100% accurately.
- **Changes endpoint uses page-based pagination**, not cursor. The `next_cursor` response field is an alias: `str(page+1) if has_next else None`. A stricter opaque-cursor implementation would be slightly more correct under concurrent inserts, but page-based is fine for this dataset (changes log is mostly historical; new events accumulate at the top).
- **`ENABLE_META_DIRECT_ADAPTER` and `ENABLE_WAREHOUSE_ADAPTER`** control combined-metrics routing but have no effect on the Google Ads workspace — the workspace always reads from SDK tables directly.

## Related docs

- `docs/runbooks/google-ads-sdk-migration.md` — OAuth, secrets, initial migration
- `docs/project/integration-data-contract-matrix.md` — source→API field mapping
- `artifacts/sprint/S5-google-ads-finish-closeout.md` — Phase A delivery
- `artifacts/sprint/S5-google-ads-phase-b-closeout.md` — Phase B delivery
- `artifacts/roadmap/google-ads-completion-plan.md` — full phase plan
