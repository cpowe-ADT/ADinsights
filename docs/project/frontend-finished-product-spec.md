# ADinsights Finished Frontend Product Spec

Status: Approved (2026-02-01). Reviewed by Lina (Frontend Architect) and Joel (Design System).

Purpose: single, exhaustive list of everything the ADinsights frontend should allow a user to do
when the product is fully finished. This spec is organized by maturity (MVP, Post-MVP, Enterprise)
and by functional grouping required by product and engineering.

Sources: README.md, docs/task_breakdown.md, docs/workstreams.md, UI screenshots (Home, Create
dashboard, Campaigns dashboard, Budget pacing).

Legend:

- MVP: must-have for a usable multi-tenant analytics product.
- Post-MVP: advanced analytics, reporting, and ops management features.
- Enterprise: UAC, approvals, agency portfolio, and compliance features.

## Review notes

- 2026-02-01: Approved by Lina (Frontend Architect) and Joel (Design System) per PM confirmation;
  no blocking gaps noted.
- Review checklist: `docs/project/frontend-spec-review-checklist.md`.

## A0) Information architecture (IA) & module map

Primary navigation (end-state) groups the product into five user-facing areas, with tenant context
and global filters shared across all analytics views:

- **Home**: quick actions, recent dashboards, release notes/docs links.
- **Dashboards**: campaign performance, creative insights, budget pacing, parish map, dashboard library/create.
- **Reporting**: report builder + reports library, exports (PDF/PNG/CSV by entitlement), board packs (Enterprise).
- **Alerts & AI**: alert rules/history, AI summaries list/detail, recipients and delivery status.
- **Admin/Settings**: profile/me, users/roles, tenant/workspace settings, entitlements, audit log, approvals/why-denied (Enterprise), ops health/sync health.

Cross-cutting UI (global):

- Tenant switcher + tenant context banner.
- Dataset mode toggle (live warehouse default; demo opt-in).
- Snapshot freshness indicator (relative + absolute timestamp, stale warning).
- Global filter bar (date range, channel(s), campaign search) applied consistently.
- Share controls (copy link), personalization (save layout), theme toggle (light/dark).

### Module → routes (quick map)

The tables below are a non-duplicative index: each module links to the detailed route specs in
Section A and API/contracts in Section E.

| Module           | MVP routes                                                                                                      | Post‑MVP routes                                                      | Enterprise routes                                                                                                        |
| ---------------- | --------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Onboarding       | `/login`, `/password-reset`, `/invite`, `/`                                                                     | `/me`                                                                | —                                                                                                                        |
| Data connections | `/dashboards/data-sources` (placeholder)                                                                        | `/ops/sync-health`, `/dashboards/uploads`, `/dashboards/uploads/:id` | —                                                                                                                        |
| Dashboards       | `/dashboards/create`, `/dashboards/campaigns`, `/dashboards/creatives`, `/dashboards/budget`, `/dashboards/map` | `/dashboards` (library)                                              | `/agency/portfolio`                                                                                                      |
| Reporting        | —                                                                                                               | `/reports`, `/reports/new`, `/reports/:id`                           | `/board-packs`, `/board-packs/:id`                                                                                       |
| Alerts/AI        | —                                                                                                               | `/alerts`, `/alerts/:id`, `/summaries`, `/summaries/:id`             | —                                                                                                                        |
| Admin/Settings   | —                                                                                                               | `/me`, `/ops/health`                                                 | `/approvals`, `/approvals/:id`, `/ops/audit`, `/why-denied`, `/support/impersonate`, `/access-review`, `/agency/tenants` |
| Docs/Help        | `/` (links)                                                                                                     | —                                                                    | —                                                                                                                        |

## A1) Feature inventory by module (end-user; no duplicates)

This section lists the complete end-user functionality by module in the requested format. It
references routes from Section A; route entries remain the source of truth for view/filter/drill/
states so we don’t duplicate those details here.

Notes on roles:

- This spec uses the simplified tenant roles **Owner/Admin/Analyst/Viewer** as shorthand.
- Enterprise/UAC roles (agency/client/support variants) are defined in `docs/security/uac-spec.md`.

### Onboarding

