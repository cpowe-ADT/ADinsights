# Reporting Builder Backend Data Structure Audit

Created: 2026-06-15
Status: docs-only audit; no runtime code changed
Timezone baseline: America/Jamaica

Purpose: determine the safest backend-only implementation plan for the v1 reporting catalog registry
and `DashboardDefinition.layout` validation for `dashboard.v1`.

See also:

- `docs/project/reporting-builder-catalog-contract.md`
- `docs/project/reporting-builder-architecture-plan.md`
- `docs/project/dashthis-replacement-reporting-plan.md`
- `docs/project/integration-data-contract-matrix.md`
- `docs/workstreams.md`

## Executive Recommendation

Go for a backend-only implementation slice, but keep it intentionally narrow.

Implement a pure backend catalog/validator module and wire it into
`DashboardDefinitionSerializer.validate_layout()` only when `layout.schema_version == "dashboard.v1"`.
Do not validate legacy layouts. Do not validate `ReportDefinition.layout` yet. Do not compute
historical 90-day coverage yet.

The first implementation should prove:

- Existing saved dashboard templates still save and duplicate.
- New `dashboard.v1` configs are accepted only when they match the catalog contract.
- Invalid dataset/metric/dimension/widget/table/slot/coverage-policy combinations are rejected.
- Tenant scoping, privileges, and audit logging remain unchanged.

## Scope And Contract Advisory

Docs-only audit status:

- Scope: `PASS_SINGLE_SCOPE` because this audit only adds docs.
- Contract risk: `WARN_POSSIBLE_CONTRACT_CHANGE` because the recommended implementation will change
  serializer validation behavior for new `dashboard.v1` payloads.

Implementation status:

- First code slice can stay in `backend/`.
- Review route: Sofia primary, Andre backup, Raj for contract awareness. Bring Mira only if the
  implementation expands into schema migration, cross-module refactor, frontend, dbt, or integration
  changes.
- Required backend checks: `make backend-lint && make backend-test`.
- Contract preflight after implementation:
  `make adinsights-preflight PROMPT="Assess backend reporting catalog and dashboard.v1 validation"`.

## Existing Models

### `TenantMetricsSnapshot`

Source: `backend/analytics/models.py:216`

Current role:

- Stores one latest cached payload per `(tenant, source)`.
- Has `source`, `payload`, `generated_at`, timestamps, tenant manager, and `latest_for()`.
- Supports freshness with `is_fresh(ttl_seconds)`.

Audit finding:

- Good existing snapshot cache for current combined payloads.
- Not sufficient by itself for reporting-builder historical fallback because it stores one latest
  payload per source, not per dataset/account/page/date-range/report.
- Do not change this model in the first validation slice.

### `ReportDefinition`

Source: `backend/analytics/models.py:344`

Current role:

- Tenant-scoped report definition.
- Stores `filters` and `layout` as JSON.
- Has schedule fields: `schedule_enabled`, `schedule_cron`, `delivery_emails`,
  `last_scheduled_at`.
- Tracks `created_by`, `updated_by`, and timestamps.

Audit finding:

- This is the right future home for `report.v1`, but it should not be changed in the first backend
  slice.
- Current report exports depend on existing loose report definitions. Tightening report validation
  too early risks breaking the current report/export UI.

### `DashboardDefinition`

Source: `backend/analytics/models.py:392` and fields at `backend/analytics/models.py:446`

Current role:

- Tenant-scoped saved dashboard definition.
- Stores `template_key`, `filters`, `layout`, `default_metric`, active flag, ownership, timestamps.
- Existing `layout` is a free JSON field.
- Legacy template dashboards use simple shapes such as:
  `{"routeKind": "campaigns", "widgets": ["kpis", "trend", "campaign_table"]}`.

Audit finding:

- This is the right first model for `dashboard.v1`.
- No database migration is needed for the first slice because the existing `layout` JSON field can
  hold versioned configs.
- Validation must be opt-in by `schema_version`; legacy layouts without `schema_version` must pass.

### `ReportExportJob`

Source: `backend/analytics/models.py:496`

Current role:

- Tenant-scoped async report export job.
- Stores export format, status, artifact path, safe error message, metadata, completion timestamp.

Audit finding:

- Useful future place for generated report coverage metadata in `metadata`.
- Do not change export behavior in the first validation slice.

