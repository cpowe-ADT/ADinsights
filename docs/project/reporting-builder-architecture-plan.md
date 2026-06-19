# Reporting Builder Architecture Plan

Created: 2026-06-15 22:14 EST

Purpose: turn the DashThis replacement work into a SaaS-ready reporting builder plan. This is the operating brief for building custom dashboards, custom report pages, chart/table configuration, paid and organic Meta/Facebook/Instagram reporting, and future external-user support without creating an unsafe freeform reporting surface.

See also:

- `docs/project/reporting-builder-catalog-contract.md`
- `docs/project/reporting-builder-backend-data-structure-audit.md`
- `docs/project/dashthis-replacement-reporting-plan.md`
- `docs/project/evidence/dashthis-replacement/2026-06-15-email-attachment-review.md`
- `docs/design/dashthis-replacement-reporting-moodboard.md`
- `docs/project/integration-data-contract-matrix.md`
- `docs/project/api-contract-changelog.md`
- `docs/project/meta-page-insights-data-dictionary.md`
- `docs/project/meta-page-insights-metric-catalog.md`
- `docs/runbooks/meta-page-insights-operations.md`

## Parsed Intent

The product goal is bigger than replacing one DashThis subscription. The system should become a governed reporting product where an internal user, then later external client users, can:

- Build individual dashboards for one source or one business object, such as Meta Ads campaign performance, Facebook Page engagement, Instagram performance, or a single client.
- Build combined dashboards that show paid, organic, web, and search metrics together while keeping source labels clear.
- Choose common visualization types: KPI tiles, line charts, bar charts, stacked bars, donut charts, scatter plots, tables, maps, and report narrative sections.
- Compare different x/y combinations, such as date vs spend, campaign vs CTR, creative vs engagement rate, platform vs reach, post vs interactions, or parish vs spend.
- Export monthly reports that combine charts, tables, top-performing content, written summaries, work completed, and recommendations.
- Support tenant isolation, role-based permissions, audit trails, source freshness, and predictable data contracts before external users are invited.

The immediate proof target remains SLB-style monthly reporting because the Gmail/PDF audit showed that full parity is not paid ads alone. It requires paid Meta Ads, organic Facebook/Instagram/Page insights, top posts, content counts, recommendations, and narrative report pages.

## Existing Scaffolding

The repo already has a good foundation. The next build should extend these surfaces rather than create a second reporting stack.

| Area | Existing surface | Use in this plan |
| --- | --- | --- |
| Saved dashboards | `backend/analytics/models.py` `DashboardDefinition` with tenant, template, filters, layout, default metric, audit metadata | Upgrade `layout` into a versioned dashboard config schema. |
| Generic reports | `ReportDefinition`, `ReportExportJob`, report export endpoints, scheduled delivery fields | Use for monthly report definitions and PDF/CSV export jobs. |
| Dashboard builder UI | `frontend/src/routes/DashboardCreate.tsx` | Evolve from template/widget toggles to governed chart/table configuration. |
| Template registry | `frontend/src/lib/dashboardTemplates.ts` | Existing `SlotConfig` and slot kinds are the natural bridge to composable widgets. |
| Combined metrics | `backend/analytics/combined_metrics_service.py` and `platform_registry.py` | Keep for paid-media combined views; extend cautiously with source-labeled dataset semantics. |
| Meta Ads | `backend/adapters/meta_direct.py`, warehouse paths, combined metrics endpoint | Source for paid campaign, ad set, ad, creative, spend, clicks, reach, conversions, ROAS, CTR, CPC, CPM, CPA. |
| Facebook Page Insights | `backend/integrations/page_insights_views.py`, Page/Post insight models, metric registry, runbook | Source for organic Page/post engagement, views, reactions, actions, and top post tables. |
| Content Ops reporting | `backend/content_ops/metrics.py`, `backend/content_ops/exports.py` | Candidate source for organic publishing activity, content counts, and monthly work-completed sections. |
| Design direction | `docs/design/dashthis-replacement-reporting-moodboard.md` and `.html` | Visual system for dashboards and monthly report output. |

## Current Gaps

The current builder is useful but not yet a true custom reporting product.