- **User can authenticate and recover access.**
  - Roles: Owner/Admin/Analyst/Viewer
  - Primary screens: `/login`, `/password-reset`, `/invite`
  - Key UI components: forms with validation, loading states, error messaging, redirect-to-intended-route
  - Data dependencies: auth tokens (`access`, `refresh`), invitation token, password reset token, `/api/me/`
  - Acceptance criteria:
    - Valid login establishes tenant context and redirects to the requested page.
    - Invalid credentials show a clear error and do not set tenant context.
    - Invite/password reset flows handle missing/expired tokens with actionable guidance.
  - Priority: MVP

- **User can land on Home and get oriented quickly.**
  - Roles: Owner/Admin/Analyst/Viewer
  - Primary screens: `/`
  - Key UI components: quick actions, recent dashboards, docs/release notes links, empty state CTA
  - Data dependencies: optional “recent dashboards” metadata; docs URLs configured via env
  - Acceptance criteria:
    - No dashboards shows a guided empty state with “Create dashboard” CTA.
    - Docs/release links open safely (new tab where applicable).
  - Priority: MVP

### Data Connections

- **User can see connector status and sync freshness, and take recovery actions.**
  - Roles: Owner/Admin (manage), Analyst (view), Viewer (view-limited)
  - Primary screens: `/dashboards/data-sources` (MVP placeholder), `/ops/sync-health` (Post‑MVP)
  - Key UI components: connector cards, last sync timestamps, status pills (fresh/stale/misconfigured), runbook links, “run now” controls (Post‑MVP)
  - Data dependencies: Airbyte connections + telemetry, health endpoints, adapter availability
  - Acceptance criteria:
    - If no integrations exist, show a “Connect data sources” empty state with setup guidance.
    - Failed syncs show error reason and a link to the relevant runbook.
    - Permission denied shows a clear message and next step (contact admin / why denied in Enterprise).
  - Priority: V1

- **User can upload CSVs and monitor ingestion jobs.**
  - Roles: Owner/Admin (and entitled roles)
  - Primary screens: `/dashboards/uploads`, `/dashboards/uploads/:id`
  - Key UI components: upload wizard, mapping/validation preview, job status, error summaries, exportable error report
  - Data dependencies: upload jobs, validation summaries (aggregated), ingestion pipeline
  - Acceptance criteria:
    - Invalid files and schema mismatches fail fast with actionable errors.
    - Job status survives refresh and supports retry on recoverable failures.
  - Priority: V1

### Dashboards

- **User can navigate tenant-scoped dashboards with consistent global controls.**
  - Roles: Owner/Admin/Analyst/Viewer
  - Primary screens: `/dashboards/*`
  - Key UI components: tenant switcher, dataset toggle, snapshot indicator, filter bar, breadcrumbs, theme toggle, save layout, copy link
  - Data dependencies: combined metrics endpoint or aggregate snapshot endpoint, tenant list, adapters endpoint
  - Acceptance criteria:
    - Live warehouse is the default; demo mode is explicit opt-in.
    - Stale snapshots (>60m) show a warning with absolute timestamp tooltip.
    - Tenant switching clears parish selection and refreshes data in the new tenant context.
  - Priority: MVP

- **User can drill from dashboards into entity detail pages without losing context.**
  - Roles: Owner/Admin/Analyst/Viewer
  - Primary screens: `/dashboards/campaigns/:id`, `/dashboards/creatives/:id`
  - Key UI components: “back” affordances, deep links, context-preserving filters
  - Data dependencies: campaign/creative dimensions + aggregates
  - Acceptance criteria:
    - 404/missing entities show “not found” with safe return CTA.
    - Copy link preserves filters/selection and enforces authorization on open.
  - Priority: MVP

### Campaigns

- **User can analyze campaign performance and export the current table view.**
  - Roles: Owner/Admin/Analyst/Viewer (exports gated by entitlement/role in Post‑MVP/Enterprise)
  - Primary screens: `/dashboards/campaigns`, `/dashboards/campaigns/:id`
  - Key UI components: KPI cards, daily trend chart, choropleth, sortable table, export control, empty/loading/error states
  - Data dependencies: spend/impressions/clicks/conversions/ROAS + derived rates, currency, snapshot timestamp
  - Acceptance criteria:
    - Filters update KPIs, trend, map, and table consistently.
    - Empty states distinguish “no data yet” vs “no results for filters”.
    - Export includes only aggregated metrics and records an audit event when enabled.
  - Priority: MVP (analysis), V1 (exports)

