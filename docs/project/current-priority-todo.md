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
- [ ] Confirm staging/prod throttle behavior for `/api/token/`, `/api/auth/login/`, and `/api/auth/password-reset/` with expected `429` responses. Status: `blocked-external`.
- [ ] Provision production AWS KMS key/alias and wire the real env values in secret management. Status: `blocked-external`.
- [ ] Load real production Meta/Google credentials and run readiness checks in the target Airbyte environment. Status: `blocked-external`.
- [ ] Run real alert simulations and attach observability evidence. Status: `blocked-external`.
- [ ] Complete SES sender identity, DKIM/SPF/DMARC, and final outbound sender verification. Status: `blocked-external`.
- [ ] Execute the final staging go/no-go rehearsal and archive evidence. Status: `blocked-external`.

## Next Unblocked Repo Work

- [x] **GA4 Integration (Phase 1):** Complete tenant-scoped OAuth setup, exchange, property discovery, and provisioning endpoints for Google Analytics 4. Scope: `backend/integrations/`. Status: `repo-ready`.
- [x] **Backend test-suite stabilization:** Reconcile canonical backend tests with the current pagination and privilege model (`HasPrivilege`, paginated list responses, upload/report access expectations). Scope: `backend/tests/`. Status: `repo-ready`.
- [x] **GA4 Integration (Phase 2):** Implement `GoogleAnalyticsClient` and KPI fetch helpers (Traffic, Engagement). Scope: `backend/integrations/`. Status: `repo-ready`.
- [x] Frontend: conditional UI rendering based on `tenantContext` role (e.g. hide "Create" for Viewer). Scope: `frontend/`. Status: `repo-ready`.
- [x] Frontend lint stabilization: resolve pre-existing ESLint failures in `src/lib/apiClient.ts` and `src/routes/google-ads/__tests__/GoogleAdsWorkspacePage.test.tsx`. Scope: `frontend/`. Status: `repo-ready`.
- [x] Ops: Enhance `backend-setup` in `docker-compose.yml` with health-checks to block backend start until DB is ready. Scope: `deploy/`. Status: `repo-ready`.

## Defer Until After Release Hardening

- [ ] Enterprise UAC UX (`S4-K`). Scope: `frontend/`. Status: `defer`.
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
1. Pick the highest-priority unchecked item in current-priority-todo.md that is marked `repo-ready`.
2. Confirm the work can stay within a single top-level folder. If it cannot, stop and flag Raj/Mira escalation instead of editing.
3. Before editing, state which item you are taking, the folder scope, the exact acceptance criteria, and the canonical tests you will run.
4. Implement the change end-to-end. Do not stop at analysis.
5. Run the canonical tests for the touched folder from AGENTS.md and docs/workstreams.md.
6. Update any required docs/runbooks affected by the change.
7. Update /Users/thristannewman/ADinsights/docs/project/current-priority-todo.md to reflect completion or any newly discovered blockers.
8. Add a one-line entry to /Users/thristannewman/ADinsights/docs/ops/agent-activity-log.md summarizing the work.
9. In the final summary, report:
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
