# Current Priority Todo

Purpose: keep the next ADinsights work items in one place, with a clear split between release blockers that require operator access and repo-ready tasks that Codex can execute immediately.

See also:

- `AGENTS.md`
- `docs/workstreams.md`
- `docs/project/phase1-execution-backlog.md`
- `docs/task_breakdown.md`
- `docs/runbooks/deployment.md`

## Status Key

- `blocked-external` — requires AWS, Airbyte, DNS, SES, staging, or other operator-controlled environment access.
- `repo-ready` — can be completed inside the repo without waiting on external credentials or runtime access.
- `defer` — valid work, but not on the critical path before release hardening is complete.

## Now

- [x] Complete the SLB product-finish lane in
      `docs/project/evidence/dashthis-replacement/2026-06-30-product-finish-goals.md`: freeze the
      current local target, prove truthful data semantics, rerun/export non-empty CSV/PDF/PNG plus
      dry-run evidence, verify client-facing UX, prove safety/supportability, and run product
      confidence hardening. Treat missing DashThis/source values as optional parity inputs, not
      product blockers. `slb_report_evidence_validate --validation-mode product_finish` now returns
      warning with zero blockers for this lane. Scope: `backend/`, `frontend/`, `docs/`,
      `integrations/exporter/`. Status: `repo-ready` (done locally for PFG-001 through PFG-006 on
      2026-06-30; PFG-007 remains optional if approved source files appear).
- [x] Document Postgres grants for RLS and confirm the deploy pipeline runs both `manage.py seed_roles` and `manage.py enable_rls`. Scope: `docs/`, `deploy/`. Status: `repo-ready`.
- [x] Replace the Home page recent dashboards/static empty state with API-driven data and true empty-state logic. Scope: `frontend/`, `backend/`. Status: `repo-ready`.
- [x] Baseline `docs/project/meta-permissions-catalog.yaml` against runtime/default scope docs and make it the maintained source of truth. Scope: `docs/`. Status: `repo-ready`.
- [x] Update the Meta App Review submission checklist from the canonical permissions catalog and add the release-gate rule for scope changes. Scope: `docs/`. Status: `repo-ready`.
- [x] Implement/verify "Admin audit log view + export" functionality end-to-end. Scope: `frontend/`, `backend/`. Status: `repo-ready`.
- [x] Hardening Permissions: Update `accounts/permissions.py` with granular role checks (IsAnalyst, IsViewer) and hierarchy support. Status: `repo-ready`.
- [x] Add comprehensive tests for `RecentDashboardsView` including tenant isolation and limit parameter. Scope: `backend/`. Status: `repo-ready`.
- [x] Enhance "Report Create" UI with templates and JSON formatting helper. Scope: `frontend/`. Status: `repo-ready`.
- [x] Implement `ScopeFilterBackend` to enforce role-based data isolation across all analytics endpoints. Scope: `backend/`. Status: `repo-ready`.
- [x] Audit Log metadata enrichment (IP, User Agent). Scope: `backend/`. Status: `repo-ready`.
- [x] "Why denied" trace logic in `IsTenantUser` to surface reason for 403. Scope: `backend/`. Status: `repo-ready`.
- [x] Implement `HasPrivilege` across remaining `analytics` and `integrations` viewsets. Scope: `backend/`. Status: `repo-ready`.
- [ ] Confirm staging/prod throttle behavior with expected `429` responses. Local command
      `backend_release_smoke --check-rate-limits` now proves `/api/token/` and public throttle
      behavior; target-env evidence remains required. Status: `blocked-external`.