### Creatives

- **User can review creatives, preview thumbnails, and drill to creative detail.**
  - Roles: Owner/Admin/Analyst/Viewer
  - Primary screens: `/dashboards/creatives`, `/dashboards/creatives/:id`
  - Key UI components: sortable table, thumbnail previews with fallback, cross-links to campaigns, empty/loading/error states
  - Data dependencies: creative aggregates + optional thumbnail URL, creative→campaign relationship
  - Acceptance criteria:
    - Missing thumbnails fall back gracefully; no broken images.
    - No creatives match filters yields an explicit “no matches” state.
  - Priority: MVP

### Budget pacing

- **User can monitor monthly pacing and identify under/over-spend risk.**
  - Roles: Owner/Admin/Analyst/Viewer
  - Primary screens: `/dashboards/budget`
  - Key UI components: pacing list, progress indicators, status categories, filter status, empty/loading/error states
  - Data dependencies: budget rows (`monthlyBudget`, `spendToDate`, `projectedSpend`, `pacingPercent`, optional `parishes`, `startDate`, `endDate`)
  - Acceptance criteria:
    - “No pacing data yet” shows guidance without breaking layout.
    - Date/currency formatting matches tenant settings when available.
  - Priority: MVP

### Parish map

- **User can explore parish-level performance and use the map as a filter.**
  - Roles: Owner/Admin/Analyst/Viewer
  - Primary screens: `/dashboards/map` and embedded map on `/dashboards/campaigns`
  - Key UI components: choropleth with legend/tooltips, metric selector, accessible parish selection list, “open full map”, scroll-zoom toggle
  - Data dependencies: parish GeoJSON + parish aggregates aligned on parish naming
  - Acceptance criteria:
    - Geometry or data load failures are explicit and retryable.
    - Tooltip rendering guards against missing values and never crashes.
  - Priority: MVP

### Reporting

- **User can build, export, and schedule reports using aggregated metrics only.**
  - Roles: Owner/Admin/Analyst (Viewer read-only by policy)
  - Primary screens: `/reports`, `/reports/new`, `/reports/:id`
  - Key UI components: template picker, narrative blocks, widget selection/layout, preview, export dialog (PDF/PNG/CSV by entitlement), history and delivery status
  - Data dependencies: report configs, export service/jobs, snapshot timestamp used for exports
  - Acceptance criteria:
    - “No data for selected range” blocks export and suggests changing filters.
    - Export includes snapshot timestamp; failures are retryable and audited.
  - Priority: V1

### Alerts/AI

- **User can configure alert rules and view history with AI summaries (with safe fallback).**
  - Roles: Owner/Admin/Analyst (Viewer read-only)
  - Primary screens: `/alerts`, `/alerts/:id`, `/summaries`, `/summaries/:id`
  - Key UI components: rules list, rule editor, recipients, history table, AI summary panel, raw payload fallback
  - Data dependencies: alert rules/runs, delivery config, AI summary outputs (aggregated only)
  - Acceptance criteria:
    - If AI summary generation fails, the UI still renders the raw aggregated results.
    - Alert history is tenant-scoped and filterable; empty states guide setup.
  - Priority: V1

### Admin/Settings

- **User can manage users/roles, view ops health, and access audit evidence (by permission).**
  - Roles: Owner/Admin (manage), Analyst (view), Viewer (view-limited)
  - Primary screens: `/me`, `/ops/health`, `/ops/audit` (Enterprise), plus admin settings pages
  - Key UI components: role badges, member lists/invite flows, health status cards, audit log table + exports
  - Data dependencies: `/api/me/`, tenants/memberships, health endpoints, audit log endpoints
  - Acceptance criteria:
    - Permission denied states are explicit (403) and provide next steps.
    - Health endpoints surfaced match the required backend health contract.
  - Priority: V1 (health + basic admin), V2 (audit exports + UAC surfaces)

