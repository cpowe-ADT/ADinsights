# Meta Reporting Data Path — What's In Use (+ refactor candidates)

Date: 2026-06-25
Scope: the SLB monthly social report path (paid + organic Facebook + Content Ops).
Purpose: record what is actually wired and used today, and flag dead/duplicate/legacy
code for a **later** refactor. This is a map, not a refactor — nothing here is removed yet.

## Live data path (what we are using)

| Concern | Component in use | Notes |
| --- | --- | --- |
| Page token | `MetaPage.decrypt_page_token()` via `integrations.tasks._candidate_page_tokens` | PAGE token, scopes incl. `pages_read_engagement`; falls back to connection (user) tokens. |
| Paid ads | `sync_meta_reporting_slice` → Meta Marketing API → ads tables → `analytics.reporting_preview` | Working (798 rows for SLB). |
| Organic Page insights | `sync_meta_page_insights` → `_sync_page_metric_chunk` → `MetaInsightsGraphClient.fetch_page_insights` (`/{page}/insights`) → `MetaInsightPoint` | **read_insights-gated → returns 200 empty** for SLB. 0 rows. |
| Organic Post insights | `sync_meta_post_insights` → `_sync_post_metric_chunk` → `fetch_post_insights` (`/{post}/insights`) → `MetaPostInsightPoint` | Same read_insights gate → 0 rows. |
| **Organic engagement (NEW)** | `integrations.meta_page_insights.engagement_edges.ingest_engagement_edges` → object **edges** (`?fields=followers_count`, `reactions/comments/shares.summary`) → `MetaInsightPoint(page_follows)` + `MetaPostInsightPoint(post_reactions_total/comments_total/shares_total)` | Uses only `pages_read_engagement`. Real data (6023 followers; per-post engagement). Wired into `slb_backfill_meta_reporting` (organic_facebook_posts). |
| Post discovery | `sync_page_posts` → `MetaInsightsGraphClient.fetch_page_posts` | Fields: `id,message,permalink_url,created_time,updated_time,attachments` — **no engagement** (engagement now comes from the edges module above). |
| Metric validity | `meta_page_insights.insights_discovery.validate_metrics` → `MetaMetricSupportStatus` | Marks `supported=True` on any non-error response (incl. 200-empty). |
| Product↔source keys | `integrations.services.metric_registry` (`map_reporting_source_metric_to_product_metric`, `seed_default_metrics`) | `page_follows` resolves cleanly; the new `post_*_total` keys store + are coverage-recognized. |
| Content Ops | `PublishedPost` import in `slb_backfill_meta_reporting._refresh_content_ops` | Activity-only until post metrics exist. |
| Report render | `analytics.reporting_preview` (reads stored tables only) + `analytics.reporting_source_health` (coverage + truthful messaging) | No live Meta calls during preview/export. |

## Permission gates (external — not code bugs)

- **`read_insights`** — required by Graph v24 for `/{object}/insights` (reach/impressions/clicks).
  Intentionally filtered out of OAuth (`DEFAULT_META_LOGIN_IGNORED_SCOPES` in `integrations/views.py`)
  because Meta rejects unapproved scopes and would break login. → engagement now comes from edges instead.
- **`instagram_basic` / `instagram_manage_insights`** — required for Instagram. Also filtered out for the
  same reason. SLB's IG (`@StudentsLoanBureau`, page-backed IG id `17841404080986070`) is linked but
  unreadable (`/{ig}/media` → error 10) until **Meta App Review** approves the scopes and SLB re-consents.

## Refactor / dead-code candidates (LATER — do not remove yet)

1. **Duplicate scope constants.** `REQUIRED_INSIGHTS_SCOPES = {"pages_read_engagement"}` and
   `_missing_insights_scopes(...)` are defined identically in BOTH `integrations/meta_page_views.py`
   and `integrations/page_insights_views.py`. Consolidate into one shared helper.
2. **Legacy source config.** `integrations/views.py` (~L2438) keeps `legacy_source_config` alongside
   `modern_source_config` in `source_config_candidates`. Confirm whether the legacy shape is still
   produced anywhere; if not, drop it.
3. **Redundant /insights sync for SLB.** While `read_insights` is ungranted, `sync_meta_page_insights`
   / `sync_meta_post_insights` always return 0 rows for engagement-style metrics — the edges module now
   covers engagement. Once the read_insights decision is final, decide whether the /insights sync stays
   (for reach/impressions if approved) or is trimmed to avoid two overlapping ingestion paths.
4. **Misleading "supported" status.** `validate_metrics` / `_mark_metric_support` set `supported=True`
   for metrics that return 200-with-empty-data (read_insights-gated). "Supported" currently means
   "callable without error," not "returns data." Consider a third state (e.g. `callable_no_data`).
5. **Instagram discovery gap.** `MetaGraphClient.list_pages` requests `instagram_business_account` and
   `connected_instagram_account` but never `page_backed_instagram_accounts`, so page-backed IG accounts
   (like SLB's) are never discovered even with scope. Add it when the IG path is built.

## Bug-sweep verdict (2026-06-25)

Reviewed the connectivity path end to end. No new live connectivity bug found beyond the ones already
addressed: the real gap was that **engagement was never fetched** (fixed via the edges module), and the
remaining blockers (`read_insights`, Instagram) are **external Meta App Review gates**, not code defects.
The items above are cleanup, not breakage — safe to leave for the planned refactor.