- [ ] Provision production AWS KMS key/alias and wire the real env values in secret management. Status: `blocked-external`.
- [ ] Load real production Meta/Google credentials and run readiness checks in the target Airbyte environment. Status: `blocked-external`.
- [ ] Run real alert simulations and attach observability evidence. Status: `blocked-external`.
- [ ] Complete SES sender identity, DKIM/SPF/DMARC, and final outbound sender verification. Status: `blocked-external`.
- [ ] Execute the final staging go/no-go rehearsal and archive evidence. Status: `blocked-external`.
- [ ] Finish Meta Ads MVP live verification for SLB, JDIC, and Bedi Walker, plus stale-snapshot UX evidence in a real runtime. Status: `blocked-external`.
- [ ] Complete Phase 0 and Phase 0A of `docs/project/dashthis-replacement-reporting-plan.md`:
      inventory the DashThis reports to replace, confirm required KPIs/outputs, choose the first
      tenant/client proof target, run the adversarial plan review, and record operator questions
      before runtime code changes. Started 2026-06-15 with evidence scaffolding, report inventory
      template, source comparison worksheet, external prerequisite checklist, and adversarial
      findings under `docs/project/evidence/dashthis-replacement/`. Gmail evidence now recommends
      SLB as first proof target; SLB report attachments show full parity requires organic
      Facebook/Instagram metrics, top performers, narrative report sections, and recommendations,
      not only paid-media metrics. Blocked on operator confirmation of full SLB report parity vs
      paid-media-only MVP, required sources, recipients, date range, and source-platform totals.
      Added `docs/project/reporting-builder-architecture-plan.md` to define the custom dashboard
      and report-builder direction: govern the builder through a dataset/metric/dimension/widget
      catalog first, then add backend validation, frontend custom widget creation, SLB monthly
      report templates, combined social semantics, and SaaS hardening.
      Scope: `docs/`. Status: `repo-ready`.

## Next Unblocked Repo Work

The next unchecked `repo-ready` item is the DashThis replacement Phase 0/0A audit. After that audit,
the critical path returns to operator-gated staging activation unless the audit discovers a repo
defect, weak gate, missing scaffolding, or missing reporting surface.

For reporting-builder work, the next repo-ready slice should be docs-first: create the v1
reporting catalog contract described in `docs/project/reporting-builder-architecture-plan.md`.
Do not start with drag-and-drop UI; start with governed dataset, metric, dimension, and widget
schema rules so later backend/frontend work has a stable contract. Include historical coverage and
disconnected-source fallback states so 90-day/monthly reports can render from retained data when a
provider is down, disconnected, or stale. Created 2026-06-15 as
`docs/project/reporting-builder-catalog-contract.md`; the next implementation slice should be
backend-only catalog registry plus `DashboardDefinition.layout` validation for `dashboard.v1`.
Backend audit completed in `docs/project/reporting-builder-backend-data-structure-audit.md`;
recommendation is go, constrained to serializer-layer `dashboard.v1` validation, no model
migration, no report layout validation, and no historical fallback computation in the first slice.

- [x] **Usable pilot delivery (2026-05-26):** Implement real generic report artifacts, encrypted
      notification channel secrets with masked API/UI responses, and scheduled daily summary email
      delivery under `docs/project/usable-pilot-delivery-spec.md`. Scope: `backend/`, `frontend/`,
      `integrations/exporter/`, `docs/`. Status: `repo-ready` (done; Raj/Mira release review and
      staging activation evidence remain required).
- [x] **Notification channel delivery verification (2026-05-01):** Fired tenant-defined alert rules now dispatch to assigned active email, Slack, and webhook `NotificationChannel` targets; channel failures are isolated and config shapes are documented. Scope: `backend/`, `docs/`, `artifacts/roadmap/`. Status: `repo-ready`.
- [x] **Alert evaluation DB rule wiring (2026-05-01):** `AlertService.run_cycle` now evaluates active DB-backed `AlertRuleDefinition` rows alongside built-in system alerts, applies tenant context per DB rule, skips paused rules, auto-resumes expired pauses, and resolves `tenant_alert:<uuid>` metadata in alert history. Scope: `backend/`, `docs/`, `artifacts/roadmap/`. Status: `repo-ready`.
- [x] **Local release gate stabilization (2026-05-01):** Fixed Google Ads frontend test drift, DuckDB demo mart month-end portability, observability external-action doc links, and Makefile Python selection so local preflight/demo commands use the repo venv when available. Scope: `frontend/`, `dbt/`, `docs/`, `Makefile`. Status: `repo-ready`.
- [x] **GA4 Integration (Phase 1):** Complete tenant-scoped OAuth setup, exchange, property discovery, and provisioning endpoints for Google Analytics 4. Scope: `backend/integrations/`. Status: `repo-ready`.
- [x] **Backend test-suite stabilization:** Reconcile canonical backend tests with the current pagination and privilege model (`HasPrivilege`, paginated list responses, upload/report access expectations). Scope: `backend/tests/`. Status: `repo-ready`.
- [x] **GA4 Integration (Phase 2):** Implement `GoogleAnalyticsClient` and KPI fetch helpers (Traffic, Engagement). Scope: `backend/integrations/`. Status: `repo-ready`.
- [x] Frontend: conditional UI rendering based on `tenantContext` role (e.g. hide "Create" for Viewer). Scope: `frontend/`. Status: `repo-ready`.
- [x] Frontend lint stabilization: resolve pre-existing ESLint failures in `src/lib/apiClient.ts` and `src/routes/google-ads/__tests__/GoogleAdsWorkspacePage.test.tsx`. Scope: `frontend/`. Status: `repo-ready`.
- [x] Ops: Enhance `backend-setup` in `docker-compose.yml` with health-checks to block backend start until DB is ready. Scope: `deploy/`. Status: `repo-ready`.
- [x] **Phase 2 Polish (2026-04-10):** Report inline editing, audit log date-range filtering, sync connection detail page, health overview auto-refresh, global error boundary, 404 catch-all, skeleton loaders, unified toast system (Zustand `useToastStore`), Google Ads error states. Scope: `frontend/`, `backend/`. Status: `repo-ready`.
- [x] **Trigger-sync endpoint upgrade (2026-04-10):** `POST /api/airbyte/connections/:id/trigger-sync/` upgraded from 501 stub to full Airbyte integration with audit logging. Scope: `backend/`. Status: `repo-ready`.
- [x] **Audit log date-range filtering (2026-04-10):** `GET /api/audit-logs/` now accepts `start_date`/`end_date` query params. Scope: `backend/`. Status: `repo-ready`.
- [x] dbt demo mart cleanup: fix the DuckDB interval-conversion failure in `dbt/models/marts/demo/vw_demo_dashboard_snapshot.sql` so full `dbt test` is green outside the Meta dashboard path. Scope: `dbt/`. Status: `repo-ready`. Done (2026-05-01).