### Docs/Help

- **User can access docs/runbooks from within the product and from error states.**
  - Roles: Owner/Admin/Analyst/Viewer
  - Primary screens: `/` and contextual links throughout
  - Key UI components: docs/release links, runbook links on failures (sync, snapshot, export)
  - Data dependencies: docs URLs/config; runbook paths in repo
  - Acceptance criteria:
    - Sync/export/snapshot failures include a relevant runbook link in the UI.
  - Priority: MVP

## A) Pages/Routes

### MVP

- Login (/login)
  - view: email/password login, optional SSO placeholder, system status hint.
  - filter: n/a.
  - drill: password reset, docs, release notes.
  - export/share: n/a.
  - no data: validation errors, "no tenant access" messaging.
  - stale data: show last health-check timestamp if surfaced; otherwise n/a.
- Password reset request (/password-reset)
  - view: request form, confirmation state.
  - filter: n/a.
  - drill: back to login.
  - export/share: n/a.
  - no data: "email not found" messaging.
  - stale data: token expiry guidance; n/a for metrics.
- Password reset confirm (/password-reset?token=... or /password-reset/confirm)
  - view: token + new password form, success/error state.
  - filter: n/a.
  - drill: back to login.
  - export/share: n/a.
  - no data: invalid/expired token messaging.
  - stale data: show token expiry timestamp if available.
- Home (/)
  - view: hero CTA, quick actions, recent dashboards, release notes link.
  - filter: n/a.
  - drill: create dashboard, connect data sources, CSV upload, recent dashboards.
  - export/share: invite teammate (mailto), copy docs/release notes links.
  - no data: "No dashboards yet" empty state with CTA.
  - stale data: show last snapshot timestamp if surfaced for recent dashboards.
- Profile/Me (/me)
  - view: user profile, tenant memberships, role badges, last login.
  - filter: n/a.
  - drill: change password, view audit log (if allowed).
  - export/share: n/a.
  - no data: "profile unavailable" state with retry.
  - stale data: show last profile/role update time.
- Create dashboard (/dashboards/create)
  - view: template selection, connect sources, upload CSV prompts.
  - filter: n/a.
  - drill: campaign dashboard, data sources, CSV uploads.
  - export/share: n/a.
  - no data: "no sources connected" hint and CTA to connect.
  - stale data: show last sync timestamp for available sources.
- Campaigns dashboard (/dashboards/campaigns)
  - view: KPI cards, daily spend trend, parish choropleth, campaign table.
  - filter: time range presets/custom, channel, campaign search, map metric.
  - drill: parish click -> filtered table, open map detail, campaign detail.
  - export/share: copy link, export table (Post-MVP).
  - no data: "No campaign insights yet" + "No trend data yet".
  - stale data: snapshot banner with relative + absolute timestamp and stale warning.
- Campaign detail (/dashboards/campaigns/:id)
  - view: campaign KPIs, metadata, related creatives table.
  - filter: inherits global filters.
  - drill: creative detail.
  - export/share: copy link, export related creatives (Post-MVP).
  - no data: "Campaign not found" state.
  - stale data: snapshot banner + timestamp tooltip.
- Creatives dashboard (/dashboards/creatives)
  - view: creative leaderboard table, thumbnails/previews, key metrics.
  - filter: global filters + parish selection.
  - drill: creative detail, campaign detail via links.
  - export/share: copy link, export table (Post-MVP).
  - no data: "No creative insights yet" state.
  - stale data: snapshot banner + timestamp tooltip.
- Creative detail (/dashboards/creatives/:id)
  - view: creative KPIs, preview, overview attributes.
  - filter: inherits global filters.
  - drill: back to campaign, cross-links to related dashboards.
  - export/share: copy link, export summary (Post-MVP).
  - no data: "Creative not found" state.
  - stale data: snapshot banner + timestamp tooltip.
- Budget pacing (/dashboards/budget)
  - view: monthly pacing list, planned vs actual status.
  - filter: global filters + parish selection.
  - drill: campaign detail, budget planner (Post-MVP).
  - export/share: copy link, export pacing summary (Post-MVP).
  - no data: "No budget pacing yet" state.
  - stale data: snapshot banner + timestamp tooltip.
