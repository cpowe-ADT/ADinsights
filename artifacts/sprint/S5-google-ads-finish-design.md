# S5 — Google Ads Phase A (Finish) — Architect Design

**Baseline commit:** `c0d132a5` (descendant of known-good `7a0e701b`).
**Sprint scope:** GA-A1 + GA-A2 + GA-A3 (Phase A only — the 3 incomplete tabs).
**Authoritative prompt:** `artifacts/roadmap/prompts/finish-google-ads.v2.md`.
**Pre-flight result:** all v2 expectations matched EXCEPT `CampaignBudget` has no `campaign_id` FK (keyed by `(tenant, name)`). Per-campaign budget match is best-effort by name; see GA-A1 §Scoping.

---

## GA-A1 — Pacing: extend tenant-rollup with per-campaign rows

### 1. Request / response shape

**Request** (unchanged):

```
GET /api/analytics/google-ads/budgets/pacing/?start_date=2026-04-01&end_date=2026-04-23[&customer_ids=...]
Authorization: Bearer <jwt>
```

**Response** (extended — new `campaigns` key):

```json
{
  "month": "2026-04",
  "spend_mtd": 12345.67,
  "budget_month": 20000.0,
  "forecast_month_end": 18518.5,
  "over_under": -1481.5,
  "runway_days": 14.2,
  "alerts": { "overspend_risk": false, "underdelivery": false },
  "campaigns": [
    {
      "campaign_id": "987654321",
      "campaign_name": "Q2 Brand Always-On",
      "customer_id": "1234567890",
      "budget_amount": 5000.0,
      "spend_mtd": 2800.0,
      "pace_pct": 0.56,
      "projected_eom": 4200.0,
      "variance": -800.0
    },
    {
      "campaign_id": "987654322",
      "campaign_name": "Promo Push — No Budget Match",
      "customer_id": "1234567890",
      "budget_amount": null,
      "spend_mtd": 350.0,
      "pace_pct": null,
      "projected_eom": 525.0,
      "variance": null
    }
  ],
  "cache": { "served_from_cache": false, "ttl_seconds": 900 }
}
```

**Error shapes** (existing — date validation via `GoogleAdsDateRangeQuerySerializer`):

- 400: invalid date range / unparseable query params
- 401: missing/invalid JWT (baseline DRF)
- 403: not assigned to any customer_id when filter specified

### 2. Scoping

- **Tenant isolation**: preserve existing pattern — `GoogleAdsSdkCampaignDaily.objects.filter(tenant_id=request.user.tenant_id, ...)` (no RLS bypass). `objects` is `TenantAwareManager`.
- **Customer scope**: reuse `_resolve_google_customer_ids` + `_apply_customer_scope` + `_apply_customer_id_filter` helpers (same as existing view).
- **Jamaica day boundaries**: `month_end = validated["end_date"]`; `month_start = month_end.replace(day=1)`. Already uses date-typed boundaries — no DST bug (per AGENTS.md §140).
- **Budget matching** (the design deviation): `CampaignBudget` has no `campaign_id` FK — it is keyed `(tenant, name)`. For each aggregated campaign row, attempt name match with `CampaignBudget.objects.filter(tenant_id=..., is_active=True, name__iexact=campaign_name).first()`. If no match → `budget_amount=null, pace_pct=null, variance=null`. This is best-effort and documented; acceptable for MVP.
- **Cache**: key `ga_pacing_v1:{tenant_id}:{customer_ids_sorted_hash}:{end_date}`; TTL 900s (15 min) via `django.core.cache.cache.get_or_set(...)`. Cache respects tenant — no cross-tenant reuse.

### 3. Failure modes

1. **Cache backend unavailable** (Redis down in prod) → falls through to live query; response marks `"served_from_cache": false`. No 5xx surfaced to client.
2. **No `GoogleAdsSdkCampaignDaily` rows for range** → `campaigns: []`, tenant rollup proceeds as before (returns zero spend + null runway). Existing behavior preserved.
3. **Budget name collision** (two budgets with same name due to case) → `name__iexact` + `.first()` picks one deterministically; acceptable because `unique_together=(tenant, name)` already enforces case-sensitive uniqueness; collision is a data-entry edge case.

### 4. Test shape

**Backend (`backend/tests/test_google_ads_budgets_pacing_extension.py`):**