- There is no backend-governed metric and dimension catalog that tells the UI which metrics, dimensions, filters, grains, and chart types are allowed together.
- `DashboardDefinition.layout` is a free JSON field. It is not yet a validated widget schema with versioning.
- The frontend builder is template-first: name, template, filters, default metric, selected widgets. It is not yet a reusable chart/table builder.
- Combined dashboards currently support paid platform semantics better than paid-plus-organic social semantics. Paid and organic metrics must stay explicitly labeled.
- Meta Ads, Facebook Page Insights, Instagram Insights, and Content Ops metrics live in different surfaces. The product needs a reporting semantic layer above those surfaces.
- Monthly reports need page-level structure: cover, overview, KPI page, paid ads page, organic page, top posts page, recommendations, appendix.
- SaaS readiness needs sharing, roles, audit, source freshness, export history, and permissions checks designed into the schema now.

## Core Architecture Decision

Do not build arbitrary SQL, arbitrary API calls, or a fully freeform dashboard editor first.

Build a governed semantic reporting layer:

1. `DatasetCatalog`: approved reportable datasets such as `paid_meta_ads`, `organic_facebook_page`, `organic_instagram`, `content_ops`, `combined_paid_media`, and later `combined_social`, `ga4_web`, `search_console`, and `csv_upload`.
2. `MetricCatalog`: approved metrics with labels, source, type, aggregation, formatting, supported grains, required scopes, freshness expectations, and compatibility rules.
3. `DimensionCatalog`: approved dimensions such as date, campaign, ad set, ad, creative, page, post, platform, placement, region/parish, client, and content type.
4. `WidgetDefinition` schema: validated widget config for chart/table/KPI/map/report-section widgets.
5. `DashboardDefinition.layout.schema_version`: versioned saved config so older dashboards can keep rendering after future schema changes.
6. Backend validation before save: reject invalid metric/dimension/chart/filter combinations and any cross-tenant references.

This gives users flexibility while keeping the product safe, testable, and explainable.

## Dashboard Config Schema V1

Target shape:

```json
{
  "schema_version": "dashboard.v1",
  "layout": {
    "columns": 12,
    "slots": [
      {
        "id": "slot_kpi_overview",
        "widget_id": "kpi_overview",
        "cols": 12,
        "rows": 1
      }
    ]
  },
  "widgets": [
    {
      "id": "kpi_overview",
      "type": "kpi",
      "dataset": "combined_social",
      "metrics": ["reach", "engagements", "spend"],
      "dimensions": [],
      "filters": {
        "date_range": "last_30d",
        "client_id": "optional-client-id"
      },
      "compare": {
        "mode": "previous_period"
      },
      "visual": {
        "title": "Social overview",
        "show_delta": true,
        "source_labels": true
      }
    }
  ]
}
```

Widget rules:

- `kpi`: one or more metrics, no x/y axis, optional comparison.
- `line_chart`: one x dimension, usually date, one or more y metrics, optional breakdown dimension.
- `bar_chart`: one categorical x dimension, one or more y metrics, optional stacked breakdown.
- `donut_chart`: one categorical dimension, one metric.
- `scatter_chart`: one x metric, one y metric, optional size metric and label dimension.
- `data_table`: explicit columns with dimension and metric keys, sorting, pagination, and row limits.
- `map`: one geography dimension and one numeric metric, only when geography coverage is known.
- `report_section`: title, narrative block, data-bound highlights, and optional recommendations.

## Dataset Families

Start narrow and label sources clearly.

| Dataset key | Product meaning | First use |
| --- | --- | --- |
| `paid_meta_ads` | Meta Ads paid media performance | SLB paid ads pages, campaign dashboards |
| `organic_facebook_page` | Facebook Page and post insights | SLB organic Facebook pages and top posts |
| `organic_instagram` | Instagram insights where available and approved | SLB Instagram pages after scope readiness |
| `content_ops` | Publishing activity, content counts, approvals, recommendations | Monthly work-completed report sections |
| `combined_paid_media` | Meta Ads + Google Ads paid media | Existing combined paid dashboard |
| `combined_social` | Approved paid + organic social rollups | Later, after metric semantics are documented |

Combined dashboards should either:

- Compose multiple source-specific widgets on one page, or
- Use a backend-approved blended dataset with documented metric definitions.

They should never silently add together incompatible metrics. For example, paid impressions, Page views, Instagram reach, and post interactions can sit in one dashboard, but each card must show its source unless a combined metric definition is explicitly approved.