- Parish heatmap detail (/dashboards/map)
  - view: full-width choropleth, legend, tooltip.
  - filter: map metric selector, global filters.
  - drill: parish click -> filtered tables, campaigns/creatives.
  - export/share: copy link, export map image (Post-MVP).
  - no data: "No parish data yet" state.
  - stale data: snapshot banner + timestamp tooltip.
- Invite + onboarding (/invite, /onboarding)
  - view: invite acceptance, tenant/workspace selection, first-time setup.
  - filter: n/a.
  - drill: back to login, dashboard.
  - export/share: n/a.
  - no data: invalid invite token messaging.
  - stale data: show invite expiry timestamp if available.

### Post-MVP

- Data sources (/dashboards/data-sources)
  - view: connector list, status, schedule, last sync, next run.
  - filter: provider, status, workspace.
  - drill: connection detail, run now, pause/resume.
  - export/share: export connection summary (CSV/PDF), copy link.
  - no data: "No sources connected" state.
  - stale data: last sync timestamp with stale warning.
- Data source detail (/dashboards/data-sources/:id)
  - view: credentials status (masked), schedule, last jobs, errors.
  - filter: job status, time range.
  - drill: retry job, edit schedule, rotate credentials.
  - export/share: export job history, copy link.
  - no data: "No jobs yet" state.
  - stale data: last job timestamp + stale sync banner.
- CSV uploads (/dashboards/uploads)
  - view: upload wizard, mapping, validation preview, job history.
  - filter: data type, date range.
  - drill: job detail, error row view (aggregated).
  - export/share: download validation report.
  - no data: "No uploads yet" state.
  - stale data: last import timestamp + stale banner.
- Upload job detail (/dashboards/uploads/:id)
  - view: job status, row counts, validation errors.
  - filter: error type.
  - drill: back to uploads.
  - export/share: export error report.
  - no data: "Job not found" state.
  - stale data: job last update timestamp.
- Dashboard library (/dashboards)
  - view: list of dashboards, owners, last viewed.
  - filter: owner, tag, time range.
  - drill: open, duplicate, rename, delete.
  - export/share: share link, export dashboard config.
  - no data: "No dashboards yet" state.
  - stale data: last snapshot timestamp per dashboard.
- Reports library (/reports)
  - view: report list, status, last generated time.
  - filter: owner, tag, time range.
  - drill: report detail, edit, schedule delivery.
  - export/share: export PDF/PNG, copy link.
  - no data: "No reports yet" state.
  - stale data: last generated timestamp.
- Report builder (/reports/new)
  - view: template picker, narrative blocks, widget selection.
  - filter: time range, channel, campaign.
  - drill: preview, edit layout.
  - export/share: export PDF/PNG, share link, schedule delivery.
  - no data: "No data for selected range" state.
  - stale data: snapshot timestamp used for preview/export.
- Report detail (/reports/:id)
  - view: report overview, history, delivery status.
  - filter: delivery status, time range.
  - drill: regenerate, edit, share.
  - export/share: export PDF/PNG, copy link.
  - no data: "Report not found" state.
  - stale data: last generated timestamp.
- Alerts (/alerts)
  - view: alert rules list, status, last triggered time.
  - filter: metric, channel, severity.
  - drill: alert detail, edit, pause.
  - export/share: export alert list (CSV/PDF).
  - no data: "No alerts configured" state.
  - stale data: last evaluation timestamp.
- Alert detail (/alerts/:id)
  - view: rule definition, history, recipients.
  - filter: time range, delivery status.
  - drill: edit rule, test delivery.
  - export/share: export history.
  - no data: "Alert not found" state.
  - stale data: last evaluation timestamp.
- AI summaries (/summaries)
  - view: summaries list, source dashboard, time range.
  - filter: dashboard, time range.
  - drill: summary detail.
  - export/share: share link, export PDF/PNG.
  - no data: "No summaries yet" state.
  - stale data: snapshot timestamp used for summary.
- Summary detail (/summaries/:id)
  - view: narrative, data sources used, transparency notes.
  - filter: n/a.
  - drill: open source dashboard with filters.
  - export/share: export PDF/PNG, share link.
  - no data: "Summary not found" state.
  - stale data: snapshot timestamp used for summary.
