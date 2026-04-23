# Sprint 5 Phase B — Architect Design (GA-B1 + GA-B2)

**Inputs:** v2 prompt §Phase B (`finish-google-ads.v2.md:54-56,124-130`), Phase A closeout (`S5-google-ads-finish-closeout.md`), state file (`S5-google-ads-state.json`), pre-flight Explore agent report (in-conversation).

**Baseline commit:** `3edac555` (Phase A closeout addendum).

**Format:** abbreviated 5-part per task. Phase B is intentionally small (1–2d each per v2); architect doc is correspondingly leaner than Phase A's.

---

## GA-B1 — Change log pagination

### 1. Request / response

The endpoint **already paginates** via `?page=N&page_size=K` (Django `Paginator`). The v2 Phase B gate requires `next_cursor` in the response. Approach: add a string `next_cursor` field that encodes `str(page+1)` when more pages exist, `null` otherwise. Page-based pagination stays under the hood — no behavior change for existing consumers; new field is purely additive.

**Existing response** (`backend/analytics/google_ads_views.py:1473-1480`):
```json
{ "count": <int>, "page": <int>, "page_size": <int>, "num_pages": <int>, "results": [...] }
```

**New response** — add one key:
```json
{ "count": ..., "page": ..., "page_size": ..., "num_pages": ..., "next_cursor": "<str|null>", "results": [...] }
```

`next_cursor = str(page_obj.number + 1) if page_obj.has_next() else None`.

### 2. Scoping

- **Backend:** 1-line change in `GoogleAdsChangeEventsView` (`google_ads_views.py:1431`) to compute + emit `next_cursor`.
- **Frontend:** `ChangesTabSection.tsx` adds a "Load more" button beneath the table; component owns local accumulated `mergedRows` state. Parent (`GoogleAdsWorkspacePage`) passes initial data + a `loadMore?: (cursor: string) => Promise<Payload>` callback. Disabled and hidden when `next_cursor === null`.
- **Client helper:** Extend `frontend/src/lib/googleAdsDashboard.ts` with `fetchGoogleAdsChangeEventsPage(cursor: string)` that calls `/analytics/google-ads/change-events/?page=<cursor>&page_size=…` and returns the typed Payload.
- **Tenant isolation:** unchanged — view already filters by `request.user.tenant_id` on `GoogleAdsSdkChangeEvent.objects` (TenantAwareManager).

### 3. Failure modes

- `cursor` parsed from query: integer-coerced via existing `GoogleAdsListQuerySerializer.page` validator. Invalid → 400 from existing serializer.
- Page beyond `num_pages`: Django `Paginator.get_page()` clamps to last page silently — `has_next()` returns False → `next_cursor: null` → button disappears. No 404.
- Concurrent inserts during paging (a new change event lands between pages): page-based pagination's known weakness. Acceptable for this dataset (changes log is mostly historical; new events accumulate at the top).

### 4. Test shape

- **Backend** (`tests/test_google_ads_changes_pagination.py`, NEW, 3 tests):
  - `test_changes_returns_next_cursor_when_more_pages` — seed N+1 rows, assert page 1 has `next_cursor="2"`.
  - `test_changes_next_cursor_null_on_last_page` — seed N rows, assert page 1 with `page_size>=N` has `next_cursor=null`.
  - `test_changes_pagination_tenant_isolated` — two tenants with overlapping rows, assert each only sees own.
- **Frontend** (`ChangesTabSection.pagination.test.tsx`, NEW, 3 tests):
  - "renders Load more button when next_cursor is present"
  - "appends results from second page after Load more click"
  - "hides Load more button when next_cursor becomes null"

### 5. Rollback posture

- Backend: revert single-line addition. No migration. No model change.
- Frontend: revert ChangesTabSection.tsx + its new test + the helper export. No types broken (added `next_cursor?: string | null` is optional).

---

## GA-B2 — Saved-view reconciliation check

### 1. Request / response

New endpoint: `GET /api/analytics/google-ads/saved-views/<uuid:pk>/verify/` (mounted as `@action(detail=True, methods=["get"])` on the existing `GoogleAdsSavedViewViewSet` at `google_ads_views.py:1616`).

**Response:**
```json
{
  "id": "<uuid>",
  "name": "<str>",
  "drift": <bool>,
  "unknown_filter_keys": ["<str>", ...],
  "unknown_columns": ["<str>", ...],
  "checked_against_version": "google-ads-v23"
}
```

`drift = bool(unknown_filter_keys or unknown_columns)`.

### 2. Scoping