## Historical Reporting And Disconnected Source Resilience

The reporting product must not depend on Facebook, Instagram, Google, or another upstream API being
online at report-render time. A temporary source outage, expired token, missing permission, or
paused connector should block fresh syncs, but it should not erase already-landed historical
reporting data.

Product requirement:

- A user should be able to generate a 90-day historical report from stored ADinsights data even when
  Meta/Facebook/Google is disconnected, as long as those 90 days were previously synced and retained.
- The report must clearly label the data coverage and freshness state: `fresh`, `stale`,
  `partial`, `source_disconnected`, `missing_history`, or `not_previously_synced`.
- The UI must distinguish "cannot fetch new data" from "cannot report on historical data." Those are
  different problems.

Architecture policy:

1. **Retain raw landed source rows** for audit/debug/backfill where allowed by policy and storage
   budget. Raw rows support reprocessing when dbt models or metric definitions change.
2. **Maintain normalized marts** for report queries. Dashboards and reports should read from
   warehouse/mart tables or stored snapshots, not from live provider APIs.
3. **Persist report-ready snapshots** for generated or scheduled reports. A completed report should
   be reproducible from the same data coverage even if the provider disconnects later.
4. **Store sync/data coverage metadata** per dataset, tenant, account/page, and date range:
   earliest retained date, latest successful sync date, row counts, source status, and freshness.
5. **Use historical fallback only when honest.** If a user asks for the last 90 days and ADinsights
   only has 47 retained days, the report should render the 47-day range with a visible coverage note
   or block generation based on template policy.
6. **Do not cache secrets or provider payloads that violate policy.** Historical retention is for
   aggregate or permitted reporting rows, not credentials, tokens, or user-level PII.

Suggested dataset status fields:

```json
{
  "dataset": "paid_meta_ads",
  "source_status": "source_disconnected",
  "freshness_status": "stale",
  "history_status": "available",
  "earliest_available_date": "2026-03-01",
  "latest_available_date": "2026-06-14",
  "last_successful_sync_at": "2026-06-15T06:04:00-05:00",
  "requested_start_date": "2026-03-17",
  "requested_end_date": "2026-06-15",
  "covered_start_date": "2026-03-17",
  "covered_end_date": "2026-06-14",
  "coverage_note": "Meta is disconnected. Report uses stored data through 2026-06-14."
}
```

Retention decision points:

- Raw source rows: keep long enough to rebuild marts and troubleshoot reporting differences.
- Aggregated marts: keep at least the reporting product window; recommended minimum is 13 months for
  month-over-month and quarter-over-quarter reporting.
- Report snapshots/artifacts: keep according to tenant/export retention policy and support needs.
- Sync telemetry and coverage logs: keep long enough to prove why a report was fresh, stale, or
  partial on a given date.

Consultant/reviewer route:

| Concern | Reviewer persona | Main question |
| --- | --- | --- |
| Source outage and backfill behavior | Maya + Leo | Can sync failures stop fresh pulls without corrupting stored history? |
| Warehouse retention and rebuilds | Priya + Martin | Can we regenerate 90-day/13-month reports from retained data? |
| Metrics API fallback semantics | Sofia + Andre | Does the API expose coverage/freshness without changing metric meaning? |
| Alerts and support diagnosis | Omar + Hannah | Will ops know source disconnected vs history unavailable vs stale mart? |
| UI trust and report labeling | Lina + Joel | Does the user understand what period is covered and what is stale? |
| Cross-stream architecture | Raj + Mira | Is the retention/fallback design consistent across ingestion, dbt, backend, frontend, and docs? |

## Metric And Dimension Compatibility

The first implementation should ship a small compatibility matrix and expand it intentionally.

| Visualization | Valid x | Valid y | Dataset examples |
| --- | --- | --- | --- |
| KPI tile | none | spend, reach, clicks, CTR, engagements, views, reactions | paid Meta, organic Page |
| Line chart | date | spend, reach, clicks, engagements, views | paid Meta, organic Page |
| Bar chart | campaign, platform, post, content type | spend, clicks, reach, interactions | paid Meta, organic Page, content ops |
| Donut chart | platform, placement, reaction type, content type | reach, interactions, post count | organic and combined dashboards |
| Scatter chart | CTR, CPC, engagement rate | conversions, clicks, interactions | paid creative and top content views |
| Data table | campaign, ad, creative, post, date | approved metrics by dataset | all datasets |
| Map | parish/region | spend, reach, conversions | paid Meta only until organic geo coverage exists |