- Budget planner (/budgets/edit)
  - view: planned budgets by campaign/parish/channel, forecast.
  - filter: time range, channel, parish.
  - drill: propose changes, compare plan vs actual.
  - export/share: export plan summary.
  - no data: "No budget plan yet" state.
  - stale data: last saved timestamp.
- Ad set detail (/dashboards/adsets/:id)
  - view: KPIs, targeting, pacing.
  - filter: global filters.
  - drill: ad detail, campaign detail.
  - export/share: export table/summary.
  - no data: "Ad set not found" state.
  - stale data: snapshot banner + timestamp tooltip.
- Ad detail (/dashboards/ads/:id)
  - view: KPIs, placements, creative preview.
  - filter: global filters.
  - drill: ad set/campaign detail.
  - export/share: export table/summary.
  - no data: "Ad not found" state.
  - stale data: snapshot banner + timestamp tooltip.
- Sync health (/ops/sync-health)
  - view: latest Airbyte jobs, success/failure rates, API cost.
  - filter: provider, status, time range.
  - drill: job detail, retry guidance.
  - export/share: export telemetry (CSV/PDF).
  - no data: "No syncs yet" state.
  - stale data: last telemetry refresh timestamp.
- Health checks (/ops/health)
  - view: status for /api/health/, /api/health/airbyte/, /api/health/dbt/, /api/timezone/.
  - filter: component, status.
  - drill: runbook links for failures.
  - export/share: export health report.
  - no data: "Health data unavailable" state.
  - stale data: last health check timestamp.
- Audit log (/ops/audit)
  - view: login, export, credential changes, approvals.
  - filter: event type, user, time range.
  - drill: event detail.
  - export/share: export audit log (CSV/PDF).
  - no data: "No audit events yet" state.
  - stale data: last audit refresh timestamp.

### Enterprise

- Agency portfolio (/agency/portfolio)
  - view: aggregate KPIs across managed tenants (no drill-through).
  - filter: time range, agency.
  - drill: tenant summary (aggregate only).
  - export/share: PDF-only export.
  - no data: "No managed tenants" state.
  - stale data: snapshot timestamp with stale banner.
- Managed tenants (/agency/tenants)
  - view: tenant list, entitlements, branding.
  - filter: plan, status.
  - drill: tenant settings, audit events.
  - export/share: export entitlements summary.
  - no data: "No tenants" state.
  - stale data: last updated timestamp.
- Approvals queue (/approvals)
  - view: drafts awaiting review, status, due dates.
  - filter: status, owner, due date.
  - drill: approval detail, comments.
  - export/share: share approval link.
  - no data: "No pending approvals" state.
  - stale data: last updated timestamp on items.
- Approval detail (/approvals/:id)
  - view: draft content, comments, approval history.
  - filter: n/a.
  - drill: approve/reject, open source dashboard/report/budget.
  - export/share: export decision summary.
  - no data: "Approval not found" state.
  - stale data: last updated timestamp.
- Board packs (/board-packs)
  - view: schedules, templates, last generated time.
  - filter: client, cadence.
  - drill: generate now, history.
  - export/share: PDF export with watermark.
  - no data: "No board packs configured" state.
  - stale data: last generated timestamp.
- Board pack detail (/board-packs/:id)
  - view: pack configuration, recipients, history.
  - filter: delivery status.
  - drill: regenerate, edit schedule.
  - export/share: PDF export with watermark.
  - no data: "Board pack not found" state.
  - stale data: last generated timestamp.
- Impersonation console (/support/impersonate)
  - view: consent requests, active sessions, audit notes.
  - filter: requester, status.
  - drill: start/stop session with reason capture.
  - export/share: export session log.
  - no data: "No active sessions" state.
  - stale data: session expiry timestamps.
- Access review (/access-review)
  - view: role bindings, attestations, review status.
  - filter: role, tenant, workspace.
  - drill: binding detail, export access list.
  - export/share: access review export.
  - no data: "No review cycles" state.
  - stale data: last review timestamp.
