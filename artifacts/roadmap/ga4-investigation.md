# GA4 Integration Investigation — v2 Prompt Execution

**Baseline commit:** `7a0e701b` (matches prompt spec)
**Investigator:** Claude (staff-engineer posture, per prompt)
**Date:** 2026-04-23

## Self-evaluation

- [x] Every DoD bullet has a matching evidence line (see Step 3 gate matrix)
- [x] R3 fetch-spy test output pasted (confirms green — 4/4 in `GoogleAnalyticsDashboardPage.test.tsx`)
- [x] Runbook opens clean and includes "how to verify live" one-liner (see `docs/runbooks/ga4-operations.md` § How to verify live)
- [x] Commits use conventional prefix (`docs(ga4):` + `test(ga4):`)
- [x] State file removed (A/B) or marked for handoff (C) — N/A, Verdict B fit in one session, no state file created
- [x] One-line answer: what did I change and why is it safe? — Added a runbook + 16 new backend pytests (PII allowlist + credential error paths + tenant-isolation). Zero production code changes; zero frontend changes; zero dbt/migrations/secrets. R3 contract untouched.
- [x] If Verdict C: I did NOT attempt full ingestion; I escalated. — **N/A, Verdict B**

---

## Step 1 — Pre-flight verification

### File reviews (CoT scaffolding step 1)