## Existing Serializers And Viewsets

### Serializer insertion point

Source: `backend/analytics/phase2_serializers.py:28`

Current role:

- `DashboardDefinitionSerializer` exposes `layout` directly.
- There is no custom `validate_layout()` or object-level validation.
- DRF/model choice validation already handles `template_key` and `default_metric`.

Recommended implementation:

- Add `backend/analytics/reporting_catalog.py` for registry data and pure validation helpers.
- Add `validate_layout()` to `DashboardDefinitionSerializer`.
- If `layout` is empty or has no `schema_version`, return it unchanged.
- If `layout.schema_version == "dashboard.v1"`, call the validator.
- If `schema_version` is present but unsupported, reject it.

Do not put validation in the model first. Serializer-layer validation keeps API behavior explicit and
avoids surprising internal creates such as default preset bootstrapping.

### Viewset behavior

Source: `backend/analytics/phase2_views.py:331`

Current role:

- `DashboardDefinitionViewSet` is tenant-scoped through `get_queryset()`.
- `perform_create()` and `perform_update()` set tenant/owner fields.
- Audit events are already emitted for create/update/delete.
- `duplicate()` directly creates a clone from an existing dashboard.

Audit finding:

- Create/update validation should occur through the serializer.
- Duplicate can safely bypass validation because the source dashboard was already persisted; this
  also preserves legacy dashboards. Later, if `dashboard.v1` migration exists, duplicate can re-run
  validation as a hardening step.
- Audit metadata is already redacted; keep unchanged.

### Default presets

Source: `backend/analytics/phase2_views.py:157`

Current role:

- `ensure_default_dashboard_presets()` creates legacy dashboards with non-versioned `layout`.

Implementation risk:

- If validation is applied to all layouts, this bootstrap path will break.
- Therefore validation must be `dashboard.v1` only.

## Existing Data/Freshness Structures

### Dataset status

Source: `backend/analytics/dataset_status.py:42`

Current behavior:

- Reports whether live warehouse data is enabled and why not.
- Reasons include `adapter_disabled`, `missing_snapshot`, `stale_snapshot`, `default_snapshot`, and
  `ready`.
- Uses `TenantMetricsSnapshot.latest_for(tenant, source="warehouse")`.

Audit finding:

- This is useful for current live-readiness UI.
- It is not the same as the reporting-builder coverage contract
  (`fresh`, `stale`, `partial`, `source_disconnected`, `missing_history`, `not_previously_synced`).
- First validation slice should only validate the string value of `coverage_policy`; do not attempt
  to compute coverage states yet.

### Warehouse coverage

Source: `backend/analytics/warehouse_metrics.py:83`, `backend/analytics/warehouse_metrics.py:658`,
and response assembly at `backend/analytics/warehouse_metrics.py:1147`.

Current behavior:

- `DatasetCoverage` tracks `start_date`, `end_date`, and `row_count`.
- Filtered warehouse metrics fetch coverage from `vw_campaign_daily`.
- Response includes `coverage.startDate`, `coverage.endDate`, and availability details.

Audit finding:

- There is a partial coverage foundation for paid warehouse metrics.
- It is not generic across `organic_facebook_page`, `content_ops`, `csv_upload`, or report snapshots.
- Do not make `dashboard.v1` validation depend on live warehouse coverage queries.
- Later slice should generalize coverage into a dataset/report coverage service.

### Snapshot generation and exports

Source: `backend/analytics/tasks.py`

Current behavior:

- `sync_metrics_snapshots` writes `TenantMetricsSnapshot(source="warehouse")`.
- Snapshot task logs row counts and stale state.
- Generic report exports use snapshot payloads and write artifact metadata.

Audit finding:

- Good operational base for current paid reporting.
- Not enough for deterministic historical report replay because generated report coverage metadata is
  not yet first-class in report definitions or export jobs.
- Defer report snapshot/coverage metadata until after dashboard validation.

## Existing Tests

Strong existing coverage:

- `backend/tests/test_phase2_api.py`
  - Report CRUD and export request.
  - Generic CSV/PDF/PNG export behavior.
  - Export download safety and tenant isolation.
  - Dashboard library/default preset bootstrap.
  - Dashboard CRUD/duplicate/recent/audit events at `backend/tests/test_phase2_api.py:463`.
  - Dashboard edit privilege check.