- Why denied (/why-denied)
  - view: explanation of denied action with required privilege.
  - filter: n/a.
  - drill: request access, view entitlements.
  - export/share: n/a.
  - no data: "No denial context" state.
  - stale data: timestamp of denial decision.

## B) Global UI Components

### MVP

- App shell: top nav, breadcrumbs, account pill, logout.
- Tenant switcher: searchable, keyboard-friendly, shows active tenant.
- Dataset toggle: demo vs live; persisted selection.
- Snapshot indicator: relative time, absolute tooltip, stale warning.
- Global filter bar: date presets/custom, channel multi-select, campaign search, clear all.
- Map metric selector: spend, impressions, clicks, conversions, ROAS.
- Layout controls: save layout, copy link.
- Theme toggle: light/dark.
- System feedback: toasts, skeleton loaders, error banners.

### Post-MVP

- Dashboard library cards: last viewed, owner, quick actions.
- Report builder blocks: narrative editor, widget picker, layout grid.
- Export dialogs: PDF/PNG/CSV options with watermark preview.
- Alert builder UI: metric thresholds, schedules, recipients.
- CSV upload wizard: mapping, validation preview, job status.
- Connector cards: status pill, schedule controls, run now.

### Enterprise

- Approval widgets: status pills, comment threads, embargo banners.
- Entitlement badges: plan tags, "why denied" inline cues.
- Step-up auth modal: MFA prompt with reason capture.
- Impersonation banners: session status + consent indicator.
- Board pack builder: template selector, watermark indicator.
- Audit log viewer: filterable event stream + export.

## C) Key User Actions

### MVP

- Authenticate, refresh session, log out.
- Switch tenant context; keep tenant label visible.
- Toggle demo/live data; handle adapter availability.
- Filter dashboards by date, channel, campaign, parish.
- Drill into campaign/creative detail; return to dashboard.
- Save layout and copy a shareable link.

### Post-MVP

- Connect data sources; test and schedule syncs.
- Upload CSVs; map columns, validate, monitor jobs.
- Build and export reports; schedule deliveries.
- Configure alerts and AI summaries; manage recipients.
- Edit budget plans; compare plan vs actual.

### Enterprise

- Approve/reject drafts and budget proposals.
- Generate and schedule board packs with watermarks.
- Use impersonation with consent and time-boxed sessions.
- Run access reviews; export attestations.
- Perform step-up auth for high-risk actions.

## D) Permissions/Roles

### MVP

- Tenant-scoped RBAC with role-aware navigation and disabled actions.
- Demo/live data toggle allowed for all roles; live data gated by adapters.
- Copy link available to all; exports gated by role/entitlement (Post-MVP).

### Post-MVP

- Workspace scoping on dashboards, reports, and alerts.
- Connector management limited to tenant admins/team leads.
- CSV uploads limited to entitled roles; high-risk actions logged.

### Enterprise

- Role catalog per UAC spec (platform, agency, client roles).
- Draft -> Review -> Publish enforced; approvals logged.
- Exports watermarked; CSV disabled unless entitled + step-up auth.
- Impersonation restricted to support/admin roles with consent.

## E) API Dependencies

### MVP

- Auth: POST /api/auth/login/, POST /api/auth/refresh/, GET /api/me/.
- Tenant switch: POST /api/auth/switch-tenant/.
- Password reset: POST /api/auth/password-reset/, POST /api/auth/password-reset/confirm/.
- Metrics: GET /api/metrics/combined/ or GET /api/dashboards/aggregate-snapshot/.
- Adapters: GET /api/adapters/.
- Health: GET /api/health/, /api/health/airbyte/, /api/health/dbt/, /api/timezone/.
- Geo: parish geometry endpoint or static GeoJSON.

### Post-MVP

- Airbyte connections: GET /api/airbyte/connections/, summary, lifecycle endpoints.
- Airbyte telemetry: GET /api/airbyte/telemetry/.
- CSV upload + jobs: upload, mapping, status endpoints.
- Reports: CRUD + export endpoints (PDF/PNG).
- Alerts: CRUD + delivery endpoints.
- Admin audit: audit log endpoints.

### Enterprise

- UAC: role bindings, entitlements, approvals workflow endpoints.
- Board packs: schedule + generate endpoints.
- Impersonation: consent + session endpoints.
- Access review: export endpoints.

