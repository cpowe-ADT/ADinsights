# ADinsights Project — Remaining Work Punchlist

**As of:** post-commit `7a0e701b` (April 2026), after 4-sprint viz-kit migration + Q1 accumulated workstreams committed.

**Purpose:** concrete list of everything left, ordered by priority. Use this alongside `google-ads-completion-plan.md` for Google Ads specifically.

**Honest state:** Phase 1 is complete. Phase 2 is ~85% shipped. The last 15% splits across Google Ads polish (separate doc), one critical missing feature (alert pause/resume), and a few medium-effort items.

## How to read this file

- **Tiers** are priority, not effort:
  - **Tier 1** = blocks shipping Phase 2 to production
  - **Tier 2** = needed for Phase 2 complete/polished
  - **Tier 3** = post-launch / nice-to-have / expansion
- **Effort** S = ≤1d, M = 1–3d, L = 3–5d, XL = 1–2 weeks
- **Deps** = prerequisite tasks
- Update task status in-place as you work (CHECK, IN-PROGRESS, BLOCKED, DONE)

## Quick status overview

| Area | % complete | Tier-1 blockers |
|---|---|---|
| Meta integration | ~95% | none |
| Google Ads | ~95% | Phase A+B+C1/C2 done (2026-04-23); C3 staging regression blocked on test-account creds |
| GA4 | ~95% | T1-04 Verdict B done (2026-04-23); live-data DoD bullet blocked on Airbyte creds (4 env vars + dbt flag) |
| Search Console | ~50% | no dedicated OAuth/sync module (uses mart) |
| LinkedIn | ~5% | scaffolded only |
| TikTok | ~5% | scaffolded only |
| Alerts CRUD | ~75% | pause/resume, edit, delete |
| Notification channels | ~90% | SMS optional |
| Reports | ~80% | PDF/PNG render |
| Core infra (dbt, Celery, migrations, runbooks) | ~95% | none |

---

## TIER 1 — Ship Phase 2 blockers (~2 weeks, 1 FTE)

These block calling Phase 2 production-ready.

### T1-01 — Alert pause/resume — **DONE (2026-04-23)**

**Recontextualization:** audit found on/off pause was already shipped via `is_active` (`AlertDetailPage.tsx:178-182` + `AlertsPage.tsx:127`). Real gap was **time-bounded pause** (`paused_until`) + auto-resume. Also found no DB-driven evaluator consumes `AlertRuleDefinition` today — `AlertService.run_cycle` iterates hardcoded `ALERT_RULES` in `backend/app/alerts.py`. Evaluator rewrite is tracked as T2-07 follow-on.

**What shipped:**
- [x] Migration `0024_alert_paused_until.py` — adds `paused_until: DateTimeField(null=True, blank=True)`
- [x] `AlertRuleDefinition.active_for_eval()` classmethod — lazy auto-resume sweep (bulk-updates expired pauses) + returns `is_active=True` queryset. Canonical "should-this-rule-evaluate-now" filter for any future DB-driven evaluator.
- [x] `AlertRuleDefinitionSerializer` exposes `paused_until` (read-only); mutations go through dedicated actions
- [x] `POST /api/alerts/<id>/pause/` — body `{pause_until?: ISO8601} | {duration_hours?: 1..720} | {}`; rejects both provided, naive datetimes, past times, bool-as-int, out-of-range durations. Audit event `alert_rule_paused`.
- [x] `POST /api/alerts/<id>/resume/` — clears `paused_until`, sets `is_active=True`. Audit event `alert_rule_resumed`.
- [x] Frontend: pause-duration dropdown on `AlertDetailPage.tsx` (1h/4h/24h/7d/Indefinite) wired to `pauseAlert` helper; `resumeAlert` replaces old `updateAlert({is_active})` path; "Auto-resumes at…" line renders when `paused_until` is set.
- [x] Tests: 16 pytest cases covering pause/resume validation, tenant isolation, audit logs, `active_for_eval` expiry sweep; 8 vitest cases covering dropdown + resume + toast behavior.

**Follow-on (tracked separately):** T2-07 — rewrite `AlertService.run_cycle` to consume `AlertRuleDefinition.active_for_eval()` instead of hardcoded `ALERT_RULES`. Model plumbing (this ticket) is the prerequisite; end-to-end "pause stops evaluations" is realized when T2-05 lands.

