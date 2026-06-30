# Report Builder — Handover & Continuation Guide

**Status:** Shipped to `main` and verified green (2026-06-25).
**Audience:** The next engineer/model picking up the config-driven report builder. Read this top-to-bottom before touching the code — it is written to be followed literally.

If anything here disagrees with the code, the code wins — but tell the user, don't silently "fix" the doc.

---

## 1. TL;DR — what exists right now

Two features were built this session and merged to `main`:

| PR                                                       | What                                                                                                                                                          | Merge commit |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| [#400](https://github.com/cpowe-ADT/ADinsights/pull/400) | Config-driven report builder: render-from-config grid, drag-and-drop editor, live-data binding, per-widget config panel, tenant/user-scoped saved-layouts API | `f0772d20`   |
| [#399](https://github.com/cpowe-ADT/ADinsights/pull/399) | SLB Meta **organic** engagement via Graph object edges (no `read_insights`)                                                                                   | `3a5ce449`   |

**Live routes:**

- `/reports/:reportId/builder` → governed report-scoped builder seeded from `POST /api/reports/{id}/preview/` plus the backend reporting catalog, linked from Report Detail as **Customize layout**.
- `/reports/:reportId` → client-facing Report Detail consumes any saved `report-<id>` layout, rebinds it to the current governed preview values, and appends missing governed preview widgets below stale saved layouts before rendering.
- `/dashboards/report-preview` → legacy dashboard-store preview; click **Edit layout** to drag/resize/add/remove/configure widgets.
- `POST /api/reports/{id}/exports/` PDF/PNG → uses the requester/shared saved `report-<id>` grid layout when present, appending any missing governed preview widgets below stale saved grids. The data still comes from the queued governed `report.v1` snapshot. CSV keeps the governed snapshot row shape for auditability.

**Verified on merged `main` (2026-06-25):** `ruff` clean · full backend `pytest` exit 0 · ESLint clean · frontend `vitest` 944/944 · `npm run build` green · `makemigrations --check` no drift.

---

## 2. Mental model — a report is DATA

The whole system rests on one idea: **a report layout is a JSON object, not code.** One object describes the whole report; one component renders it read-only; one editor mutates the same object. Because the view and the editor share the exact same config, they can never drift.

```
DashboardLayoutConfig  ──renders──▶  <GridCanvas>      (read-only view)
        │  same object
        └────mutates────────────────▶  <LayoutEditor>   (drag/resize/add/remove/configure)
```

The config shape (`layoutSchema.ts`):

```ts
DashboardLayoutConfig = {
  id: string;            // stable id, e.g. "live-dashboard"
  title: string;
  cols: number;          // grid columns (default 12)
  rowHeight: number;     // px per row unit (default 64)
  widgets: DashboardWidget[];
}

DashboardWidget = {
  id: string;
  type: 'kpi' | 'bar' | 'line' | 'pie' | 'gauge' | 'table' | 'note';
  title?: string;
  x: number; y: number;  // 1-based grid position
  w: number; h: number;  // span in columns / rows
  dataKey?: string;      // binds to live store data, e.g. "summary.totalSpend"
  data?: unknown;        // static fallback data if no dataKey/resolver
  options?: WidgetOptions; // format, currency, max, unit, columns, text, …
  source?: WidgetSourceBinding; // governed dataset/widget/metric binding + runtime availability
}
```

---

## 3. File map (`frontend/src/components/report-layout/`)

Everything is dependency-free (no `react-grid-layout`) — deliberately, to keep the lockfile/CI clean. Pointer events do the drag/resize.

| File                      | Responsibility                                                                                                                                                                                         |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `layoutSchema.ts`         | Types + `isDashboardLayoutConfig()` validator + `DEFAULT_GRID_COLS`/`DEFAULT_ROW_HEIGHT`, including optional `source` metadata for governed dataset/widget/metric availability. **Start here.**        |
| `GridCanvas.tsx`          | Renders a config to a CSS grid (read-only). `resolveData?` prop binds live data.                                                                                                                       |
| `WidgetRenderer.tsx`      | Maps one `widget.type` → the matching viz-kit component (`KpiTile`, `DistributionBar`, `TrendLine`, `PieComposition`, `GaugeRing`, `VizDataTable`). **This is the switchboard.**                       |
| `LayoutEditor.tsx`        | Drag-and-drop editor over the config. Palette to add, ⠿ to move, corner to resize, ⚙ to configure, × to remove. Calls `onChange`/`onSave`.                                                             |
| `gridMath.ts`             | Pure functions: px↔grid-unit conversion, clamp move/resize, next free row. Fully unit-tested; no React.                                                                                                |
| `WidgetConfigPanel.tsx`   | The ⚙ inline form: edit title, type, `dataKey`, format/currency/unit/note.                                                                                                                             |
| `dataResolvers.ts`        | `createStoreResolver({summary, parish})` → resolves a widget's `dataKey` to real values. **This is the live-data bridge.**                                                                             |
| `reportPreviewAdapter.ts` | Converts governed `ReportPreviewResponse` pages/widgets into `DashboardLayoutConfig` for `/reports/:reportId/builder`; preserves missing metric values as `null` and turns blocked widgets into notes. |
| `layoutStorage.ts`        | localStorage read/write (`adinsights.report-layout.<id>`). The offline fallback.                                                                                                                       |
| `savedReportLayouts.ts`   | API client for the backend saved-layouts endpoint (list/get/create/update/delete + `is_shared` + `saveLayoutToApi` upsert).                                                                            |
| `sampleLayouts.ts`        | `liveDashboardLayout` (bound to live dataKeys) + `slbSampleLayout` (static demo).                                                                                                                      |
| `index.ts`                | Barrel. Import from here.                                                                                                                                                                              |
| `reportLayout.css`        | All grid + editor + config-panel styles (CSS vars with fallbacks).                                                                                                                                     |
| `__tests__/`              | 36 tests. Mirror these when you add features.                                                                                                                                                          |

Consumer route: `frontend/src/routes/ReportLayoutPreview.tsx` (wires report preview/catalog/data-availability or dashboard store data + API + edit toggle, plus report-scoped saved-layout selection, rename, delete, and tenant-share toggle). Registered in `frontend/src/router.tsx` as `/reports/:reportId/builder` and legacy dashboard child `report-preview`.

---

## 4. How live data binding works (READ before changing data flow)

There are now two data-binding modes:

1. Report builder mode (`/reports/:reportId/builder`) calls `getReport`, `previewReport`, `fetchReportingCatalog`, and `fetchReportDataAvailability`, then `reportPreviewToLayout(preview)` seeds the same layout config the canvas/editor mutate. The generated config id is `report-<reportId>` so saved layouts are report-scoped. Runtime availability annotates widget `source.availability`; `LayoutEditor` disables governed add-back for `permission_gated`/`unsupported` states and shows `available`/`no data`/`gated`/`unsupported` chips in the canvas and settings panel.
2. Report Detail mode (`/reports/:reportId`) looks for a saved layout with `config.id === report-<reportId>`. If found, it renders that layout but resolves each widget's `data` from a freshly generated layout for the current preview. It also appends any governed preview widgets missing from the saved layout below the custom grid, matching by widget id and source signature. This keeps user positioning/titles while avoiding stale saved metric values or hidden newly governed notes/metrics.
3. Export mode stores the same saved grid config in `ReportExportJob.metadata.report_layout` when a matching layout exists. Before storing, the backend appends any governed preview widgets missing from that saved config, using the same widget-id/source-signature rule as Report Detail and placing them below the custom grid. PDF/PNG render that augmented config through the `report_v1_snapshot` exporter template, but the values remain the already queued governed report snapshot. CSV remains the governed row snapshot so coverage/status evidence stays stable.
4. Legacy dashboard preview mode (`/dashboards/report-preview`) reads `summary` (campaign totals) and `parish` (per-parish rows) from `useDashboardStore` and calls `loadAll(tenantId)`.
5. Dashboard preview mode builds a resolver: `createStoreResolver({ summary, parish })`.
6. `GridCanvas`/`LayoutEditor` call `resolveData(widget)` per widget when a resolver exists. The resolver reads `widget.dataKey`:
   - `summary.<field>` → a number (or **`null`** if missing — never invented, never `0`).
   - `parish.<metric>` → `[{label, value}]` for bar/pie.
   - `parish.rows` → raw rows for tables.
   - no match → falls back to `widget.data`.

**Hard rule:** a missing metric resolves to `null`, which renders as "no data". Do **not** convert missing values to `0` — that fabricates performance numbers. (See constraints §6.)

---

## 5. Recipes (do exactly these)

### 5a. Add a new widget type

1. `layoutSchema.ts`: add `'line'` to the `WidgetType` union; add any new `WidgetOptions` fields.
2. `WidgetRenderer.tsx`: add a `case 'line':` that renders the viz-kit component. If no viz component exists, build it under `frontend/src/components/viz/` first (match the existing ones).
3. `GridCanvas.tsx`: if the type is self-titling (renders its own heading), add it to `SELF_TITLING`.
4. `LayoutEditor.tsx`: add it to `PALETTE` + give it `placeholderData`/`placeholderOptions`.
5. `WidgetConfigPanel.tsx`: expose any new options if user-editable.
6. Add a test in `__tests__/` mirroring `WidgetRenderer`/`LayoutEditor` patterns.

### 5b. Bind a widget to a new live field

- Pick a `dataKey` (`summary.<field>` or `parish.<metric>`). Make sure the store actually exposes that field (`useDashboardStore` → `campaign.data.summary` / `parish.data`). Extend `dataResolvers.ts` only if you need a new key _prefix_. Add a `dataResolvers.test.ts` case.

### 5c. Persisting layouts (already wired)

- `ReportLayoutPreview` hydrates from the API on mount (`listSavedLayouts`) and saves through it (`saveLayoutToApi`), with a localStorage fallback. To add a "my layouts" picker, list with `listSavedLayouts()` and `setLayout(row.config)` + set the `remoteId` ref so saves PATCH the right row.

---

## 6. HARD CONSTRAINTS — do not violate (these are user-set, non-negotiable)

- **Meta:** do **not** add the `read_insights` scope. Do **not** bump `META_GRAPH_API_VERSION`. Do **not** call live Meta during report preview/export. Live Meta calls are allowed **only** during OAuth, sync, the diagnostic probe, and backfill.
- **No invented data.** Never fabricate metrics; never convert a missing metric to `0`. Missing → `null` → "no data".
- **Tenant isolation.** Every tenant-scoped query filters by tenant; RLS (`SET app.tenant_id` per request) must never be weakened. The saved-layouts viewset stamps tenant + owner from the authenticated user, never from request body. Aggregate-only — no per-user/PII data.
- **Secrets/tokens.** Never print or log raw tokens. Only `.env.sample`/`.example` placeholders are committed.
- **Conventions.** Conventional commits (`feat(reporting):`, `fix(...)`, `docs(...)`, `chore(...)`). Commit messages end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. PR bodies end with the Claude Code generated-with line. Timezone `America/Jamaica`. No alternative frameworks (no FastAPI/Next.js). Don't remove health endpoints.
- **Background auto-committer:** this repo auto-commits AND pushes the working tree. Do work on a feature branch (not directly on `main`) and never leave secrets in the tree.

---

## 7. CI gates that fail non-obviously (I hit all four — you don't have to)

`npm run build` + `pytest` passing locally is **not** enough. Before pushing a PR:

1. **Contract guard** — adding/altering any `/api/...` endpoint requires an entry in `docs/project/api-contract-changelog.md` (Date/Endpoint/Change/Impact/Owner), or CI fails `ESCALATE_CONTRACT_CHANGE_REQUIRES_DOCS`. New endpoints → owner/reviewer **Raj**.
2. **detect-secrets** — any new flagged string (even a fake test password) drifts `.secrets.baseline`. Fix: `pip install detect-secrets==1.4.0`, then re-run the exact scan from `.github/workflows/secret-scan.yml` to regenerate the baseline and commit it. CI ignores `generated_at`, so only real findings matter.
3. **Prettier** (`scripts/ci/prettier_changed_check.sh`) — checks **every** file changed vs `main`, including `.md` and `.stories.tsx`. Run `npx prettier --check --ignore-unknown $(git diff --name-only origin/main..HEAD)` and `--write` failures. **Gotcha:** an unquoted `$(...)` file list can reformat unrelated working-tree files — verify against the true two-dot `origin/main..HEAD` set before committing.
4. **Frontend typecheck** — `npm run build` runs `tsc -p tsconfig.build.json`, which **type-checks `*.stories.tsx`** (excludes only tests). Local incremental `.tsbuildinfo` caching can hide errors CI catches; delete `*.tsbuildinfo` for a faithful repro. Stories type errors surface in the "Lighthouse dashboards smoke" → "Build frontend" job.

(Also captured in the project memory `project_ci_gates.md`.)

---

## 8. Commands

```bash
# Backend (from repo root)
ruff check backend
cd backend && PYTHONPATH=.. DJANGO_SETTINGS_MODULE=config.settings.test ./.venv/bin/pytest -q
cd backend && PYTHONPATH=.. DJANGO_SETTINGS_MODULE=config.settings.test ./.venv/bin/python manage.py makemigrations --check --dry-run

# Frontend (from frontend/)
npm run lint
npx vitest run                 # full suite
npm run build                  # tsc -p tsconfig.build.json && vite build

# Saved-layouts API (mounted under /api/analytics/)
GET/POST   /api/analytics/report-layouts/
GET/PATCH/PUT/DELETE  /api/analytics/report-layouts/{id}/
```

Backend model: `analytics.SavedReportLayout` (migration `0009_savedreportlayout`). ViewSet + serializer: `backend/analytics/report_layout_views.py`. Routed in `backend/analytics/urls.py`. Mirrors `GoogleAdsSavedView` — copy that pattern for any sibling persistence surface.

---

## 9. Suggested next steps (backlog)

Done after the original handover: report builder mode now lists report-scoped saved layouts (`config.id === report-<reportId>`), switches between them, renames the selected backend row, deletes the selected backend row while keeping a browser copy active, and toggles `is_shared` on the selected backend row so admins/users can publish a layout to the tenant. Report exports now persist a matching saved layout into `ReportExportJob.metadata.report_layout`; PDF/PNG render that saved grid layout when present, append missing governed widgets below stale saved grids, and fall back to the governed snapshot table when absent.

Ordered roughly by value. None are required; the shipped feature is complete and standalone.

1. **More widget types** — area/sparkline, a big-number-with-trend, a map widget reusing the parish Leaflet component.
2. **Export polish** — make the static Node renderer visually closer to the React `GridCanvas` for complex charts, while preserving the no-live-Meta-during-export constraint.
3. **Per-tenant default layout** — let an admin mark one shared layout as the tenant default.

---

## 10. The other merged work — SLB Meta organic (#399), brief pointer

If you touch SLB/Meta reporting: organic Page/Post engagement is now sourced from Graph **object edges** (`reactions.summary(true)`, `comments.summary(true)`, `shares`, `followers_count`) — which work with `pages_read_engagement` — instead of the `read_insights`-gated `/insights` endpoint. Real data, no faked values.

- Ingestion: `backend/integrations/meta_page_insights/engagement_edges.py` (`ingest_engagement_edges`, `fetch_page_follower_count`, `fetch_post_engagement`).
- Backfill command: `backend/analytics/management/commands/slb_backfill_meta_reporting.py`.
- Context docs: `docs/project/meta-reporting-data-path.md`, `docs/project/meta-reporting-roadmap.md`, `docs/project/meta-graph-v24-provider-key-audit.md`.
- Known truthful limitation: follower **history** (day-by-day deltas) isn't available without `read_insights`; the export surfaces this honestly rather than fabricating a series. Instagram is gated behind Meta App Review scopes (`DEFAULT_META_LOGIN_IGNORED_SCOPES`) — a review/config gate, not a code bug.
- 2026-06-26 follow-up: the SLB monthly template uses Page follows plus post reactions/comments/shares, marks gated organic reach/impression/click metrics through reporting-catalog `availability_state`, allows paid coverage gaps to export only as explicit warnings, and adds `import_meta_organic_csv` for approved aggregate Meta UI/export values when manual reach/impression fallback is required. Later the same day, SLB gained an explicit warning-only export policy so missing organic Facebook/Page, organic post, and Content Ops history can render as visible warnings; the local fixed target generated non-empty CSV/PDF/PNG plus a sanitized dry-run. Parity still needs real DashThis/source values.
- 2026-06-26 truthfulness correction: the local fixed target must be scoped to the SLB paid account before export evidence counts. An account-scope recheck pinned `account_id=act_791712443035541`, blocked unscoped SLB paid widgets, and superseded the earlier export-ready local bundle because the retained May paid rows were not SLB rows. Follow-up made selected-account paid `missing_history`/`not_previously_synced` warning-only for SLB exports, so current fixed-target CSV/PDF/PNG artifacts are non-empty but paid values remain no-data until scoped SLB rows are backfilled or manually imported.
- 2026-06-26 readiness UI follow-up: `GET /api/reports/data-availability/` can now return `paid_meta_ads.scope_diagnostic` with `credential_status`; the Reports page renders that guidance inside the SLB source availability card so operators see when the selected SLB ad account is missing a Meta credential and must be reconnected/backfilled instead of using unrelated tenant rows.
- 2026-06-26 evidence follow-up: `slb_report_export_evidence` and `slb_report_evidence_bundle` now include a compact `data_availability` summary, including successful warning-only runs. For the fixed SLB target, keep `data_availability.datasets.paid_meta_ads.scope_diagnostic.credential_status` in the evidence packet so reviewers see the selected SLB account is missing retained paid rows/credential and unrelated retained tenant rows were not substituted.
- 2026-06-26 validation follow-up: `slb_report_evidence_validate` now reads bundle `data_availability` when present and emits `data_availability_paid_credential` only when paid availability remains blocking. Warning-only selected-account no-data exports still require reviewer explanation and do not close paid parity until the SLB ad account is reconnected/backfilled or manually imported.
- 2026-06-26 retained-history follow-up: `slb_report_history_probe` now includes per-probe `data_availability` for `primary_month` and `retained_90_day`, so G2/G3 evidence preserves the selected paid account scope diagnostic and missing credential status for both date windows.
- 2026-06-26 diagnostics follow-up: SLB diagnostics `source_health` now includes redacted `report_scope.paid_meta_ads` with selected-scope row count, redacted credential status, backfill status, and a placeholder `slb_paid_meta_backfill` remediation action so G8 support evidence can name the paid reconnect/backfill task without leaking account IDs.
- 2026-06-26 paid fallback follow-up: `import_meta_paid_csv` can import approved daily Meta Ads UI/export rows for the selected SLB account into stored paid reporting rows when API backfill is blocked by missing credentials. It rejects multi-day aggregate rows, skips blank metric cells on update, and does not create ad accounts or call Meta. `slb_backfill_meta_reporting` now emits the redacted import template in `post_backfill_commands.manual_paid_csv_import` and `fallback_actions[].code=manual_meta_paid_csv_import` when paid API backfill is credential-blocked; paired `dry_run_command_template` / `manual_paid_csv_import_dry_run` values should be used before write-capable repair commands. Fixed-range `slb_backfill_meta_reporting --dispatch-mode dry-run` is plan-only: it emits `audit_event.status=skipped`, skips request audit creation, and reports organic engagement-edge enrichment as planned without calling Meta.
- 2026-06-26 report-builder follow-up: `/reports/:reportId/builder` now uses the real governed report preview/catalog as its seed, adds layout-schema `line` widgets backed by `TrendLine`, and Report Detail consumes saved `report-<id>` layouts while rebinding current preview data before the collapsed support/data-path/evidence diagnostics.
- 2026-06-27 report-detail follow-up: Report Detail now appends any missing governed preview widgets below a saved custom `report-<id>` layout, keyed by widget id and source signature, so stale custom layouts do not hide newly governed SLB notes or metrics.
- 2026-06-27 export follow-up: report.v1 export metadata now augments matching saved `report-<id>` layouts with any missing governed preview widgets before PDF/PNG rendering, using the same id/source-signature fallback as Report Detail and preserving null missing values instead of zeros.
- 2026-06-27 evidence follow-up: `slb_report_export_evidence` now attaches the same augmented saved-layout snapshot to its fixed-target CSV/PDF/PNG jobs and emits layout source/append-count evidence fields. `slb_report_evidence_bundle` preserves those fields in its export summary too, so G5/G7 bundled artifacts exercise the same governed PDF/PNG path as API exports.
- 2026-06-26 report-builder saved-layout UI follow-up: `/reports/:reportId/builder` now includes a report-scoped saved-layout selector plus rename/delete actions and an `is_shared` tenant-share toggle for backend `SavedReportLayout` rows. The route still keeps a browser copy after delete, preserves sharing state when saving the selected row, and filters out unrelated dashboard layouts.
- 2026-06-26 report-builder availability follow-up: `/reports/:reportId/builder` now fetches `GET /api/reports/data-availability/` from the saved report filters, annotates generated and older saved widgets through `source.availability`, surfaces metric-state chips in the editor/settings panel, and keeps permission-gated or unsupported governed widgets from being re-added as active metric widgets.
- 2026-06-28 report-builder metric-binding follow-up: `POST /api/reports/{id}/preview/` now includes additive widget `metrics`/`dimensions` arrays. The React adapter and backend saved-layout snapshot adapter use declared `metrics` for `source.metrics` before falling back to row inference, so table dimensions like `campaign`, `post`, and `content` stay display columns and do not affect source signatures, runtime availability chips, stale-layout append matching, or PDF/PNG saved-grid exports.
- 2026-06-28 report-detail UX follow-up: Report Detail keeps `report.v1` edit, layout, refresh, export, and delivery controls inside the collapsed operator-controls section so the first visible surface reads like a client monthly report. Non-`report.v1` reports still expose edit/refresh actions in the page header.

---

## 11. Where to look when context is unclear

1. `CLAUDE.md` (root) — project overview + guardrails.
2. `AGENTS.md` — authoritative guardrails, schedules, testing matrix.
3. `docs/project/api-contract-changelog.md` — every API payload change.
4. `docs/project/reporting-builder-architecture-plan.md` and siblings — earlier planning for this builder.
5. `docs/runbooks/` — Meta validation/operations runbooks.

Welcome aboard. Keep changes scoped, run the §7 gates locally, and never fabricate data.