### Contract artifacts (link index)

These files are the reference artifacts that should stay in lockstep with backend serializers/tests
and frontend types:

- API payload change log: `docs/project/api-contract-changelog.md`
- Aggregate snapshot contract:
  - Human-readable: `docs/project/api/aggregate_snapshot.md`
  - JSON schema: `docs/project/api/aggregate_snapshot.schema.json`
- Frontend-facing endpoint notes (JSON):
  - Tenant switch: `docs/api/tenant-switch.json`
  - Password reset: `docs/api/password-reset.json`
  - Airbyte connections: `docs/api/airbyte-connections.json`
  - Airbyte telemetry: `docs/api/airbyte-telemetry.json`
  - (Legacy) Aggregate snapshot example: `docs/api/aggregate-snapshot.json`

## F) Empty/Error/Loading States

### MVP

- Skeleton loaders for KPIs, charts, tables, maps.
- Clear empty states with actionable CTAs (refresh data, connect sources).
- Errors surfaced inline with retry and runbook links when applicable.
- Stale data banner with snapshot timestamp; warning tone on stale.

### Post-MVP

- Connector errors: distinguish stale vs misconfigured credentials.
- CSV validation errors: aggregated error tables + retry mapping.
- Report export failures: retry + audit event logging.
- Alert delivery failures: show reason and next retry time.

### Enterprise

- Approval blocks: embargo/blackout messaging with timestamps.
- Entitlement denied: "why denied" explanation with request access CTA.
- Step-up required: MFA modal and audit capture on cancel.
- Impersonation expired: banner and forced logout from session.

### Non-happy-path UX requirements (global)

All screens that call the API must consistently handle:

- **Unauthenticated (401)**: redirect to `/login` and preserve the intended destination.
- **Permission denied (403)**: show a clear “You don’t have access” message; in Enterprise, deep-link to `/why-denied` with required privilege context.
- **Not found (404)**: show a “not found” state with a safe navigation CTA back to the nearest parent list.
- **Missing integrations/adapters**: show “connect sources” guidance and/or allow demo mode when explicitly enabled.
- **Stale/partial data**: show snapshot timestamp and “stale” warning when freshness thresholds are exceeded; avoid rendering NaN/Infinity in derived metrics.
- **Failed syncs/exports**: surface error reasons, next retry time (when available), and link to the relevant runbook for triage.

## G) Analytics/Telemetry Events

### MVP

- Auth lifecycle: login success/failure, logout, token refresh errors.
- Tenant context: tenant switch, dataset toggle changes.
- Exploration: dashboard view, filter change, map metric change.
- Drill-through: campaign/creative detail opened.
- Sharing: copy link, save layout.

### Post-MVP

- Data ops: connector create/update, run now, pause/resume.
- CSV uploads: upload start/finish, validation errors.
- Reports: create/edit/export, schedule delivery.
- Alerts: create/edit/pause, delivery status.

### Enterprise

- Approvals: submitted, approved, rejected, comments added.
- Board packs: scheduled, generated, delivered.
- Security: step-up auth triggered, impersonation start/end.
- Access review: export generated, review completed.

## Frontend acceptance checklist

### MVP

- Login, tenant switch, and logout flow works end-to-end.
- Dashboards load live data by default; demo mode is opt-in only.
- Snapshot freshness banner shows relative + absolute timestamps and stale warnings.
- Filters (date, channel, campaign) update KPIs, charts, tables, map.
- Empty and error states render with retry actions across all dashboards.

### Post-MVP

- Data sources management shows status, schedules, run-now controls, and last sync timestamps.
- CSV upload wizard validates, maps, and reports job status with error handling.
- Report builder exports PDF/PNG with filters and timestamps applied.
- Alerts and AI summaries support create/edit/schedule flows.

### Enterprise

- Draft -> Review -> Publish workflow enforces role gates and records audit events.
- Board packs schedule, generate, watermark, and export successfully.
- Step-up auth and impersonation flows display required banners and logs.
- "Why denied" explanations surface when entitlement blocks an action.

### Review gate

- Spec reviewed by Lina (Frontend Architect) and Joel (Design System), with feedback merged.