- `backend/analytics/tests/test_phase2_views.py`
  - Recent dashboards auth/empty/limit/tenant isolation.
  - Meta Page Insights saved dashboard CRUD.
  - Report schedule fields and toggle action.
- `backend/tests/test_metrics_api.py`
  - Dataset status: adapter disabled, missing snapshot, stale snapshot, default snapshot, ready.
  - Combined metrics snapshot behavior and payload shape.
- `backend/tests/test_snapshot_task.py`
  - Snapshot generation, freshness, row counts, stale logging.
- `backend/tests/test_metrics_upload_api.py`
  - Upload snapshot fallback path.

Recommended tests to add:

- New pure validator tests: `backend/tests/test_reporting_catalog.py`.
- Serializer/API tests in `backend/tests/test_phase2_api.py` or
  `backend/analytics/tests/test_phase2_views.py` for DRF error shape and legacy compatibility.

## Recommended Backend File/Module Layout

First slice:

- `backend/analytics/reporting_catalog.py`
  - Dataclasses or frozen dictionaries for datasets, metrics, dimensions, widget types, coverage
    policies.
  - Pure helper functions:
    - `get_reporting_catalog()`
    - `validate_dashboard_layout(layout: object) -> dict`
    - `is_dashboard_v1_layout(layout: object) -> bool`
  - Custom exception or return structure that serializer converts into DRF `ValidationError`.

- `backend/analytics/phase2_serializers.py`
  - Add `validate_layout()` on `DashboardDefinitionSerializer`.
  - Keep `ReportDefinitionSerializer` unchanged.

- Tests:
  - `backend/tests/test_reporting_catalog.py`
  - Extend `backend/tests/test_phase2_api.py` dashboard CRUD tests for one valid `dashboard.v1`
    create and representative invalid creates.

No model migration is required.

## Validation Rules To Implement First

Implement these in the first backend slice:

1. `layout` must be a JSON object when provided.
2. Missing `schema_version` means legacy layout; pass unchanged.
3. `schema_version == "dashboard.v1"` enables strict validation.
4. Unsupported `schema_version` is rejected.
5. `widgets` must be a non-empty list for `dashboard.v1`.
6. Each widget must have unique `id`, valid `type`, valid `dataset`, and valid `coverage_policy`
   when provided.
7. Each metric must exist and be valid for the widget dataset.
8. Each dimension must exist and be valid for the widget dataset.
9. Widget type rules:
   - `line_chart` requires time x dimension: `date`, `week`, or `month`.
   - `data_table` requires `visual.row_limit` or equivalent `row_limit`.
   - `map` requires `region` or `parish` and only active v1 paid dataset support.
   - `scatter_chart` is rejected for v1 user payloads.
10. Slot validation:
    - `layout.slots` is optional.
    - If present, each slot must reference an existing `widget_id`.
    - Slot `cols` must be 1-12.
    - Slot `rows` must be positive and bounded.
11. Combined/source label rule:
    - `combined_social` remains future-gated and should be rejected.
    - `combined_paid_media` widgets grouped by platform/source must set `visual.source_labels=true`.
12. Page Insights metric rule:
    - Deprecated/unknown Page metrics from the catalog contract are rejected by product key. Do not
      dynamically parse the full generated Meta metric catalog in the first slice.

## Validation Rules To Defer

Defer these until after the first backend validation slice:

- `ReportDefinition.layout` validation for `report.v1`.
- A public `GET /api/reporting/catalog/` endpoint.
- Dynamic DB-backed catalog records.
- Full Meta Page metric registry integration.
- Real dataset coverage computation for `fresh`, `partial`, `source_disconnected`,
  `missing_history`, and `not_previously_synced`.
- Cross-object tenant validation for actual `client_id`, `ad_account`, `page_id`, `workspace_id`
  inside widget filters.
- Report export coverage metadata persistence.
- Frontend TypeScript catalog generation.
- Combined social blended metrics.
- Organic Instagram activation.
- Scatter chart UI/validation.

Reason: those require frontend, dbt, integrations, or runtime data access and should be split into
separate Raj/Mira-reviewed phases.

## Implementation Risks

### Backward compatibility

Risk: existing default presets and saved dashboards use non-versioned layout JSON.