## Phased Build Plan

### Phase 0: Product Audit And Decisions

Scope: `docs/`

Goal: decide exactly what the first reporting builder must support before runtime changes.

Tasks:

1. Pick the first proof target: recommended `SLB Monthly Social Report`.
2. Mark which report pages are required for cancellation parity and which are post-MVP.
3. Define v1 datasets: recommended `paid_meta_ads`, `organic_facebook_page`, and `content_ops`; defer `organic_instagram` unless required scopes/data are confirmed.
4. Define v1 widget types: KPI, line, bar, table, report section; defer drag-and-drop and scatter/map unless required for the proof.
5. Write the metric/dimension compatibility matrix.
6. Record source freshness expectations and missing-scope handling.
7. Confirm roles: admin/editor can create, analyst can view/export, viewer can view only.

Acceptance criteria:

- A v1 metric/dimension/widget matrix exists.
- SLB parity pages are mapped to datasets and widgets.
- No implementation starts without Raj/Mira review if backend/frontend/dbt/integration folders will be touched together.

### Phase 1: Reporting Catalog Contract

Scope: preferably `docs/` first, then a backend-only slice.

Goal: create the contract the UI and API will use.

Tasks:

1. Define `DatasetCatalog`, `MetricCatalog`, `DimensionCatalog`, and `WidgetDefinition` fields.
2. Expose the backend registry through `GET /api/dashboards/reporting-catalog/`.
3. Decide whether the catalog is static Python config, database-backed, or hybrid. Recommended v1: static backend registry plus generated docs.
4. Add validation rules for chart type, metric compatibility, dimensions, filters, date grain, row limits, and source labels.
5. Add data coverage and historical fallback states for each dataset so the builder knows whether a
   requested report can be rendered from stored history when a source is disconnected.

Acceptance criteria:

- Backend has one source of truth for approved reporting options.
- Frontend no longer hardcodes unsupported metric/chart combinations.
- Contract docs are updated before or with code.
- Historical reports can be classified as available, partial, or unavailable without calling the
  upstream provider at render time.

### Phase 2: Backend Dashboard Schema Validation

Scope: `backend/`

Goal: make saved dashboards reliable and future-compatible.

Tasks:

1. Add versioned validation for `DashboardDefinition.layout`.
2. Keep legacy template dashboards rendering.
3. Validate widget ids, slot ids, chart type, dataset, metrics, dimensions, filters, compare mode, and row limits.
4. Ensure all saved dashboard CRUD remains tenant-scoped and audit logged.
5. Add serializer tests for valid and invalid configs.

Acceptance criteria:

- Invalid widgets cannot be saved.
- Existing saved dashboard tests still pass.
- Audit log metadata remains redacted.
- No raw metric keys outside the catalog are accepted.

### Phase 3: Frontend Custom Builder

Scope: `frontend/`

Goal: make the UI build the validated schema instead of only toggling templates.

Tasks:

1. Add dataset selector.
2. Add chart/table type selector.
3. Add metric picker filtered by dataset and chart type.
4. Add x/y dimension controls only when relevant to the visualization.
5. Add filter controls for date range, client, account/page, platform, campaign, post, and content type.
6. Add preview using the same backend validation result.
7. Keep an approved-template path for fast starts.

Acceptance criteria:

- User can create at least one KPI, line chart, bar chart, and table widget.
- UI prevents invalid combinations before save.
- Backend still enforces the same rules.
- Mobile and desktop layouts do not overlap.

### Phase 4: SLB Monthly Report Template

Scope: likely `backend/`, `frontend/`, and `docs/`; treat as cross-stream implementation.

Goal: produce a real monthly report from the same widget/report schema.

Recommended pages:

1. Cover and reporting period.
2. Executive KPI summary.
3. Paid Meta Ads performance.
4. Organic Facebook/Page performance.
5. Instagram performance if scope/data is available.
6. Top posts/content table.
7. Work completed/content operations summary.
8. Recommendations and next actions.
9. Appendix/data notes.

Acceptance criteria:

- Report can be regenerated from live tenant data or demo fixtures.
- Each metric shows source and date coverage.
- Missing data produces a clear report note, not a blank or misleading chart.
- Export history records the generated artifact.

### Phase 5: Combined Dashboards

Scope: backend/frontend/dbt/integration contract-sensitive work.

Goal: safely support combined and individual dashboards.

Tasks:

1. Add source-labeled combined social widgets.
2. Define approved blended metrics only where semantics match.
3. Show freshness and missing-source states per widget.
4. Prevent unsupported paid/organic merges.
5. Add tests for source-label rendering and invalid blends.

Acceptance criteria:

- Users can place paid and organic widgets on one dashboard.
- Any true blended metric has a documented definition.
- The UI never implies that incompatible metrics are equivalent.

### Phase 6: SaaS Hardening

Scope: cross-stream; plan before implementation.

Goal: prepare for users outside the internal team and clients.

Tasks:

1. Sharing model: private, tenant-wide, client-scoped, role-scoped.
2. Permissions: create/edit/export/admin separated by privilege.
3. Audit: create, edit, duplicate, export, schedule, share, delete.
4. Quotas: max widgets, max rows, max scheduled reports, export throttles.
5. Versioning: dashboard schema migration and rollback.
6. Template library: internal templates, tenant templates, locked system templates.
7. Support/debug views: source freshness, last sync, missing scopes, row counts, export job status.

Acceptance criteria:

- External users cannot access cross-tenant dashboards, reports, clients, pages, or exports.
- Heavy report configs cannot create unbounded queries.
- Support can explain why data is missing without reading logs or exposing secrets.

## Testing Methodology

Run tests by folder according to `AGENTS.md`. For this reporting builder, add targeted checks:

- Backend unit tests: catalog validation, dashboard serializer validation, invalid metric/dimension/chart combos, tenant isolation, permissions, audit logging.
- Backend API tests: catalog endpoint shape, dashboard CRUD, duplicate, report export request, missing-scope responses.
- Frontend unit tests: builder state transitions, chart type picker, metric picker filtering, invalid-state messaging, save payload shape.
- Frontend visual tests: builder desktop/mobile layout, dashboard render, report preview, export history, long labels and table overflow.
- dbt tests when marts change: model run plus metric field tests for affected marts.
- Integration tests: Meta Ads and Page Insights missing credentials, expired OAuth, empty sync, stale data, partial source coverage.
- Export tests: PDF render page breaks, CSV headers, artifact history, failed export state.

Minimum command expectations by touched folder:

- Backend: `make backend-lint && make backend-test`
- Frontend: `make frontend-guardrails && make frontend-lint && make frontend-test && make frontend-build`
- Contract-sensitive work: `make adinsights-preflight PROMPT="Assess reporting builder schema and dashboard contract changes"`

## Debugging Methodology

Every reporting bug should be traced through the same path:

1. Tenant and role: confirm the user has the expected tenant and privilege.
2. Dashboard/report config: validate `schema_version`, widget ids, dataset, metric, dimension, filters, and compare mode.
3. Catalog compatibility: confirm the metric/dimension/chart combination is allowed.
4. Source readiness: check OAuth permissions, account/page mapping, client scoping, and sync status.
5. Data freshness: compare selected date range against last successful sync and mart freshness.
6. Historical coverage: confirm whether the requested date range exists in retained rows, marts, or
   report snapshots.
7. Query payload: inspect sanitized request/response shape without logging secrets or user-level data.
8. Renderer: confirm the widget renderer supports the validated config and coverage status.
9. Export: confirm the export job saw the same config and data coverage as preview.

Common failure classes to build explicit states for:

- Metric exists but is not valid for selected dataset.
- Dimension exists but is not valid for selected chart type.
- Organic metric requires a Meta Page permission that is missing.
- Instagram metric is requested before Instagram source readiness is approved.
- Combined widget has one source fresh and one source stale.
- Table request exceeds row limit.
- Date grain is unsupported by the selected source.
- Geography map requested without trustworthy geography coverage.
- User tries to save a dashboard scoped to another tenant/client.
- Source is disconnected but historical rows are available; UI incorrectly blocks the full report.
- Source is disconnected and historical rows are missing; UI incorrectly renders a complete-looking report.
- Requested range exceeds retained history; report lacks a partial-coverage note.

