# Meta Reporting Compatibility Sprint

Date: 2026-06-23  
Branch: `codex/meta-reporting-compat-audit`  
Timezone baseline: `America/Jamaica`

## Goal

Determine whether the current Meta reporting gaps are caused by Graph API metric drift, stale docs, credential/setup state, sync failures, warehouse readiness, or genuinely missing source rows. Fix only proven bugs and keep report preview/export based on stored aggregate ADinsights data.

## Guardrails

- Keep `META_GRAPH_API_VERSION=v24.0` until a separate compatibility migration is validated.
- Do not add `read_insights`.
- Do not invent Page, Post, or Content Ops values.
- Do not call live Meta providers during report preview/export.
- Do not treat "Meta connected" as equivalent to report/export readiness.
- Keep ad-account state, Facebook Page state, direct sync state, warehouse readiness, and report coverage separate.

## Current Runtime Evidence

Evidence was captured against the visible local SLB report:

- Report ID: `09c96ea9-a9e5-4283-aa29-401179ab05dc`
- Report name: `LOCAL SMOKE - SLB Monthly Social Report May 2026`
- Report schema: `report.v1`
- Template key: `slb_monthly_social_report`
- Requested range: `2026-05-01` through `2026-05-31`
- Evidence user/tenant: `devadmin@local.test`, tenant `ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2`

Local runtime:

- Backend health: OK on `http://localhost:8000/api/health/`
- Frontend: serving from `https://localhost:5173`
- OAuth redirect: `https://localhost:5173/dashboards/data-sources`
- Warehouse adapter: disabled in current local runtime

Stored rows for the report tenant:

| Area                         | Current finding                                                                     |
| ---------------------------- | ----------------------------------------------------------------------------------- |
| Meta marketing credentials   | 1 valid credential                                                                  |
| Meta Page connection         | Active and usable                                                                   |
| Paid Meta rows               | 464 total stored rows, 116 rows in May 2026 availability check                      |
| Paid Meta coverage           | Partial for fixed May range, rows cover `2026-05-02` through `2026-05-31`           |
| Facebook Page insight rows   | 0                                                                                   |
| Facebook posts               | 0                                                                                   |
| Facebook post insight rows   | 0                                                                                   |
| Content Ops published posts  | 0                                                                                   |
| Content Ops metric snapshots | 0                                                                                   |
| Airbyte Meta connection      | Active row exists, last job failed historically with sanitized `meta_token_expired` |

API evidence:

- `GET /api/integrations/social/status/` returns Meta status `complete`, reason `awaiting_recent_successful_sync`, direct sync status `pending`.
- `GET /api/datasets/status/` returns live reporting `adapter_disabled`.
- `GET /api/reports/data-availability/` returns `eligible_for_report_export=false`.
- `GET /api/reports/{id}/diagnostics/` returns `export_ready=false`.

Primary diagnosis for the current local report: `missing/stale/default snapshot`.

Secondary findings:

- Organic Facebook/Page data is missing because Page and Post syncs have run but stored zero Page/Post rows for the selected Page/date range.
- Content Ops is empty because there are no stored published Content Ops posts or aggregate snapshots for the range.
- Paid Meta data is present but partial because May 1 is not covered.
- The report is correctly blocked from export.

## Agent Handoffs

### Meta Orchestrator

Owner route: Raj + Mira

Current decision:

- Implementation may proceed for docs and UX truthfulness only.
- Do not change Graph version or OAuth scopes based on current evidence.
- Do not claim API metric drift until official docs or Graph Explorer verification proves it.

Next handoff:

- Send official-docs verification to Maya + Andre.
- Send UI wording cleanup to Lina + Joel.

### Official Meta API Agent

Owner route: Maya + Andre

Status:

- Official Meta Developer docs were not reachable from this environment during this run because the site returned rate-limit style access failures.
- A logged-in browser or Graph Explorer check is still required before changing the provider metric catalog.

Required verification:

- Confirm current `v24.0` Page Insights provider keys.
- Confirm current `v24.0` Post Insights provider keys.
- Confirm whether `page_media_view`, `page_total_media_view_unique`, `post_media_view`, and `post_total_media_view_unique` are valid defaults.
- Confirm legacy impression keys remain fallback-only or historical-only.
- Confirm no `read_insights` requirement should be reintroduced.

Output target:

- `docs/project/meta-graph-v24-provider-key-audit.md`

### Meta Data/Sync Agent

Owner route: Maya + Leo + Omar

Current finding:

- Credentials and Page auth are usable in the report tenant.
- Direct sync state is not fresh as of 2026-06-23.
- Page/Post sync timestamps exist, but no Page/Post rows are stored for the fixed range.

Next action:

- Run a fresh direct Meta sync from the UI or operator command.
- If Page/Post rows remain zero, verify the selected Page and May 2026 range in Graph Explorer.
- If Graph Explorer shows rows that ADinsights misses, classify as code drift and route to Sofia/Andre.

### Metric Semantics Agent

Owner route: Andre + Sofia

Current finding:

- `backend/integrations/services/metric_registry.py` already maps stable ADinsights product metrics to Graph-v24-aware source keys.
- Legacy Page/Post impression keys are kept as fallbacks, not the first provider key for reporting defaults.

Next action:

- Do not rewrite the registry until official provider verification is complete.
- If drift is proven, update the registry, catalog docs, sync tests, and reporting preview tests together.

### Report UX Agent

Owner route: Lina + Joel + Hannah

Current finding:

- Data Sources direct-sync labels used `Complete` and `Complete (no data)`, which can be misread as report readiness.

Action taken in this branch:

- Changed direct sync labels to `Sync complete` and `Sync complete, no report rows`.
- Wired `POST /api/integrations/meta/sync/` so the Data Sources "Run Meta sync" action also
  attempts the organic Facebook reporting bundle for selected analyzable Pages.
- Added `organic_sync` response metadata and UI toast copy so operators can see whether Page/Post
  work was queued, skipped, completed with no rows, or needs attention.

Additional runtime check:

- Fixed-range local backfill for `organic_facebook_page`, `organic_facebook_posts`, and
  `content_ops` ran against the visible SLB report and selected Page.
- Result: Page Insights returned `0` rows, post discovery/insights returned `0` rows, and Content
  Ops remained blocked because no synced/published Content Ops posts were available for the range.
- Interpretation: the report remains correctly export-blocked until real Page/Post/Content Ops rows
  exist for the selected Page/date range.

### Reporting QA Agent

Owner route: Raj + Omar + Hannah

Checks to keep:

- Report preview/export uses stored aggregate data only.
- Export stays blocked when required coverage is missing or partial.
- No user-level metrics are exposed.
- Tenant isolation stays unchanged.

## Decision Tree

Use this order before making backend changes:

1. If Meta OAuth scopes or Page auth are missing, classify as `permission failure`.
2. If ad account or Page selection is missing, classify as `asset discovery failure`.
3. If direct sync fails or is stale, classify as `direct sync failure`.
4. If sync runs and Graph returns no rows, classify as `provider data unavailable for selected Page/range` until Graph Explorer proves otherwise.
5. If Graph Explorer returns rows that ADinsights does not store, classify as `code drift`.
6. If warehouse is disabled or stale, classify as `warehouse adapter disabled` or `missing/stale/default snapshot`.
7. If report export is blocked because required stored rows are missing, treat that as correct behavior.

## Current Go/No-Go

- Graph/API migration: NO-GO pending official docs or Graph Explorer verification.
- UI truthfulness cleanup: GO.
- Report export readiness: NO-GO because paid coverage is partial and organic/content datasets are missing.
- DashThis cancellation: NO-GO.