**DoD:** satisfied — user can pause indefinitely or for N hours, auto-resume fires on `paused_until` expiry, pause/resume are audited + tenant-isolated.

---

### T1-02 — Alert edit + delete endpoints — **DONE (2026-04-23)**

**Recontextualization:** audit confirmed DELETE + PATCH already work end-to-end via `ModelViewSet` + existing `deleteAlert` helper (`phase2Api.ts`) + existing Delete button (`AlertDetailPage.tsx:149`). Missing pieces were: (1) frontend edit form (rule details were display-only), (2) serializer-level validators for blank name/metric, (3) end-to-end PATCH test coverage. Also caught a **latent bug**: `AlertCreatePage` was submitting severity `info/warning/critical` while the backend enum is `low/medium/high` — every create via UI was failing validation. Fixed as part of this work (precondition for the edit form reusing the same enum).

**What shipped:**
- [x] Inline edit form on `AlertDetailPage.tsx` with controlled inputs for name/metric/comparison_operator/threshold/lookback_hours/severity. Save → `updateAlert`, Cancel restores, error keeps form open.
- [x] Serializer validators: `validate_name` + `validate_metric` reject blank/whitespace.
- [x] `AlertCreatePage.tsx` severity values aligned to backend enum (`low`/`medium`/`high`).
- [x] Hard-delete (codebase convention — no `deleted_at` pattern exists in `integrations/models.py`).
- [x] Tests: 5 pytest cases covering PATCH success+audit, blank-name/metric rejection, `paused_until` read-only enforcement, DELETE tenant isolation; 4 vitest cases covering edit-form open/submit/cancel/error.

**DoD:** satisfied — user can edit all rule fields, delete their own rules, both audited, validation rejects obviously-bad inputs.

---

### T1-03 — Google Ads Phase A (3 incomplete tabs) — **DONE (2026-04-23)**

**See:** `artifacts/roadmap/google-ads-completion-plan.md` Phase A, `artifacts/sprint/S5-google-ads-finish-design.md`, `artifacts/sprint/S5-google-ads-finish-closeout.md`.

**Recontextualization:** v2 prompt pre-flight (state file `S5-google-ads-state.json`) found that all three Phase A endpoints already existed in tree at baseline `c0d132a5` (pacing view at `google_ads_views.py:1308`, recommendations view at `:1413`, export status/download views at `:1673`/`:1690`). Scope was therefore **extensions, actions, and polling** — not new endpoints. Also found one deviation from v2's implicit assumption: `CampaignBudget` has no `campaign_id` FK (keyed `(tenant, name)` — unique_together). Per-campaign budget match is best-effort case-insensitive by name; unmatched campaigns surface `budget_amount=null` and the UI renders `"—"` in pace/variance cells.

**What shipped:**
- [x] **GA-A1** — `GoogleAdsBudgetPacingView` extended with `campaigns[]` per-campaign rows (`campaign_id`, `campaign_name`, `customer_id`, `budget_amount`, `spend_mtd`, `pace_pct`, `projected_eom`, `variance`) + 15-min tenant-scoped cache keyed `ga_pacing_v1:<tenant>:<sha1(customer_ids)>:<end_date>`; response gains `cache: {served_from_cache, ttl_seconds}`. Frontend: "Over-pacing campaigns" KPI + DistributionBar panel + companion table on `PacingTabSection.tsx`.
- [x] **GA-A2** — New `POST /analytics/google-ads/recommendations/<int:pk>/dismiss/` — idempotent, tenant-scoped 404, **LOCAL ONLY** (no SDK `DismissRecommendation` call — regression-guarded by subprocess grep of production `.py` excluding vendored SDK). Migration `0025_recommendation_dismissed_audit` adds `dismissed_at` + `dismissed_by`. AuditLog event `google_ads_recommendation_dismissed`. Frontend: Dismiss `<button>` replacing Status chip on `RecommendationsTabSection.tsx` with optimistic update + rollback + toast.
- [x] **GA-A3** — `ReportsTabSection.tsx` polling loop via `setTimeout` chain + `useRef` for cancellation; 3s steady / 60s ceiling / exp-backoff (3s→6s→12s) on 5xx; AbortController + mounted-ref cleanup on unmount; short-circuits when initial response is already terminal (uses `deriveExportJobStatusTone` for the status pill).
- [x] Tests: 11 new pytest cases (5 pacing extension, 6 dismiss including SDK-regression guard) + 16 new vitest cases across 3 new FE test files (5 pacing, 6 dismiss, 5 polling). T1-03 owned vitest passes 16/16 deterministically in isolation.