## Defer Until After Release Hardening

- [ ] GA4 live onboarding completion and Search Console tenant onboarding for the pilot. Scope:
      `backend/`, `frontend/`, `infrastructure/airbyte/`. Status: `defer`.
- [ ] Enterprise UAC UX (`S4-K`). Scope: `frontend/`. Status: `defer`.
- [ ] Remaining Content Operations governance and external readiness for Meta/Facebook/Instagram
      organic publishing (`CO-0A`, `CO-0C`, App Review evidence, asset URL strategy, scheduler
      activation). Scope: `docs/`/future backend slices. Status: `defer`; backend data/API skeleton
      has started under `backend/content_ops/`; implementation backlog:
      `docs/project/content-operations-implementation-backlog.md`.
- [ ] LinkedIn/TikTok connector implementation beyond planning. Scope: `backend/` or `infrastructure/airbyte/`. Status: `defer`.

## Working Order

1. Prefer the highest-priority `repo-ready` item whenever the top `Now` item is blocked by external access.
2. Keep each implementation inside one top-level folder unless Raj and Mira are explicitly brought in.
3. Update this file when an item changes status or is completed so the next session can resume without re-triage.

## Codex Execution Prompt

Use this prompt for the next implementation session:

```text
You are resuming ADinsights from /Users/thristannewman/ADinsights.

First read:
- /Users/thristannewman/ADinsights/AGENTS.md
- /Users/thristannewman/ADinsights/docs/workstreams.md
- /Users/thristannewman/ADinsights/docs/project/phase1-execution-backlog.md
- /Users/thristannewman/ADinsights/docs/project/current-priority-todo.md

Then do the following:
1. Work step by step in this thread; do not use sub-agents.
2. Pick the highest-priority unchecked item in current-priority-todo.md that is marked `repo-ready`.
3. If no unchecked `repo-ready` item exists, do not invent scope. Audit the validation state, summarize the blocked-external staging evidence, and stop before editing.
4. Confirm the work can stay within a single top-level folder. If it cannot, stop and flag Raj/Mira escalation instead of editing.
5. Before editing, state which item you are taking, the folder scope, the exact acceptance criteria, and the canonical tests you will run.
6. Implement the change end-to-end. Do not stop at analysis.
7. Run the canonical tests for the touched folder from AGENTS.md and docs/workstreams.md.
8. Update any required docs/runbooks affected by the change.
9. Update /Users/thristannewman/ADinsights/docs/project/current-priority-todo.md to reflect completion or any newly discovered blockers.
10. Add a one-line entry to /Users/thristannewman/ADinsights/docs/ops/agent-activity-log.md summarizing the work.
11. In the final summary, report:
   - what changed
   - tests/commands run and results
   - remaining blockers
   - the next highest-priority repo-ready item

Guardrails:
- Preserve tenant isolation and RLS.
- Never log or commit secrets.
- Keep changes scoped to one top-level folder unless explicitly escalated.
- Use America/Jamaica when documenting schedules.
```
