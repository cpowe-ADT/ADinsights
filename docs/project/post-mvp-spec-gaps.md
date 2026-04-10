# Post-MVP Feature Audit and Spec Gaps

Audit date: 2026-04-10 (updated with second build-out closing remaining spec gaps)

## Summary Table

| # | Feature | Route(s) | Rating | Frontend Tests | Backend Endpoint |
|---|---------|----------|--------|---------------|-----------------|
| 1 | Reports | `/reports`, `/reports/new`, `/reports/:reportId` | WORKING | Yes (ReportsPage) | `/api/reports/` CRUD + `/api/reports/{id}/exports/` |
| 2 | Alerts | `/alerts`, `/alerts/:alertId` | WORKING | Yes (AlertsPage) | `/api/alerts/` CRUD (AlertRuleDefinition) |
| 3 | AI Summaries | `/summaries`, `/summaries/:summaryId` | WORKING | Yes (SummariesPage) | `/api/summaries/` read-only + `/api/summaries/refresh/` |
| 4 | Sync Health | `/ops/sync-health` | WORKING | Yes (SyncHealthPage) | `/api/ops/sync-health/` |
| 5 | Health Overview | `/ops/health` | WORKING | Yes (HealthOverviewPage) | `/api/ops/health-overview/` |
| 6 | Audit Log | `/ops/audit` | WORKING | Yes (AuditLogPage) | `/api/audit-logs/` paginated list |

## Detailed Findings

### 1. Reports (WORKING)

Full CRUD implementation with list, create, and detail pages. Backend `ReportDefinitionViewSet` supports all REST operations plus nested `/exports/` action for requesting CSV/PDF/PNG exports via Celery. Export download available at `/api/exports/<uuid>/download/`. Report creation is gated by RBAC (`canAccessCreatorUi`). Internal reports can be toggled visible via checkbox filter.

**Closed gaps (2026-04-10):**
- ~~No inline report editing on the detail page~~ — Edit/Save/Cancel inline editing added to ReportDetailPage.
- ~~Export job polling is manual~~ — Auto-polling (5s interval, 60s max) added to ReportDetailPage for pending exports.

**Closed gaps (2026-04-10, second build-out):**
- ~~No scheduled delivery UI~~ — Schedule section added to ReportDetailPage with enable toggle, cron expression input, delivery emails, and save action. Backend fields (`schedule_enabled`, `schedule_cron`, `delivery_emails`, `last_scheduled_at`) and `toggle_schedule` action added.

**Remaining gaps:**
- None for Reports.

### 2. Alerts (WORKING)

Frontend list and detail pages consume the `AlertsViewSet`, which extends `AlertRuleDefinitionViewSet` from the integrations app. Backend serializer fields (`name`, `metric`, `comparison_operator`, `threshold`, `lookback_hours`, `severity`) align with the frontend `AlertRule` type. Note: there is a separate `AlertRun` model/viewset at `/api/alerts/runs/` for execution history which is not surfaced in the frontend.

**Closed gaps (2026-04-10):**
- ~~No alert creation UI~~ — AlertCreatePage added at `/alerts/new` with full form (name, metric, operator, threshold, lookback, severity). Gated by `canAccessCreatorUi`.
- ~~Alert run history not displayed~~ — AlertDetailPage now shows AlertRunHistory table via `listAlertRuns`.

**Closed gaps (2026-04-10, second build-out):**
- ~~No notification channel configuration~~ — `NotificationChannel` model added (email/webhook/slack) with full CRUD at `/api/notification-channels/`. M2M on `AlertRuleDefinition`. Frontend page at `/settings/notifications` with create form and channel list. Alert detail page shows channel assignment with checkboxes.

**Remaining gaps:**
- None for Alerts.

### 3. AI Summaries (WORKING)

Read-only list with detail view and manual refresh action. Backend `AISummaryViewSet` is read-only with a `refresh` action that calls `generate_ai_summary_for_tenant`. Summaries display title, status (generated/fallback/failed), source, and raw payload.

**Closed gaps (2026-04-10, second build-out):**
- ~~No automatic/scheduled summary generation UI~~ — Info banner added to SummariesPage showing the 6:10 AM daily schedule. Source badges ("Daily" / "Manual") displayed in list and detail views.
- ~~No summary editing or annotation capability~~ — Summary detail page enhanced with source badge, model name display, and collapsible raw payload section.

**Remaining gaps:**
- Refresh action is synchronous and may time out for large tenants.

### 4. Sync Health (WORKING)

Displays Airbyte connection health with state classification (fresh/stale/failed/missing/inactive) and aggregate counts. Backend reads directly from `AirbyteConnection` model. Stale threshold is hardcoded at 2 hours.

**Closed gaps (2026-04-10, second build-out):**
- ~~No direct action to trigger a re-sync from this page~~ — Per-row "Re-sync" button added (wired to stub backend action returning 501). State filter bar (All/Fresh/Stale/Failed/Missing/Inactive) and "Last refreshed" timestamp with manual refresh added.

**Remaining gaps:**
- No configurable stale threshold per tenant.
- No historical trend view (current snapshot only).

### 5. Health Overview (WORKING)

Aggregates responses from the four health endpoints (`/api/health/`, `/api/health/airbyte/`, `/api/health/dbt/`, `/api/timezone/`) into cards with overall status derivation (ok/degraded/error). Frontend displays card key, HTTP status, and detail.

**Remaining gaps:**
- No historical uptime tracking.
- No alerting integration when status degrades.

### 6. Audit Log (WORKING)

Paginated, filterable audit event list with JSON export. Backend `AuditLogViewSet` supports `action` and `resource_type` query filters. Frontend includes client-side JSON blob download.

**Closed gaps (2026-04-10):**
- ~~No date range filtering~~ — Start/end date inputs added with 30-day default, passed to backend.
- ~~No pagination controls~~ — Previous/Next buttons with "Page X of Y" display added.
- ~~Client-side JSON only~~ — CSV export button added alongside JSON export.

**Closed gaps (2026-04-10, second build-out):**
- ~~No server-side CSV export~~ — `export_csv` action added to `AuditLogViewSet` returning `StreamingHttpResponse` with full CSV. Frontend CSV export button now opens the server-side endpoint directly.

**Remaining gaps:**
- None for Audit Log.
