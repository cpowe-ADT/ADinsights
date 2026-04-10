# Post-MVP Spec Gaps

Tracks remaining gaps between the frontend-finished-product-spec and what is actually built.
Updated: 2026-04-10.

## 1. Dashboard Library (DONE)

Dashboard library is live with API integration (system templates + saved dashboards).
Supports rename, duplicate, archive, delete actions.

### Remaining gaps
- None for core library functionality.

## 2. Alerts (WORKING)

Alert rules list page and alert detail page are built. Both consume live API data.

### What is built
- Alerts list with name, metric, rule, severity, and updated timestamp columns.
- Alert detail page showing rule metadata (metric, comparison, threshold, lookback, severity).
- Loading, error, and empty states on both pages.

### Remaining gaps
- Alert creation page does not yet include notification channel assignment during creation.
- Alert detail page does not include delete functionality.
- Alerts list does not show active/inactive status column.
- No notification channels CRUD UI (create/edit/delete channels).
- No confirm dialogs for destructive actions (delete alert).
- No alert history/triggered events timeline.
- No alert pause/resume controls.

## 3. AI Summaries (WORKING)

Summaries list and summary detail pages are built.

### What is built
- Summaries list page with title, status pill, and generated-at timestamps.
- Summary detail page with summary text and raw payload snapshot.
- Loading, error, and empty states.

### Remaining gaps
- No source badges showing which dashboard/data source generated the summary.
- No schedule info on summary detail page.
- No summary regeneration controls.

## 4. Reports (WORKING)

Report builder (create), reports library (list), and report detail with export jobs are built.

### What is built
- Report create page with name, description, filters (JSON), layout (JSON), and quick templates.
- Reports library with name, description, and timestamps.
- Report detail page with CSV/PDF/PNG export job creation and job status table.
- Role-based access: viewers get read-only messaging on create page.

### Remaining gaps
- Scheduled delivery UI is referenced in copy but not yet a configurable form field.
- No report editing (only create and view).
- No delivery status tracking for scheduled reports.

## 5. Sync Health (WORKING)

Sync health page is built with connection status table.

### What is built
- Connection table with name, provider, status pill, last sync timestamps, and job errors.
- Summary stat cards (total, fresh, stale, failed connections).
- Loading, error, and empty states.

### Remaining gaps
- No re-sync / "run now" controls per connection.
- No provider or status filters on the table.
- No drill-through to connection detail page.

## 6. Audit Log (WORKING)

Audit log page is built with action/resource filters and JSON export.

### What is built
- Audit log table with action, resource type, detail, user, and timestamp columns.
- Action and resource type text filters.
- Client-side JSON export of current view.

### Remaining gaps
- Server-side CSV export (current export is client-side JSON only).
- No date range filter.
- No pagination controls visible (backend pagination exists but UI does not expose it).

## 7. Health Overview (DONE)

Health checks overview page is built, showing status for all required health endpoints.

### Remaining gaps
- None for core health overview.

## 8. Toast Notification System (DONE)

ToastProvider is implemented and wired into the app shell.

### Remaining gaps
- Not yet used consistently across all CRUD operations (dashboard library uses it; alerts/reports do not).

## 9. Cross-Cutting Gaps

- No confirm dialogs for destructive actions across the app (delete channel, delete alert, delete report).
- Notification channels CRUD is not yet built as a standalone management page.
