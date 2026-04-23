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
| Google Ads | ~72% | see `google-ads-completion-plan.md` Phase A |
| GA4 | ~80% | verify sync path populates `agg_ga4_daily` |
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

### T1-01 — Alert pause/resume — CONFIRMED MISSING (M, 1–2d)

**Status:** NOT STARTED.

**Evidence:** `backend/integrations/models.py:1495-1545` — `AlertRuleDefinition` has `is_active` (on/off) but no `is_paused` / `paused_until` field.

**Work:**
- [ ] Add `is_paused: BooleanField(default=False)` + `paused_until: DateTimeField(null=True, blank=True)` to `AlertRuleDefinition`. Migration in `backend/integrations/migrations/0024_alert_pause.py`.
- [ ] Update `AlertRuleDefinitionSerializer` (`backend/integrations/serializers.py:374`) to expose the new fields
- [ ] Add action endpoints `POST /api/alert-rules/<id>/pause/` and `POST /api/alert-rules/<id>/resume/` to `AlertRuleDefinitionViewSet` (`backend/integrations/views.py:3661`). `pause` accepts optional `pause_until` body param.
- [ ] Evaluator should skip paused rules: wherever alert evaluation runs (grep `AlertRuleDefinition.*filter.*is_active`), add `is_paused=False` and `(paused_until__isnull=True | paused_until__lt=now())` filter.
- [ ] Frontend: add pause/resume toggle to `AlertRuleDefinition` list/detail UI. Grep for `AlertRulesPage` / `AlertSettings`.
- [ ] Tests: backend pytest for paused-rule evaluation skip; vitest for UI toggle.

**DoD:** toggling pause on an alert rule stops evaluations; resume or `pause_until` expiry re-enables.

---

### T1-02 — Alert edit + delete endpoints (S, 1d)

**Status:** Likely PARTIAL. `AlertRunViewSet` at `backend/alerts/views.py:10` is read-only (`ListModelMixin + RetrieveModelMixin`). `AlertRuleDefinitionViewSet` at `backend/integrations/views.py:3661` is a `ModelViewSet` so should have full CRUD — verify and add frontend plumbing if missing.

**Work:**
- [ ] Verify PATCH and DELETE on `/api/alert-rules/<id>/` work end-to-end (may already; check tests)
- [ ] If frontend has no edit/delete UI for alert rules, add it
- [ ] Consider soft-delete (`deleted_at` timestamp) if audit trail matters

**DoD:** user can edit and delete their own alert rules from the UI.

---

### T1-03 — Google Ads Phase A (3 incomplete tabs)

**See:** `artifacts/roadmap/google-ads-completion-plan.md` Phase A.

- [ ] GA-A1 Per-campaign budget variance endpoint (L, 3–5d)
- [ ] GA-A2 Recommendations dismiss wired (M, 2–3d)
- [ ] GA-A3 Report list + export polling (M, 2–3d)

---

### T1-04 — Verify GA4 ingestion path (S, 1d)

**Status:** API view exists (`backend/analytics/web_views.py:126` `GA4WebInsightsView`) reading from `agg_ga4_daily` mart. The integration module at `backend/integrations/google_analytics/` has `client.py` + `views.py` + `urls.py`. Need to confirm the sync path that populates `agg_ga4_daily` actually runs.

**Work:**
- [ ] Read `backend/integrations/google_analytics/client.py` and `views.py` — is there a working sync task?
- [ ] Check `dbt/models/` for `agg_ga4_daily` — are its upstream source tables getting data?
- [ ] Check Airbyte config at `infrastructure/airbyte/` for any GA4 connector
- [ ] Smoke-test: in dev stack, trigger a GA4 sync (if controllable) and verify data lands in mart, then visible in `GoogleAnalyticsDashboardPage`
- [ ] If sync isn't wired: decide whether to wire it now (medium) or defer to post-launch

**DoD:** either we know GA4 is shipping live data, or we have a clear go/no-go on what's needed.

---

### T1-05 — Search Console: decide ingestion strategy (S–M, 1–3d)

**Status:** Asymmetric to GA4 — `SearchConsoleInsightsView` exists (`backend/analytics/web_views.py:130`) reading from `agg_search_console_daily` mart, but no dedicated `integrations/search_console/` module. Unlike GA4, it has no OAuth client or sync code.

**Work:**
- [ ] Confirm how `agg_search_console_daily` gets populated. If via Airbyte, document; if via a future sync, decide now
- [ ] If keeping Search Console dashboard-only with no live ingestion: flip the UI to show "data refresh coming soon" and document as post-launch
- [ ] If building real ingestion: mirror the GA4 pattern — `backend/integrations/search_console/` with client.py + views.py + urls.py. Effort ~M.

**DoD:** clear answer: Search Console is either fully wired end-to-end OR explicitly deferred with a user-visible notice.

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

**See:** `google-ads-completion-plan.md`.
- [ ] Phase B polish (change log pagination, saved-view reconciliation) — 3–4d
- [ ] Phase C hardening (integration tests, docs, staging regression) — 5–7d

---

### T2-03 — Notification channels: end-to-end delivery verification (S, 1d)

**Status:** Model + ViewSet + M2M to AlertRuleDefinition all present (`backend/integrations/models.py:1548`). Need to confirm delivery actually fires.

**Work:**
- [ ] Grep for where alert evaluation dispatches notifications
- [ ] Test email delivery on a fired alert
- [ ] Test Slack delivery (webhook URL in `NotificationChannel.config`)
- [ ] Test webhook delivery
- [ ] Document each channel's `config` shape in `docs/runbooks/`

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