## Adversarial Plan

Before building each phase, run this review:

1. What can a user configure that would be misleading?
2. What can a user configure that would be too expensive?
3. What could leak another tenant, client, page, account, export, or report?
4. What can fail because Meta scopes, Page tasks, or Instagram availability are missing?
5. What chart would look valid but compare incompatible metrics?
6. What old dashboard would break if the schema changes?
7. What test proves the backend rejects invalid config even if the frontend is bypassed?
8. What debug state does support see when the widget cannot load?

## Scope And Contract Advisory

Docs-only planning status:

- Scope: PASS_SINGLE_SCOPE when limited to `docs/`.
- Contract risk: advisory only while no runtime contract changes are made.

Implementation status:

- Full builder implementation is cross-stream because it touches `backend/`, `frontend/`, and potentially `dbt/` or `integrations/`.
- Treat backend serializers/views/API schema, dbt marts, source schemas, and integration mappings as contract-sensitive.
- Bring in Raj for cross-stream integration review and Mira for architecture/schema review before code spans multiple top-level folders.
- Update `docs/project/api-contract-changelog.md` and `docs/project/integration-data-contract-matrix.md` when API or data contracts change.

## Better Prompts For The Next Work

Use these prompts as bounded agent tasks. They are designed to keep the work systematic.

### Prompt 1: Audit Existing Reporting Builder Architecture

```text
You are working in /Users/thristannewman/ADinsights.

Goal: audit the existing reporting/dashboard scaffolding and produce an implementation-ready gap list for the custom reporting builder.

Read:
- AGENTS.md
- docs/workstreams.md
- docs/project/reporting-builder-architecture-plan.md
- docs/project/dashthis-replacement-reporting-plan.md
- backend/analytics/models.py
- backend/analytics/phase2_serializers.py
- backend/analytics/phase2_views.py
- frontend/src/routes/DashboardCreate.tsx
- frontend/src/lib/dashboardTemplates.ts
- backend/integrations/page_insights_views.py

Output:
1. Existing surfaces we should reuse.
2. Gaps by backend/frontend/dbt/integrations/docs.
3. Contract-sensitive files.
4. Recommended first code slice that stays in one top-level folder.
5. Tests required before handoff.

Do not edit code in this audit task.
```

### Prompt 2: Define The Reporting Catalog Contract

```text
Goal: write the v1 DatasetCatalog, MetricCatalog, DimensionCatalog, and WidgetDefinition contract for custom dashboards.

Scope: docs/ only.

Create or update:
- docs/project/reporting-builder-catalog-contract.md
- docs/ops/doc-index.md
- docs/ops/agent-activity-log.md

Requirements:
- Include dataset keys for paid_meta_ads, organic_facebook_page, content_ops, combined_paid_media, and future combined_social.
- Include metric fields: key, label, dataset, type, aggregation, format, supported_grains, supported_dimensions, supported_widgets, required_permissions, freshness_source.
- Include widget schema examples for KPI, line chart, bar chart, table, and report section.
- Include invalid examples that must be rejected.
- Include historical coverage fields and fallback states for disconnected sources.
- Include acceptance criteria and tests for the future backend implementation.
```

### Prompt 2A: Design Historical Reporting Fallback

```text
Goal: design how ADinsights can generate 90-day and monthly reports from stored history when Meta,
Facebook, Instagram, Google, or another source is disconnected.

Scope: docs/ first. Do not change runtime code.

Read:
- docs/project/reporting-builder-architecture-plan.md
- docs/project/dashthis-replacement-reporting-plan.md
- docs/workstreams.md
- docs/project/integration-data-contract-matrix.md
- docs/runbooks/alerting.md
- docs/ops/data-quality-checklist.md

Use these consultant lenses:
- Maya/Leo: ingestion, retries, disconnected source behavior, backfill.
- Priya/Martin: raw retention, marts, rebuilds, source freshness.
- Sofia/Andre: metrics API, snapshots, coverage status, backward compatibility.
- Omar/Hannah: alerts, runbooks, support diagnosis.
- Lina/Joel: UI labels, stale/partial report states.
- Raj/Mira: cross-stream architecture and rollout sequence.

Produce:
1. Required retention windows for raw rows, marts, report snapshots, artifacts, and sync telemetry.
2. Dataset coverage status schema: fresh, stale, partial, source_disconnected, missing_history,
   not_previously_synced.
3. Rules for when a 90-day report can render, render with a warning, or must block.
4. UI copy rules for disconnected-but-historical data.
5. Backend/API acceptance criteria.
6. dbt/data quality tests needed.
7. Alerting and runbook updates.
8. Cross-stream implementation slices in safe order.

Guardrails:
- Preserve tenant isolation.
- Do not store or expose secrets.
- Do not expose user-level PII.
- Do not call live provider APIs at report-render time unless explicitly marked as a fresh-sync action.
```