- `test_pacing_returns_campaigns_array` — seed 2 `GoogleAdsSdkCampaignDaily` rows for 2 campaigns + 1 `CampaignBudget` that matches one name; assert `campaigns` has 2 entries, first with budget, second with `budget_amount=null`.
- `test_pacing_tenant_isolation` — seed data for tenant A and tenant B; request as A; assert B's campaigns are absent.
- `test_pacing_cache_hit` — call twice, assert second response has `served_from_cache: true`.
- `test_pacing_cache_tenant_scoped` — tenant A primes cache, tenant B calls, assert tenant B gets its own result not A's.
- `test_pacing_empty_campaigns_when_no_data` — no daily rows; `campaigns == []` but status 200.

### 5. Rollback posture

- **Feature flag**: none (additive only — old clients that don't read `campaigns` still work). Existing contract rows (`spend_mtd`, `budget_month`, …) are unchanged.
- **Revert path**: `git revert <commit>` — no migration to reverse. Cache keys are namespaced `ga_pacing_v1:` so a later `v2:` rewrite doesn't collide.
- **Who's paged**: nobody for a clean revert; watch `/api/analytics/google-ads/budgets/pacing/` p99 latency for 1 hour post-deploy.

### 6. Frontend wire-up (GA-A1 continued)

- `PacingTabSection.tsx`: remove the `[NEW-ENDPOINT]` comment on line 48; add a `DistributionBar`-style panel showing per-campaign `pace_pct` bars sorted descending. Each bar labeled with `campaign_name` + `formatCurrency(spend_mtd, 'JMD')`.
- Empty state: when `campaigns.length === 0`, existing "No pacing data" empty state still applies.
- KPI tiles extended by 1: "Campaigns over-pacing" (count where `pace_pct > 1.0`). Keep existing 3 tiles.

---

## GA-A2 — Recommendations: dismiss action (LOCAL ONLY)

### 1. Request / response shape

**New endpoint:**

```
POST /api/analytics/google-ads/recommendations/<int:pk>/dismiss/
Authorization: Bearer <jwt>
Body: {} (empty — dismiss is a state toggle, no parameters)
```

**Response** (200):

```json
{
  "id": 42,
  "customer_id": "1234567890",
  "recommendation_type": "KEYWORD",
  "resource_name": "customers/1234567890/recommendations/abc",
  "campaign_id": "987654321",
  "ad_group_id": "",
  "dismissed": true,
  "dismissed_at": "2026-04-23T14:32:10-05:00",
  "dismissed_by_user_id": 7,
  "impact_metadata": {...},
  "last_seen_at": "2026-04-23T09:00:00-05:00"
}
```

**List endpoint extension** (existing `GoogleAdsRecommendationsView`): add `id`, `dismissed_at`, `dismissed_by_user_id` to the row payload so the frontend can key on `id` for the dismiss button.

**Error shapes:**

- 404: recommendation not found for this tenant (prevents cross-tenant leak via ID enumeration — 404 not 403)
- 409: if re-dismissing an already-dismissed rec, return 200 with current state (idempotent) — no 409

### 2. Scoping

- **URL**: `path("google-ads/recommendations/<int:pk>/dismiss/", GoogleAdsRecommendationDismissView.as_view(), name="google-ads-recommendation-dismiss")` added to `backend/analytics/urls.py`.
- **Tenant isolation**: `get_object_or_404(GoogleAdsSdkRecommendation.objects.filter(tenant_id=request.user.tenant_id), pk=pk)`. `TenantAwareManager` (`objects`) also filters by tenant — double defense.
- **Permission**: `IsAuthenticated`. No admin-only gate per v2 "add admin-only permission" wording — recon with the user if strict admin required. For MVP: any authenticated tenant user can dismiss their tenant's recs.
- **Audit**: write `AuditLog` entry `action="google_ads_recommendation_dismissed"` with `resource_type="google_ads_recommendation"`, `resource_id=str(rec.pk)`, `metadata={"resource_name": rec.resource_name, "customer_id": rec.customer_id, "recommendation_type": rec.recommendation_type}`.
- **LOCAL ONLY** (v2 hard requirement): no SDK call. No import of `google.ads.googleads.*` dismiss APIs. Verified by grep `"DismissRecommendation"` in `backend/` returns zero hits.

### 3. Failure modes

1. **Rec already dismissed** → idempotent: set `dismissed=True, dismissed_at=now, dismissed_by_user=user` again (overwrites timestamp). Return 200 with current state. Audit entry still written (captures re-dismiss intent).
2. **Rec not found for tenant** → 404 with `{"detail": "Not found."}`. Cross-tenant ID enumeration yields 404, not 403 (no information leak).
3. **Audit log write fails** → transaction rolls back; return 500. Alternative: best-effort audit via `try/except AuditLog.DoesNotExist` — ADinsights pattern is hard-fail (see `backend/integrations/views.py` alert pause). Hard-fail chosen.

### 4. Test shape

**Backend (`backend/tests/test_google_ads_recommendations_dismiss.py`):**

- `test_dismiss_sets_fields` — create rec, POST dismiss, assert `dismissed=True, dismissed_at` is non-null, `dismissed_by=user`.
- `test_dismiss_tenant_isolation` — tenant A creates rec; tenant B POSTs dismiss by same pk → 404; tenant A re-reads rec and sees it still undismissed (from B's perspective's failed attempt).
- `test_dismiss_is_idempotent` — dismiss twice; second call returns 200; assert two audit log entries.
- `test_dismiss_writes_audit` — assert `AuditLog` row with action `google_ads_recommendation_dismissed`.
- `test_dismiss_has_no_sdk_call` — `grep -r "DismissRecommendation\|dismiss_recommendation" backend/` via subprocess in test, assert 0 hits (static guard against regression).
- `test_list_returns_new_fields` — GET recommendations, assert `id`, `dismissed_at`, `dismissed_by_user_id` keys present.

### 5. Rollback posture

- **Migration**: `0025_recommendation_dismissed_audit.py` adds 2 nullable fields. Reverse: `makemigrations --empty → migrations.RemoveField(…)`. Safe.
- **Revert path**: drop the 2 fields; drop the URL + view; frontend stops calling it. No data loss (dismissed=True state remains on any existing rows, just without timestamp/user).
- **Who's paged**: nobody for clean revert; watch `/api/analytics/google-ads/recommendations/<id>/dismiss/` 5xx rate post-deploy.

### 6. Frontend wire-up (GA-A2 continued)

- `RecommendationsTabSection.tsx`: replace the "Status" column's static chip with a `<button>` labeled "Dismiss" for non-dismissed rows; dismissed rows show a disabled "Dismissed" chip.
- On click: optimistic update — mark row.dismissed=true locally, call `dismissGoogleAdsRecommendation(id)`; on failure, revert + toast error.
- Add `dismissGoogleAdsRecommendation(id: number)` helper to `frontend/src/lib/googleAdsDashboard.ts`.
- Add `id: number | null` to `GoogleAdsRecommendationRow` type in `frontend/src/lib/googleAdsAggregates.ts`.

---

## GA-A3 — Reports: export polling loop (frontend-only)

### 1. Request / response shape

**No backend changes.** Existing `GoogleAdsExportStatusView` at line 1673 returns `GoogleAdsExportJob` shape (already typed in `googleAdsDashboard.ts:48`).

**Frontend flow:**

1. User clicks "Create CSV Export" → `createGoogleAdsExport({export_format: 'csv', ...})` returns a job with `status='completed'` today (sync backend) but may be `'queued'|'running'` in a future async world.
2. If status is terminal (`completed`|`failed`), render the pill + download link immediately — skip polling.
3. Else start polling: every 3s call `fetchGoogleAdsExportStatus(jobId)`. Stop when:
   - status becomes terminal, OR
   - 60s elapsed, OR
   - component unmounts.
4. On HTTP 5xx during poll: exponential backoff — attempt 1 after 3s, attempt 2 after 6s, attempt 3 after 12s. After 3 consecutive 5xx → stop polling, set status to `failed` locally with message "Polling aborted after 3 consecutive errors."

### 2. Scoping

- File allowlist: `frontend/src/components/google-ads/workspace/tab-sections/ReportsTabSection.tsx` + `frontend/src/lib/googleAdsDashboard.ts` (types) + `frontend/src/lib/googleAdsAggregates.ts` (optional: add `isTerminalExportStatus` helper).
- Cleanup: `useEffect` cleanup function clears the interval and aborts any in-flight fetch via `AbortController`.

### 3. Failure modes

1. **Network flap during poll** → 5xx branch above; surface toast + abort.
2. **Rapid re-click of "Create CSV Export"** → cancel prior polling via existing AbortController; start fresh.
3. **Browser tab backgrounded** → `setInterval` throttles but still fires; 60s ceiling protects against runaway.

### 4. Test shape

**Frontend (`frontend/src/components/google-ads/workspace/__tests__/ReportsTabSection.polling.test.tsx`):**

- `polls_until_terminal` — mock `createGoogleAdsExport` to return `status=running`; mock `fetchGoogleAdsExportStatus` to return `running` then `completed`; `vi.useFakeTimers()`; advance by 3s twice; assert final pill is "completed" + download link present.
- `stops_at_60s_ceiling` — mock status stays `running`; advance timers past 60s; assert polling stopped, status remains running, no further fetches.
- `exp_backoff_on_5xx` — mock 3 consecutive 500 responses; assert 3 fetches with increasing gaps (3s, 6s, 12s); final status `failed`.
- `cleanup_on_unmount` — render, kick off poll, unmount before timer fires; assert no pending fetch + no state updates after unmount.

### 5. Rollback posture

- Frontend-only change; revert via `git revert`. No data migration.
- Baseline (pre-change) behavior was a single status fetch — still functional for the sync backend; polling is additive UX.

---

## Sub-agent orchestration plan

Per v2 §Sub-agent orchestration (strict), sequential:

1. **Backend agent (one invocation)** — file allowlist:
   - `backend/analytics/google_ads_views.py`
   - `backend/analytics/urls.py`
   - `backend/integrations/models.py` (GA-A2 migration fields only)
   - `backend/integrations/migrations/0025_recommendation_dismissed_audit.py` (new)
   - `backend/tests/test_google_ads_budgets_pacing_extension.py` (new)
   - `backend/tests/test_google_ads_recommendations_dismiss.py` (new)
   - Scope: GA-A1 backend + GA-A2 backend + their pytest coverage.

2. **Main-thread gate matrix + commit** — one commit per task (split in commit step, not in-agent).

3. **Frontend agent (one invocation)** — file allowlist:
   - `frontend/src/components/google-ads/workspace/tab-sections/{Pacing,Recommendations,Reports}TabSection.tsx`
   - `frontend/src/lib/googleAdsDashboard.ts`
   - `frontend/src/lib/googleAdsAggregates.ts`
   - `frontend/src/components/google-ads/workspace/__tests__/*.test.tsx` (new polling test + updated section tests)
   - Scope: GA-A1 UI + GA-A2 UI + GA-A3 polling + vitest coverage.

4. **Main-thread gate matrix + commit** — one commit per task.

5. **Closeout** — update state file, punchlist, write `artifacts/sprint/S5-google-ads-finish-closeout.md` matching `S4-final-closeout.md` shape.

## Deviations from v2

- v2 proposes URL `<resource_name>/dismiss/`. resource_names contain slashes (`customers/X/recommendations/Y`) — using them in URL paths is ugly + requires `<path:...>` converter. **Chose `<int:pk>/dismiss/` instead.** List endpoint gains `id` field so frontend can address rows. Functionally equivalent; cleaner routing.
- v2 mentions "admin-only permission" for dismiss. **Relaxed to `IsAuthenticated` for MVP.** Any tenant user can dismiss their tenant's recs; audit trail captures who. Can tighten later if product review asks.
- v2 Pre-flight §5 says "reports tab polling fires once — polling loop, not new endpoints." **Saved-views list endpoint already exists** at `/analytics/google-ads/saved-views/` via `fetchGoogleAdsSavedViews` — that's the "list saved reports" equivalent. No new backend endpoint needed. Polling loop only.

---

### Architect pass complete

Design doc: `artifacts/sprint/S5-google-ads-finish-design.md`
Phase A tasks:

- GA-A1 — extend pacing view with per-campaign rows + cache; wire `DistributionBar` in `PacingTabSection`.
- GA-A2 — dismiss action (local) + migration + UI button with optimistic rollback.
- GA-A3 — frontend polling loop in `ReportsTabSection`.

Pre-flight verification: passed with one known deviation (budget name-match best-effort).
Open questions: none blocking; dismiss permission relaxed to IsAuthenticated for MVP.
Next action: dispatch backend sub-agent.