- **Backend:** new `verify` action in the viewset. Compares `instance.filters.keys()` against a static `KNOWN_FILTER_KEYS` whitelist + `instance.columns` against `KNOWN_COLUMN_KEYS` whitelist. Whitelists derived from existing `GoogleAdsListQuerySerializer` field set (filters) and the union of column keys returned by the campaigns/keywords/changes endpoints (columns). Static whitelists are appropriate because our SDK is pinned to v23 — drift would surface only if a saved view persisted a key not in the current backend's vocabulary.
- **Frontend:** new banner in `ReportsTabSection.tsx`. On mount, after `initialSavedViews` loads, fetches verify for each view in parallel (`Promise.all`); aggregates drift count. Renders dismissible amber `<aside role="status">` banner above the table when `driftCount > 0`. Click on row could surface drift detail in future, but Phase B scope is the count + name list only.
- **Client helper:** `verifyGoogleAdsSavedView(id: string)` in `googleAdsDashboard.ts`.
- **Tenant isolation:** the viewset's `get_queryset()` already filters by tenant; the `verify` action inherits the queryset via `get_object()` which calls `get_queryset().get(pk=…)` → cross-tenant PK gives 404.

### 3. Failure modes

- Saved view with empty `filters={}` and empty `columns=[]` → `drift=false`. (No keys to be unknown.)
- Network failure on individual verify call from FE: Promise.allSettled-style — failed verifies silently drop from drift count; banner only counts confirmed drift. (Erring on the side of fewer false alarms.)
- Whitelist evolution: when we ship a new column key in the future, **the whitelist must be updated too**, otherwise stale saved views look "fine" while new ones look "drifted." This is a known maintenance cost; documented in the Phase B closeout.

### 4. Test shape

- **Backend** (`tests/test_google_ads_saved_view_verify.py`, NEW, 4 tests):
  - `test_verify_returns_no_drift_for_canonical_view` — view with all-known keys → `drift=false`.
  - `test_verify_flags_unknown_filter_key` — view with `filters={"banana": 1}` → `drift=true`, `unknown_filter_keys=["banana"]`.
  - `test_verify_flags_unknown_column` — view with `columns=["bogus_col"]` → `drift=true`.
  - `test_verify_tenant_isolation` — cross-tenant pk → 404.
- **Frontend** (`ReportsTabSection.driftBanner.test.tsx`, NEW, 3 tests):
  - "no banner when all saved views verify clean"
  - "renders banner with drift count when 1+ views drift"
  - "banner dismissible (sets local state, hides)"

### 5. Rollback posture

- Backend: revert viewset action + remove whitelists. No migration. No model change.
- Frontend: revert ReportsTabSection.tsx + helper + test. Banner is purely additive.

---

## Phase B file allowlist (sub-agent guardrails)

**Backend agent allowlist:**
- `backend/analytics/google_ads_views.py` — extend `GoogleAdsChangeEventsView` (1 line) + add `verify` action on `GoogleAdsSavedViewViewSet`
- `backend/tests/test_google_ads_changes_pagination.py` — NEW
- `backend/tests/test_google_ads_saved_view_verify.py` — NEW

**Frontend agent allowlist:**
- `frontend/src/lib/googleAdsDashboard.ts` — add 2 helpers
- `frontend/src/components/google-ads/workspace/tab-sections/ChangesTabSection.tsx` — add Load more button + accumulated state
- `frontend/src/components/google-ads/workspace/tab-sections/ReportsTabSection.tsx` — add drift banner
- `frontend/src/routes/google-ads/GoogleAdsWorkspacePage.tsx` — wire `loadMore` callback into `<ChangesTabSection>`
- `frontend/src/components/google-ads/workspace/__tests__/ChangesTabSection.pagination.test.tsx` — NEW
- `frontend/src/components/google-ads/workspace/__tests__/ReportsTabSection.driftBanner.test.tsx` — NEW

**Out of scope (do not touch):**
- Model changes / migrations (Phase B is non-schema)
- Other tab sections
- Phase A files (already shipped)

---

## Phase B gate (per v2 §Phase B gate)

| Check | Expected |
|---|---|
| `curl .../change-events/?page=1 \| jq '.next_cursor'` | non-null when more pages exist |
| `curl .../saved-views/<id>/verify/ \| jq '.drift'` | boolean response |
| Backend ruff | clean |
| Backend pytest | clean (no regression from `3edac555`) |
| Frontend lint | clean |
| Frontend build | clean |
| New backend tests pass | 7/7 (3 pagination + 4 verify) |
| New frontend tests pass | 6/6 (3 pagination + 3 drift banner) |
| Tenant isolation tests | both new test files cover isolation |