### Prompt 3: Implement Backend Dashboard Config Validation

```text
Goal: add backend validation for DashboardDefinition.layout schema_version dashboard.v1.

Scope: backend/ only unless explicitly escalated.

Requirements:
- Preserve existing template dashboards.
- Add a backend reporting catalog registry or validation module.
- Validate widget ids, datasets, metrics, dimensions, chart types, filters, compare modes, row limits, and source label requirements.
- Add serializer/API tests for valid configs and rejected invalid configs.
- Keep tenant isolation, HasPrivilege, and audit logging intact.

Run:
- make backend-lint
- make backend-test
- make adinsights-preflight PROMPT="Assess backend reporting builder dashboard schema validation"
```

### Prompt 4: Build The Frontend Custom Widget Builder

```text
Goal: evolve DashboardCreate into a custom widget builder that produces dashboard.v1 layout configs.

Scope: frontend/ only if the backend contract already exists.

Requirements:
- Load reporting catalog from the backend or use a typed fixture if backend is not ready.
- Add dataset selector, visualization selector, metric picker, x/y controls, filters, preview, and validation messaging.
- Keep approved templates as quick-start presets.
- Prevent invalid combinations in the UI, but assume backend remains the source of truth.
- Add tests for builder state, save payload, invalid states, and mobile layout.

Run:
- make frontend-guardrails
- make frontend-lint
- make frontend-test
- make frontend-build
```

### Prompt 5: Build SLB Monthly Report Template

```text
Goal: build the first monthly report template using the same reporting schema as the custom dashboard builder.

Scope: cross-stream; stop for Raj/Mira review before editing backend+frontend together.

Report pages:
- Cover and date range
- Executive summary
- Paid Meta Ads performance
- Organic Facebook/Page performance
- Instagram section only if data/scopes are ready
- Top posts/content table
- Work completed/content operations
- Recommendations
- Appendix/data notes

Requirements:
- Every metric must show source and date coverage.
- Missing sources produce explicit report notes.
- Export history records generated artifacts.
- PDF and preview use the same data contract.
```

### Prompt 6: Add Combined Social Dashboard Semantics

```text
Goal: support combined dashboards with paid and organic widgets while preventing misleading metric blends.

Scope: backend/frontend/dbt/integrations likely cross-stream.

Requirements:
- Define which metrics are source-specific and which can be blended.
- Add source labels to combined widgets.
- Add freshness and missing-source states per widget.
- Reject unsupported blends in backend validation.
- Add tests for paid+organic side-by-side dashboards and invalid blends.
```

### Prompt 7: SaaS Hardening For External Users

```text
Goal: harden reporting builder for external client users.

Scope: planning first, then separate backend/frontend implementation slices.

Requirements:
- Define dashboard/report sharing modes: private, tenant-wide, client-scoped, role-scoped.
- Define privileges for create, edit, view, duplicate, export, schedule, and share.
- Add audit events for every reporting mutation and export.
- Define quotas for widgets, table rows, exports, scheduled reports, and preview requests.
- Add debug states for missing scopes, stale sources, empty syncs, and export failures.
- Prove tenant/client isolation with tests.
```

## Recommended Immediate Next Build

Do not start with drag-and-drop UI. Start with the reporting catalog contract and backend validation.

Recommended order:

1. Write the v1 catalog contract in `docs/`.
2. Implement backend catalog and dashboard config validation in `backend/`.
3. Update frontend builder to consume the catalog and produce valid `dashboard.v1` configs.
4. Build the SLB Monthly Report template on top of that same schema.
5. Expand to combined social only after source semantics and compatibility rules are documented.

This keeps the DashThis replacement work useful now while building the foundation for a real multi-user reporting product.