**Gates:** ruff clean, backend pytest clean, frontend lint clean, `npm run build ✓ built`. Full-suite vitest exhibited the same environment-thrash pattern documented in S4 closeout §4 — 98 timeout `STACK_TRACE_ERROR` noise on unrelated viz primitives when run under concurrent CPU contention; T1-03 owned files pass deterministically in isolation (see S5 closeout §5).

**Commits on `main`:**
- `15e33459` — backend: migration + models + pacing/dismiss view changes + backend tests
- `01780559` — FE: GA-A1 per-campaign pacing UI + aggregates types + FE test
- `07bd1327` — FE: GA-A2 dismiss UI + dashboard helper + FE test
- `7b7920e3` — FE: GA-A3 polling loop + FE test

**DoD:** satisfied — pacing endpoint returns per-campaign rows cached 15 min tenant-scoped; recommendation dismiss is wired end-to-end LOCAL ONLY with optimistic UI and audit trail; report export polls 3s→60s with exp-backoff on 5xx and stops on terminal status or unmount.

**Follow-on (tracked separately):** Phase B (GA-B1 change-log pagination, GA-B2 saved-view reconciliation) and Phase C (integration tests, runbook, staging smoke) remain deferred per state file. A future cleanup could replace the best-effort name-match budget join with a proper `CampaignBudget.campaign_id` FK migration.

---

### T1-04 — Verify GA4 ingestion path — **DONE-WITH-BLOCKER (2026-04-23)**

**See:** `artifacts/roadmap/ga4-investigation.md` (Verdict B), `artifacts/sprint/S5-ga4-finish-closeout.md`, `artifacts/sprint/S5-ga4-staging-smoke-checklist.md`.

**Status:** **Verdict B — wired but untested live in this environment.** Full engineering-side DoD satisfied; the one remaining bullet ("dashboard shows real data") is credential-gated.