Mitigation: validate only `schema_version == "dashboard.v1"`; pass legacy layouts unchanged.

### Frontend payload assumptions

Risk: the current frontend builder sends `layout` with `routeKind` and `widgets`, not
`dashboard.v1`.

Mitigation: do not require `schema_version` yet. Add backend validation before frontend migration.

### API contract changes

Risk: new validation changes POST/PATCH error behavior for users who send `dashboard.v1`.

Mitigation: document as additive validation for new schema only; update
`docs/project/api-contract-changelog.md` in the implementation PR.

### Tenant/client/account/page isolation

Risk: catalog validation can falsely imply tenant object references are validated.

Mitigation: first slice validates config shape and allowed keys only. Explicitly defer live
object-reference ownership checks.

### Historical fallback semantics

Risk: validating `coverage_policy` without coverage computation may be mistaken for completed
90-day fallback.

Mitigation: first slice only validates allowed policy values. Coverage computation remains a later
data/API slice.

## API Contract And Docs Updates Needed During Implementation

Required when backend validation is implemented:

- `docs/project/api-contract-changelog.md`
  - Add entry: `POST/PATCH /api/dashboards/` now validates `layout.schema_version=dashboard.v1`.
  - Clarify legacy layouts remain accepted.
- `docs/project/reporting-builder-catalog-contract.md`
  - Update only if implementation intentionally differs from this audit.
- `docs/ops/agent-activity-log.md`
  - Add implementation summary.

Not required in first backend slice:

- `docs/project/integration-data-contract-matrix.md`, unless implementation changes source fields,
  marts, connector mappings, or coverage semantics.
- `docs/orchestration.md`, unless background tasks or scheduling change.

## Reviewer Route By Persona

| Area                                  | Reviewer              | Why                                                                                      |
| ------------------------------------- | --------------------- | ---------------------------------------------------------------------------------------- |
| Backend serializer/catalog validation | Sofia + Andre         | Own `backend/analytics/`, metrics API compatibility, snapshots, and validation behavior. |
| Contract awareness                    | Raj                   | New validation affects dashboard API writes for `dashboard.v1`.                          |
| Architecture watch                    | Mira if scope expands | Needed only if the implementation becomes a broader schema/refactor or crosses folders.  |
| Frontend notification                 | Lina                  | Inform only; no frontend code in first slice.                                            |
| Data/freshness watch                  | Priya + Martin later  | Needed when historical coverage moves into dbt/marts.                                    |
| Ops/freshness watch                   | Omar + Hannah later   | Needed when fallback states become live alerts/runbooks.                                 |

## Final Go/No-Go

Go for implementation, with constraints:

- Backend-only.
- No model migration.
- No report layout validation yet.
- No public catalog endpoint yet.
- No historical fallback computation yet.
- Validate only `dashboard.v1` layouts.
- Preserve all legacy dashboard and report behavior.

Recommended implementation prompt:

```text
Implement the backend reporting catalog registry and dashboard.v1 validation for ADinsights.

Use:
- docs/project/reporting-builder-backend-data-structure-audit.md
- docs/project/reporting-builder-catalog-contract.md
- backend/analytics/models.py
- backend/analytics/phase2_serializers.py
- backend/analytics/phase2_views.py
- backend/tests/test_phase2_api.py

Scope:
- backend/ only.

Create:
- backend/analytics/reporting_catalog.py
- backend/tests/test_reporting_catalog.py

Modify:
- backend/analytics/phase2_serializers.py
- backend/tests/test_phase2_api.py only as needed for API-level validation tests
- docs/project/api-contract-changelog.md for the additive dashboard.v1 validation contract
- docs/ops/agent-activity-log.md

Requirements:
- Preserve legacy dashboard layouts with no schema_version.
- Validate only layout.schema_version == "dashboard.v1".
- Reject unsupported schema_version.
- Validate datasets, metrics, dimensions, widget types, row limits, slot references, coverage_policy,
  and source label requirements per docs/project/reporting-builder-catalog-contract.md.
- Keep DashboardDefinitionViewSet audit logging unchanged.
- Keep duplicate behavior backward-compatible.

Run:
- make backend-lint
- make backend-test
- make adinsights-preflight PROMPT="Assess backend reporting catalog and dashboard.v1 validation"
```
