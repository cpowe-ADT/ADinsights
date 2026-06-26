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

**Live route:** `/dashboards/report-preview` → click **Edit layout** to drag/resize/add/remove/configure widgets.

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
  type: 'kpi' | 'bar' | 'pie' | 'gauge' | 'table' | 'note';
  title?: string;
  x: number; y: number;  // 1-based grid position
  w: number; h: number;  // span in columns / rows
  dataKey?: string;      // binds to live store data, e.g. "summary.totalSpend"
  data?: unknown;        // static fallback data if no dataKey/resolver
  options?: WidgetOptions; // format, currency, max, unit, columns, text, …
}
```

---

## 3. File map (`frontend/src/components/report-layout/`)

Everything is dependency-free (no `react-grid-layout`) — deliberately, to keep the lockfile/CI clean. Pointer events do the drag/resize.

| File                    | Responsibility                                                                                                                                                      |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `layoutSchema.ts`       | Types + `isDashboardLayoutConfig()` validator + `DEFAULT_GRID_COLS`/`DEFAULT_ROW_HEIGHT`. **Start here.**                                                           |
| `GridCanvas.tsx`        | Renders a config to a CSS grid (read-only). `resolveData?` prop binds live data.                                                                                    |
| `WidgetRenderer.tsx`    | Maps one `widget.type` → the matching viz-kit component (`KpiTile`, `DistributionBar`, `PieComposition`, `GaugeRing`, `VizDataTable`). **This is the switchboard.** |
| `LayoutEditor.tsx`      | Drag-and-drop editor over the config. Palette to add, ⠿ to move, corner to resize, ⚙ to configure, × to remove. Calls `onChange`/`onSave`.                          |
| `gridMath.ts`           | Pure functions: px↔grid-unit conversion, clamp move/resize, next free row. Fully unit-tested; no React.                                                             |
| `WidgetConfigPanel.tsx` | The ⚙ inline form: edit title, type, `dataKey`, format/currency/unit/note.                                                                                          |
| `dataResolvers.ts`      | `createStoreResolver({summary, parish})` → resolves a widget's `dataKey` to real values. **This is the live-data bridge.**                                          |
| `layoutStorage.ts`      | localStorage read/write (`adinsights.report-layout.<id>`). The offline fallback.                                                                                    |
| `savedReportLayouts.ts` | API client for the backend saved-layouts endpoint (list/get/create/update/delete + `saveLayoutToApi` upsert).                                                       |
| `sampleLayouts.ts`      | `liveDashboardLayout` (bound to live dataKeys) + `slbSampleLayout` (static demo).                                                                                   |
| `index.ts`              | Barrel. Import from here.                                                                                                                                           |
| `reportLayout.css`      | All grid + editor + config-panel styles (CSS vars with fallbacks).                                                                                                  |
| `__tests__/`            | 36 tests. Mirror these when you add features.                                                                                                                       |

Consumer route: `frontend/src/routes/ReportLayoutPreview.tsx` (wires store + API + edit toggle). Registered in `frontend/src/router.tsx` (`path: 'report-preview'`).

---

## 4. How live data binding works (READ before changing data flow)

1. `ReportLayoutPreview` reads `summary` (campaign totals) and `parish` (per-parish rows) from `useDashboardStore` and calls `loadAll(tenantId)`.
2. It builds a resolver: `createStoreResolver({ summary, parish })`.
3. `GridCanvas`/`LayoutEditor` call `resolveData(widget)` per widget. The resolver reads `widget.dataKey`:
   - `summary.<field>` → a number (or **`null`** if missing — never invented, never `0`).
   - `parish.<metric>` → `[{label, value}]` for bar/pie.
   - `parish.rows` → raw rows for tables.
   - no match → falls back to `widget.data`.

**Hard rule:** a missing metric resolves to `null`, which renders as "no data". Do **not** convert missing values to `0` — that fabricates performance numbers. (See constraints §6.)

---

## 5. Recipes (do exactly these)

### 5a. Add a new widget type (e.g. `line`)

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

## 9. Suggested next steps (backlog — not started)

Ordered roughly by value. None are required; the shipped feature is complete and standalone.

1. **Saved-layouts UI** — a picker to list/switch/rename/delete layouts (API already supports all of it; only the UI is missing). Currently the preview auto-loads the first layout whose `config.id` matches `liveDashboardLayout.id`.
2. **Share toggle** — surface `is_shared` in the editor so a user can publish a layout to their tenant.
3. **Wire into the real reports nav** — `/dashboards/report-preview` is currently a standalone route; promote it into the reporting section once the UX is signed off.
4. **More widget types** — line/area/sparkline, a big-number-with-trend, a map widget reusing the parish Leaflet component.
5. **Export** — render a saved layout to PDF/PNG for the existing report-export pipeline (respect the no-live-Meta-during-export constraint — use already-synced/aggregated data only).
6. **Per-tenant default layout** — let an admin mark one shared layout as the tenant default.

---

## 10. The other merged work — SLB Meta organic (#399), brief pointer

If you touch SLB/Meta reporting: organic Page/Post engagement is now sourced from Graph **object edges** (`reactions.summary(true)`, `comments.summary(true)`, `shares`, `followers_count`) — which work with `pages_read_engagement` — instead of the `read_insights`-gated `/insights` endpoint. Real data, no faked values.

- Ingestion: `backend/integrations/meta_page_insights/engagement_edges.py` (`ingest_engagement_edges`, `fetch_page_follower_count`, `fetch_post_engagement`).
- Backfill command: `backend/analytics/management/commands/slb_backfill_meta_reporting.py`.
- Context docs: `docs/project/meta-reporting-data-path.md`, `docs/project/meta-reporting-roadmap.md`, `docs/project/meta-graph-v24-provider-key-audit.md`.
- Known truthful limitation: follower **history** (day-by-day deltas) isn't available without `read_insights`; the export surfaces this honestly rather than fabricating a series. Instagram is gated behind Meta App Review scopes (`DEFAULT_META_LOGIN_IGNORED_SCOPES`) — a review/config gate, not a code bug.

---

## 11. Where to look when context is unclear

1. `CLAUDE.md` (root) — project overview + guardrails.
2. `AGENTS.md` — authoritative guardrails, schedules, testing matrix.
3. `docs/project/api-contract-changelog.md` — every API payload change.
4. `docs/project/reporting-builder-architecture-plan.md` and siblings — earlier planning for this builder.
5. `docs/runbooks/` — Meta validation/operations runbooks.

Welcome aboard. Keep changes scoped, run the §7 gates locally, and never fabricate data.