**What shipped (2026-04-23):**
- [x] Investigation doc with Verdict B + file-level evidence (214 LoC, pasted psql + curl + grep output proving mart absent by design with `enable_ga4=false`)
- [x] 16 new backend pytests: 12 PII allowlist tests for both GA4 dbt models, 3 credential-classification tests for `GoogleAnalyticsClient._build_client`, 1 tenant-isolation test (`test_ga4_web_insights_isolates_rows_by_tenant` — seeds two tenants' rows into transient `agg_ga4_daily`, asserts only tenant A rows returned)
- [x] 4 dashboard vitest (existing) covering populated render, R3 contract (no `/metrics/combined/` call), `no_ga4_property_selected` empty state, `no_data_for_range` empty state
- [x] Runbook `docs/runbooks/ga4-operations.md` (155 LoC: architecture, connect-a-property, make-dashboard-live operator path, verify-live one-liner, troubleshooting, OAuth token refresh, rate limits, scopes, test commands)
- [x] Finish closeout `S5-ga4-finish-closeout.md` — DoD audit + gate matrix + known architectural quirks + blocker detail
- [x] Operator-runnable smoke checklist `S5-ga4-staging-smoke-checklist.md` — 6 phases (Airbyte+dbt provision, OAuth connect, dashboard E2E, R3+tenant isolation, freshness scheduling, record results) with triage cheat sheet

**Blocker:**
- [ ] Dashboard shows real data in dev stack — **BLOCKED on external credentials.** Needs `AIRBYTE_GA4_CLIENT_ID`, `AIRBYTE_GA4_CLIENT_SECRET`, `AIRBYTE_GA4_REFRESH_TOKEN`, `AIRBYTE_GA4_PROPERTY_ID` provisioned in staging + dbt `enable_ga4=true` flip + `dbt build --select +agg_ga4_daily` run. Estimated 60-90 min of operator work once creds are surfaced. Execution walkthrough: `S5-ga4-staging-smoke-checklist.md`.

**Known architectural quirk:** in-app OAuth flow writes `GoogleAnalyticsConnection` rows but does NOT feed Airbyte — Airbyte uses its own refresh-token env var. A tenant completing OAuth in the UI still sees empty dashboard until operator separately provisions Airbyte. Out-of-scope for T1-04; tracked as future feature.

**DoD:** clear answer — GA4 is **Verdict B (ship-ready pending creds)**. Dashboard serves EmptyState-by-design until operator provisions Airbyte per the smoke checklist.

---

### T1-05 — Search Console: decide ingestion strategy (S–M, 1–3d) — **DONE-WITH-DEFERRAL (2026-04-23)**

**Decision (Option B — explicit defer with user-visible notice):** The backend dashboard path is fully wired (view + dbt staging + mart + Airbyte template all exist). The **tenant-facing OAuth on-ramp is deferred** to a post-launch follow-on; there is no `backend/integrations/search_console/` module today, and no self-serve connect flow in Data Sources. The dashboard surfaces a persistent "data refresh coming soon" notice and a new `search_console_ingestion_deferred` empty-state reason code so the deferred state is visible regardless of mart presence.

**What shipped (2026-04-23):**
- [x] Confirmed ingestion path: Airbyte Search Console source (`infrastructure/airbyte/search_console_source.yaml`, operator creds) → `raw.search_console_performance` → dbt `stg_search_console` → `agg_search_console_daily` (gated by `enable_search_console=false`) → `SearchConsoleInsightsView`
- [x] Deferred-ingestion notice on `SearchConsoleDashboardPage.tsx` (persistent panel with `data-reason="search_console_ingestion_deferred"`). R3 contract preserved — page still only hits `/api/analytics/web/search-console/`
- [x] Updated `isUnavailable` empty state to reason `search_console_ingestion_deferred` with copy matching the deferral
- [x] Operations runbook `docs/runbooks/search-console-operations.md` documenting current state, operator path to go live, and the outstanding tenant-OAuth work
- [x] Frontend test coverage updated in `SearchConsoleDashboardPage.test.tsx` — asserts notice visibility + new reasonCode

**Follow-on work (NOT part of T1-05):**
- [ ] Build `backend/integrations/search_console/` mirroring `backend/integrations/google_analytics/` (OAuth client + start/exchange/provision/status views)
- [ ] Add Data Sources card + provisioning flow
- [ ] Decide on Airbyte operator bridge vs. per-tenant OAuth tokens for ingestion
- [ ] Remove the deferred notice once the tenant-facing flow lands

**DoD:** clear answer: Search Console is **explicitly deferred with a user-visible notice**. Dashboard + mart + Airbyte template remain available for operator-wired single-tenant deployments.

---

## TIER 2 — Phase 2 polish (~2–3 weeks after T1)

These make Phase 2 feel done, not just work.

### T2-01 — Report PDF/PNG generation (L, 3–4d)

**Status:** `ReportExportJob` model supports format choices (CSV working, PDF/PNG defined but no render task).

**Work:**
- [ ] Pick a rendering approach: Playwright screenshot (works for PNG, PDF via browser print) OR headless chrome via puppeteer OR wkhtmltopdf (older but simpler)
- [ ] Implement the Celery task that renders a report by ID to the chosen format
- [ ] Wire into existing `ReportExportJob` dispatcher
- [ ] Tests: backend pytest for render task with sample payload; check output file is non-empty valid PDF/PNG

**Recommend:** Playwright — already in `qa/` so dep already in house.

---

### T2-02 — Google Ads Phase B + C

**See:** `google-ads-completion-plan.md`, `artifacts/sprint/S5-google-ads-phase-b-closeout.md`, `artifacts/sprint/S5-google-ads-phase-c-closeout.md`.

**Phase B — DONE (2026-04-23):**
- [x] GA-B1 Change log pagination — `next_cursor` alias on existing paginated endpoint + Load more UI with accumulated rows (commits `cda49031` backend, `f066e527` FE). 3 pytest + 3 vitest.
- [x] GA-B2 Saved-view reconciliation — new `verify` action comparing `filters`/`columns` against static v23 whitelist + FE dismissible drift banner (commits `cda49031` backend, `4e1733ec` FE). 4 pytest + 3 vitest.

**Phase C — PARTIAL (2026-04-23):**
- [x] GA-C1 Integration test suite — 10 new `*.integration.test.tsx` files, one per tab section (Assets, Campaigns, Changes, Conversions, Overview, Pacing, Pmax, Recommendations, Reports, Search), each covering loading/empty/populated branches. 30 new tests, 57/57 workspace vitest pass (commit `81df0c18`).
- [x] GA-C2 Documentation — new `docs/runbooks/google-ads-operations.md` (10 `##` sections: scope, SDK-vs-Airbyte hybrid, endpoint register, day-2 ops, known quirks, related docs) + CLAUDE.md current-state updated to reflect shipped Phase B (commit `37ff1b77`).
- [ ] GA-C3 Staging regression — **BLOCKED on test-account credentials** (M, 2–3d). Per v2 protocol (`finish-google-ads.v2.md §Phase C`), requires user to surface staging Google Ads OAuth creds + a test tenant with linked customer_ids. Escalation open 2026-04-23. **Deliverable prepared:** `artifacts/sprint/S5-google-ads-phase-c-staging-smoke-checklist.md` (full operator-runnable regression checklist: pre-flight creds table, per-tab smoke for all 10 tabs, cross-cutting auth + isolation checks, record-results procedure, failure triage cheat sheet). Execute top-to-bottom when creds land.

---

### T2-03 — Notification channels: end-to-end delivery verification (S, 1d)

**Status:** DONE (2026-05-01). Model + ViewSet + M2M to `AlertRuleDefinition` were already present; delivery now fires for tenant-defined alert rules with active channel assignments when evaluation returns rows.

**Work:**
- [x] Grep for where alert evaluation dispatches notifications
- [x] Test email delivery on a fired alert
- [x] Test Slack delivery (webhook URL in `NotificationChannel.config`)
- [x] Test webhook delivery
- [x] Document each channel's `config` shape in `docs/runbooks/alerting.md`

**DoD:** a fired alert produces expected side-effects on all 3 channel types.

---

### T2-04 — Audit trail for alert changes (M, 2d)

**Status:** No audit log table linked to `AlertRuleDefinition`.

**Work:**
- [ ] Add `AlertRuleAudit` model (who, when, what changed) OR use `django-simple-history` if already installed
- [ ] Hook on `AlertRuleDefinition` save/delete
- [ ] Optional: serialize changes (old→new) for rich audit

Skip if out of scope for current compliance needs.

---

### T2-05 — Tenant quota enforcement (S, 1d)

**Status:** No "max alerts per tenant" check at `AlertRuleDefinition.save()`.

**Work:**
- [ ] Add a `MAX_ALERT_RULES_PER_TENANT` setting (e.g. 50)
- [ ] Validator in serializer or model.clean(): raise if creating Nth rule would exceed
- [ ] Same check for reports, notification channels if we want quotas broadly

Skip if current tenants are trusted + low count.

---

### T2-06 — AI summary refresh cadence + cache invalidation (S, 1d)

**Status:** `AISummary` model exists, UI shows badges, but no refresh-interval config or cache-invalidation logic.

**Work:**
- [ ] Decide cadence (per-tenant config? fixed daily?)
- [ ] Add scheduled Celery task to regenerate stale summaries
- [ ] Cache-invalidate when underlying data window changes

---

### T2-07 — Wire `AlertService` to DB-defined `AlertRuleDefinition` (M, 2–3d)

**Status:** DONE (2026-05-01). Prerequisite shipped with T1-01 (`AlertRuleDefinition.active_for_eval()` classmethod).

**Context:** `AlertService.run_cycle` now preserves hardcoded `ALERT_RULES` as system presets and also evaluates DB-backed `AlertRuleDefinition.active_for_eval()` rows via generated `tenant_alert:<uuid>` SQL rules. Each DB-backed rule carries tenant-scoped parameters and runs inside `tenant_context(rule.tenant_id)`. Alert history metadata resolves `tenant_alert:<uuid>` slugs for user-defined rule names, descriptions, and severity.

**Work:**
- [x] Complement `ALERT_RULES` iteration with `AlertRuleDefinition.active_for_eval()` in `AlertService.run_cycle`
- [x] Map `AlertRuleDefinition` fields (metric, comparison_operator, threshold, lookback_hours) to a generic tenant-scoped SQL threshold rule
- [x] Keep hardcoded `ALERT_RULES` as system presets rather than migrating them to seeded DB rows in this pass
- [x] Tests: paused rule is skipped end-to-end; auto-resumed rule re-enters evaluation; tenant isolation during evaluation

**DoD:** toggling pause on an alert rule in the UI stops its SQL evaluation in the next `run_cycle`; auto-resume (via `paused_until` expiry) re-enters it.

---

## TIER 3 — Post-launch / expansion (4–8 weeks if all done)

### T3-01 — LinkedIn adapter (XL, 2 weeks)

**Status:** `ProviderType.LINKEDIN` enum exists in `backend/integrations/models.py` but no sync code.

**Work:**
- [ ] OAuth flow (LinkedIn Marketing API)
- [ ] Airbyte connector OR direct sync
- [ ] dbt models for staging → mart
- [ ] Add to warehouse adapter dispatch
- [ ] Frontend dashboard page (likely mirror Google Ads workspace pattern)
- [ ] Runbook + tenant onboarding doc

### T3-02 — TikTok adapter (XL, 2 weeks)

Same pattern as LinkedIn.

### T3-03 — SMS notification channel (S, 1d)

**Status:** `NotificationChannel.CHANNEL_TYPE_CHOICES` has email/webhook/slack only. Add SMS if needed.

**Work:**
- [ ] Add `CHANNEL_SMS = 'sms'` + pick provider (Twilio/AWS SNS)
- [ ] Implement dispatch
- [ ] Config shape in `NotificationChannel.config` (provider, phone number, api creds via env)

### T3-04 — Bulk re-sync + dry-run preview (M, 2d)

**Status:** Per-connection re-sync exists (`SyncHealthPage`). Bulk re-sync and dry-run preview not wired.

### T3-05 — Legacy component migration (M, 2–3d)

**Status:** `CampaignTable`, `CreativeTable`, `BudgetPacingList`, legacy `Skeleton` still retained as drilldown companions to viz kit. Architect deferred in Sprint 4.

**Work:** replace each with `VizDataTable` + `ChartSkeleton` equivalents. Nothing is broken; this is cleanup.

### T3-06 — Parish bubble overlay + tooltip sparkline (M, 2–3d + backend)

**Status:** `ParishMapDetail.tsx:227` + `:233` have `[NEW-ENDPOINT]` markers.

**Work:**
- Backend: add lat/lng to `ParishAggregate` payload + per-parish daily series endpoint
- Frontend: wire bubble overlay on Leaflet + sparkline in tooltip

Blocked on backend endpoint.

### T3-07 — Vitest ≥ 80% coverage gate (S, 1d)

**Status:** Deferred per S1 architect §10.10 because Recharts SVG inflates coverage noise. Add filter to exclude viz kit rendering-only paths, then turn on the gate.

---

## Suggested execution order

If you have **1 FTE for ~3 weeks** and want to ship Phase 2 to production:

**Week 1 — Alert pause + Google Ads A1 + GA4 verification**
- Day 1–2: T1-01 (alert pause/resume end-to-end)
- Day 2: T1-02 (alert edit/delete verification)
- Day 3–4: T1-04 (GA4 ingestion verification) + T1-05 (Search Console decision)
- Day 4–5: Start GA-A1 (budget variance endpoint)

**Week 2 — Finish Google Ads Phase A**
- Day 1–3: Finish GA-A1
- Day 3–5: GA-A2 (dismiss) + GA-A3 (report list + polling)

**Week 3 — Phase 2 polish + release prep**
- Day 1–2: T2-03 (notification channel delivery test)
- Day 3–5: GA-C1 (Google Ads integration tests) + ship prep

At end of Week 3: **Phase 2 ship-ready.** Everything else (T2 remaining + T3) is post-launch iteration.

If you have **1 FTE for 6–8 weeks**, add all of T2 (including PDF/PNG exports, audit trail, GA Phase B+C) before calling it GA.

If LinkedIn/TikTok matter for GA: add 3–4 weeks each.

## Commit rhythm

After each task in this list:
1. Tests pass isolated (`npx vitest --run <file>` + `pytest <file>`)
2. Full matrix green (`npm test -- --run`, `pytest`, `ruff check`, `npm run lint`, `npm run build`)
3. Commit with conventional-commits prefix: `feat(alerts):`, `fix(google-ads):`, `docs(runbooks):`
4. Check off the task in this file in the same commit

Keep this file updated as the source of truth for what's left.
