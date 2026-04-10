# Post-MVP Spec Gaps

Tracks remaining gaps between the frontend-finished-product-spec and what is actually built.
Updated: 2026-04-10.

## 1. Dashboard Library (DONE)

Dashboard library is live with API integration (system templates + saved dashboards).
Supports rename, duplicate, archive, delete actions.

### Remaining gaps
- None for core library functionality.

## 2. Alerts (WORKING)

Alert rules list page, alert detail page, and alert creation page are built. All consume live API data.

### What is built
- Alerts list with name, metric, rule, severity, active/inactive status column, and updated timestamp columns.
- Alert detail page showing rule metadata (metric, comparison, threshold, lookback, severity).
- Alert creation page with notification channel assignment (AlertCreatePage.tsx).
- Alert detail page with notification channel assignment and delete button with confirm dialog.
- Notification channels CRUD management page at /settings/notifications (NotificationChannelsPage.tsx).
- Confirm dialogs for destructive actions (delete alert, delete channel).
- Toast notifications for CRUD feedback.
- Loading, error, and empty states on both pages.

### Remaining gaps
- No alert history/runs page (backend API exists at /api/alerts/runs/).
- No alert pause/resume UI controls.

## 3. AI Summaries (WORKING)

Summaries list and summary detail pages are built.

### What is built
- Summaries list page with title, status pill, and generated-at timestamps.
- Summary detail page with summary text and raw payload snapshot.
- AI summary source badges ("Daily"/"Manual") on SummariesPage and SummaryDetailPage.
- AI summary schedule info banner on SummariesPage.
- Loading, error, and empty states.

### Remaining gaps
- No summary regeneration controls.

## 4. Reports (WORKING)

Report builder (create), reports library (list), and report detail with export jobs are built.

### What is built
- Report create page with name, description, filters (JSON), layout (JSON), and quick templates.
- Reports library with name, description, and timestamps.
- Report detail page with CSV/PDF/PNG export job creation and job status table.
- Role-based access: viewers get read-only messaging on create page.
- Report scheduled delivery UI with toggle, cron expression, and email recipients (ReportDetailPage.tsx).

### Remaining gaps
- No report editing (only create and view, no edit form).
- No delivery status tracking for scheduled reports.

## 5. Sync Health (WORKING)

Sync health page is built with connection status table.

### What is built
- Connection table with name, provider, status pill, last sync timestamps, and job errors.
- Summary stat cards (total, fresh, stale, failed connections).
- Re-sync / "run now" controls per connection (SyncHealthPage.tsx).
- Loading, error, and empty states.

### Remaining gaps
- No provider or status filter dropdowns on the table.
- No drill-through to connection detail page.

## 6. Audit Log (WORKING)

Audit log page is built with action/resource filters and server-side CSV export.

### What is built
- Audit log table with action, resource type, detail, user, and timestamp columns.
- Action and resource type text filters.
- Server-side audit CSV export at /api/audit-logs/export_csv/ (AuditLogPage uses window.open).

### Remaining gaps
- No date range filter.
- No pagination controls visible (backend pagination exists but UI does not expose it).

## 7. Health Overview (DONE)

Health checks overview page is built, showing status for all required health endpoints.

### Remaining gaps
- None for core health overview.

## 8. Toast Notification System (DONE)

ToastProvider (useToastStore + ToastContainer) is implemented and wired into the app shell.
Toast notifications are used consistently across CRUD operations including dashboard library, alerts, reports, and notification channels.

### Remaining gaps
- None.

## 9. Cross-Cutting Gaps

- Confirm dialogs for destructive actions are now built (delete channel, delete alert).
- Notification channels CRUD is built as a standalone management page at /settings/notifications.

### Remaining cross-cutting gaps
- /me profile page (no frontend yet, backend GET /api/me/ exists).
- CSV upload detail page at /dashboards/uploads/:id.
- Configurable stale threshold per tenant.
- Historical trend views (sync health, health overview).
- Health overview alerting on degradation.