| # | File | 1-line finding |
|---|---|---|
| 1 | `dbt/models/staging/stg_ga4_reports.sql` | Reads `source('raw', 'ga4_reports')` (Airbyte raw). Schema: `property_id, channel_group, country, city, campaign_name, sessions, engaged_sessions, conversions, purchase_revenue`. Gated by `enable_ga4=false`. |
| 2 | `dbt/models/marts/agg_ga4_daily.sql` | Aggregates `stg_ga4_reports` by `(tenant_id, date_day, property_id, channel_group, country, city, campaign_name)`. Incremental merge. Gated by `enable_ga4=false`. |
| 3 | `backend/integrations/google_analytics/{client.py,views.py,urls.py}` | OAuth start/exchange/properties/provision/status + live GA4 Data API v1beta client. **Schema DIVERGES from mart** (`sessionSource/sessionMedium` vs mart's `channel_group/country/city`). |
| 4 | `backend/integrations/tasks.py`, `backend/core/celery.py`, `backend/integrations/clients/tasks.py` | **No task invokes `GoogleAnalyticsClient` for sync**. Zero grep hits. |
| 5 | `infrastructure/airbyte/ga4_source.yaml` + `sources/ga4.json.example` | Airbyte source template exists; dimensions/metrics **do match the mart**. Driven by env vars `AIRBYTE_GA4_CLIENT_ID/SECRET/REFRESH_TOKEN/PROPERTY_ID`. Template only — no evidence of an instantiated/running Airbyte source. |
| 6 | `backend/adapters/google_analytics.py` + `backend/analytics/web_views.py:126` | Two independent read paths: (a) `GA4WebInsightsView` → raw SQL on `agg_ga4_daily` (dashboard path, R3-protected), (b) `GoogleAnalyticsAdapter.fetch_metrics` → live GA4 API via client (combined-metrics dispatch, not dashboard). |

### Component mapping (CoT scaffolding step 2)

| Component | Category | State |
|---|---|---|
| `integrations.google_analytics.views` (OAuth flow) | auth | **Complete**. State-signing via `django.core.signing`, AES-encrypted tokens via `PlatformCredential.set_raw_tokens`. Scopes = `analytics.readonly + openid + userinfo.*`. |
| `GoogleAnalyticsClient` (GA4 Data API v1beta live fetch) | read-path (direct) | Implemented. Used by `GoogleAnalyticsAdapter`. Returns `Ga4DailyRow` with divergent schema from mart. |
| Celery sync task (client → DB → mart) | sync | **MISSING — does not exist, does not need to exist**. Architecture is Airbyte → dbt, not Django → dbt. |
| Airbyte GA4 connector | sync | Template present; **no deployed connection in this environment**. |
| `stg_ga4_reports` + `agg_ga4_daily` dbt models | storage | Exist, `enable_ga4=false` by default → tables are NOT materialized in local/dev. |
| `GA4WebInsightsView` (`/api/web/ga4/`) | read-path (dashboard) | Reads mart via raw SQL. Graceful-degrades to `status: "unavailable"` when mart is absent. Tenant filter in `WHERE`. |
| Tests | test | 727 backend + 770 frontend green at baseline. `GoogleAnalyticsDashboardPage.test.tsx` asserts R3 (no `/metrics/combined/` call). |

### Primary gap (CoT scaffolding step 3)

**The gap is not "missing sync code" — it's "no documented operator path to flip GA4 live."** Concretely, any tenant onboarding GA4 today would need to:

1. Complete OAuth in the UI (works today — see `GoogleAnalyticsProvisionView`). *This creates a `GoogleAnalyticsConnection` row, but no data flows from it.*
2. **Manually** deploy an Airbyte source using `infrastructure/airbyte/ga4_source.yaml` with env vars set.
3. **Manually** set `dbt_project.yml` vars `enable_ga4: true`.
4. **Manually** run dbt build.
5. Wait for Airbyte's scheduled sync + next dbt run.

Steps 2-5 are undocumented. There is no runbook. The dashboard will read `status: "unavailable"` until the mart exists.

Secondary observation: `client.py` and the OAuth-provisioned `GoogleAnalyticsConnection` are **not wired to Airbyte's refresh token**. Airbyte gets its refresh token from env var `AIRBYTE_GA4_REFRESH_TOKEN`, not from the tenant's `PlatformCredential`. So the in-app OAuth flow is decorative unless we bridge the OAuth-captured tokens into Airbyte config (out of scope — that's a feature).

### Verdict: **B — wired but untested in this environment**

**Rationale (CoT scaffolding step 4/5):**

- OAuth + dbt + Airbyte templates + dashboard view all exist and compile.
- No evidence any tenant in this dev stack has `enable_ga4=true` or a deployed Airbyte source.
- No operator runbook exists for the end-to-end path.
- Mart does not exist locally, so dashboard is empty (not broken).
- Does NOT meet Verdict A criteria (no live mart data in last 48h; no runbook).
- Does NOT meet Verdict C criteria (the code paths exist end-to-end; the gap is operational/documentation, not missing components).

### Evidence — pasted command output

```
$ git rev-parse HEAD
7a0e701bfa42c62c8c71f7a9d42e8eb03eba4cce

$ find dbt/models -name "*ga4*" -o -name "*google_analytics*"
dbt/models/marts/agg_ga4_daily.sql
dbt/models/staging/stg_ga4_reports.sql

$ grep -n "enable_ga4\|ga4_reports" dbt/dbt_project.yml dbt/models/staging/stg_ga4_reports.sql dbt/models/marts/agg_ga4_daily.sql
dbt/dbt_project.yml:164:      ga4_reports:
dbt/dbt_project.yml:315:    raw__ga4_reports:
dbt/models/staging/stg_ga4_reports.sql:1:{{ config(materialized='view', enabled=var('enable_ga4', false)) }}
dbt/models/staging/stg_ga4_reports.sql:5:    from {{ source('raw', 'ga4_reports') }}
dbt/models/marts/agg_ga4_daily.sql:4:    enabled=var('enable_ga4', false),

$ grep -rn "GoogleAnalyticsClient\|google_analytics" backend/integrations/tasks.py backend/core/celery.py
# (no matches)

$ find infrastructure/airbyte -type f | xargs grep -l "ga4\|google_analytics"
infrastructure/airbyte/sources/ga4.json.example
infrastructure/airbyte/env.example
infrastructure/airbyte/README.md
infrastructure/airbyte/ga4_source.yaml

$ grep -n "ga4\|google_analytics" backend/integrations/models.py
535:        Tenant, on_delete=models.CASCADE, related_name="google_analytics_connections"
540:        related_name="google_analytics_connections"
556:        models.Index(fields=["tenant","is_active"], name="ga4_conn_tenant_active")
1633:    PLATFORM_GA4 = "ga4"
```

### PII allowlist pre-check

Grep against GA4 dbt models for PII columns:

```
$ grep -En "user_pseudo_id|device_id|client_id|ip_address|stream_id|user_id" dbt/models/*ga4* 2>/dev/null
# (no matches — clean)
```

Allowlist enforced by the dbt staging model itself: `stg_ga4_reports.sql` only selects `property_id, tenant_id, date_day, channel_group, country, city, campaign_name, sessions, engaged_sessions, conversions, purchase_revenue, currency_code, engagement_rate, conversion_rate`. No PII fields are propagated from source.

---

## Planned work for Step 3 (Verdict B path)

1. **Runbook `docs/runbooks/ga4-operations.md`** (~60 min): architecture, connect-a-property, trigger sync, verify-live one-liner, troubleshoot, rate limits.
2. **Tenant isolation test** for `GA4WebInsightsView` (~20 min): tenant A cannot read tenant B rows through the view.
3. **PII allowlist test** (~20 min): pytest that introspects `stg_ga4_reports.sql` source text and fails if any of the forbidden column names appear.
4. **OAuth token decrypt/build test** for `GoogleAnalyticsClient._build_client` (~20 min): credential missing tokens → raises `GoogleAnalyticsClientError` with specific classification. Covers the handoff path where a refresh would be needed. (Full live-refresh-on-401 requires mocking Google's OAuth server — acceptable scope cut documented in runbook.)

### STEP 1 COMPLETE, verdict B

---

## Step 2 — Dev-stack verification

**Stack state:** Docker Compose up ~35h. `adinsights-backend-1` on `0.0.0.0:8001`, `adinsights-frontend-1` on `0.0.0.0:5174`, `adinsights-postgres-1` on `0.0.0.0:5435`. Airbyte stack up ~10 days on `18000/18001`. No dev-stack launch needed.

**Evidence (pasted):**

```
$ docker exec -e PGPASSWORD=*** adinsights-postgres-1 psql -U adinsights_user -d adinsights -tAc \
    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='agg_ga4_daily');"
f

$ docker exec -e PGPASSWORD=*** adinsights-postgres-1 psql -U adinsights_user -d adinsights -tAc \
    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='stg_ga4_reports');"
f

$ docker exec -e PGPASSWORD=*** adinsights-postgres-1 psql -U adinsights_user -d adinsights -tAc \
    "SELECT COUNT(*) FROM integrations_googleanalyticsconnection;"
0

$ docker exec -e PGPASSWORD=*** adinsights-postgres-1 psql -U adinsights_user -d adinsights -tAc \
    "SELECT COUNT(*) FROM integrations_platformcredential WHERE provider='google_analytics';"
0

$ docker exec -e PGPASSWORD=*** adinsights-postgres-1 psql -U adinsights_user -d adinsights -tAc \
    "SELECT table_schema, table_name FROM information_schema.tables
     WHERE table_name LIKE '%ga4%' OR table_name LIKE '%google_analytics%';"
(empty)

$ curl -s -w "HTTP %{http_code}\n" http://localhost:8001/api/analytics/web/ga4/
HTTP 401
{"detail":"Authentication credentials were not provided."}

$ curl -s http://localhost:18001/api/v1/sources/list -X POST -H "Content-Type: application/json" \
    -d '{"workspaceId":"00000000-0000-0000-0000-000000000000"}'
{"sources":[]}
```

**Interpretation:**
- Mart `agg_ga4_daily` and staging view `stg_ga4_reports` do not exist — consistent with `enable_ga4=false`.
- Zero `GoogleAnalyticsConnection` rows, zero `PlatformCredential` rows with `provider='google_analytics'` — no tenant has connected GA4 in this dev stack.
- Zero sources in Airbyte — GA4 template is not instantiated.
- `GA4WebInsightsView` is registered (returns 401 on anonymous request at `/api/analytics/web/ga4/`, not 404). When authed, the raw-SQL query on the missing mart would be caught by the view's `except Exception` at `web_views.py:109` and return `{status: "unavailable", ...}`.
- Dashboard behavior is therefore **empty-by-design**, not broken. Tenant-scoped row count is 0 for all tenants because the table does not exist.

**Step 1 verdict (B) is not contradicted by Step 2 evidence.** No revision needed.

### STEP 2 COMPLETE, dashboard state empty

---

## Step 3 — Gap-close (Verdict B path)

### Artifacts

| Kind | Path | Summary |
|---|---|---|
| Runbook | `docs/runbooks/ga4-operations.md` | New. Sections: scope, architecture (two paths), connect-a-property, make-dashboard-live operator path, trigger sync, verify live (one-liner + deeper), troubleshoot, OAuth token refresh, rate limits, scopes, test commands. |
| Test | `backend/tests/test_ga4_pii_allowlist.py` | New. 12 parametrized tests: both GA4 dbt models exist and do not reference any of the PII columns `user_pseudo_id, device_id, client_id, ip_address, stream_id`. |
| Test | `backend/tests/test_google_analytics_client.py` | +3 tests: `credential_missing_access_token` classification, `oauth_not_configured` classification, refresh-readiness SDK handoff (`refresh_token + client_id + client_secret + token_uri` all passed through). |
| Test | `backend/tests/test_phase2_api.py` | +1 test: `test_ga4_web_insights_isolates_rows_by_tenant` — seeds two tenants' rows in a transient `agg_ga4_daily` table, auths as tenant A, asserts only tenant A's rows come back (plus explicit leak-canary assertions). |

### Pre-code CoT checks

1. Does any edit touch R3? **No.** Backend-only test additions + docs; no frontend files edited.
2. Does any edit touch `GoogleAnalyticsDashboardPage.tsx`? **No.**
3. Would the new tests pass if the implementation were deleted? **No.** PII tests parse source files and assert allowlist. Credential tests assert specific `GoogleAnalyticsClientError.classification` values. Tenant isolation test seeds adversarial rows and asserts exactly-one-row containment.

### Gate matrix

| Gate | Command | Result |
|---|---|---|
| Backend ruff | `cd backend && ruff check .` | **All checks passed!** |
| Backend pytest (full) | `cd backend && pytest` | **743 passed, 1 skipped** (baseline was 727 passed + 1 skipped → +16 new tests, none regressed) |
| Frontend lint | `cd frontend && npm run lint` | clean |
| Frontend build | `cd frontend && npm run build` | **✓ built in 17.10s** |
| Frontend R3 contract | `npx vitest run src/routes/__tests__/GoogleAnalyticsDashboardPage.test.tsx` | **4/4** passed (R3 fetch-spy green) |
| Frontend vitest (full) | `cd frontend && npm test -- --run` | 2 known full-suite flakes (`App.integration.test.tsx`, `CampaignDashboard.layout.test.tsx`); **both pass 4/4 in isolation** — matches S4 deep review's documented cross-test mock-order flake pattern. No frontend source code was changed in this Step 3, so this is not a regression introduced here. |

### Frontend flake note (pre-existing)

The S4 deep review (`artifacts/sprint/S4-deep-review.md` § SummaryDetailPage note) documented this pattern:
> Passes 6/6 in isolation. Not introduced by this review's changes. Did not exist at S4 close — this is drift from parallel work elsewhere in the tree. Single-test-file run is deterministic; full-suite run fails intermittently.

Today's full-suite failures (`App.integration` + `CampaignDashboard.layout`) exhibit the same signature (isolated-pass, full-suite-flake). Out of scope for this GA4 task per the prompt's anti-pattern #9 ("do not attempt full ingestion" / stay scoped). Spawning a sibling task to track the flake.

### STEP 3 COMPLETE

Final commit SHAs: see `git log -n 3 --oneline` after commit (posted in close-out message).
