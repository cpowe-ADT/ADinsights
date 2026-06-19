# G9 Safety Controls Proof: Permissions, Tenant Isolation, Audit, Quotas

Date: 2026-06-16
Timezone: America/Jamaica
Status: evidence protocol; G9 remains `evidence_pending` until fixed-range proof is captured.

## Purpose

Prove the SLB reporting path is safe enough for cancellation review by verifying that report
preview, diagnostics, exports, scheduled dry-runs, and parity evidence remain tenant-scoped,
permission-gated, audited, quota-limited, and aggregate-only.

This packet does not close G9 by itself. It defines the evidence future sessions must collect for
the fixed G1 SLB report/date range.

## Preconditions

- G0 Raj/Mira scope review is cleared or explicitly still pending.
- G1 fixed proof target is recorded: environment, tenant/client, report ID, account/Page scope, and
  date range.
- G2/G3 coverage proof identifies the active datasets and retained-history state.
- G4/G5 render/export proof identifies the preview hash and export job IDs under review.
- G7/G8 delivery and diagnostics proof identifies the scheduled dry-run job and diagnostics payload.

If any prerequisite is missing, record the missing item in the worksheet below and keep G9
`evidence_pending`.

## Safety Invariants

- Report data must be scoped to the authenticated user's tenant.
- Cross-tenant report IDs, export job IDs, client IDs, account IDs, and Page IDs must be rejected.
- Preview, diagnostics, export, scheduled dry-run, and parity evidence must use stored aggregate
  ADinsights data only.
- No provider tokens, OAuth secrets, raw provider payloads, emails, user-level engagement records,
  or unredacted recipient data may appear in API responses, logs, export metadata, parity output, or
  evidence files.
- Unsupported Instagram assumptions remain blocked in v1.
- Quota failures must return safe messages without stack traces, SQL, provider payloads, or secrets.

## Current Backend Controls To Verify

| Control | Existing path | Evidence to capture |
| --- | --- | --- |
| Report view/list/export history | `report_view` privilege | Allowed/blocked behavior by role for report retrieve and `GET /api/reports/{id}/exports/`. |
| Report preview and diagnostics | `report_preview` privilege | Allowed/blocked behavior for `POST /api/reports/{id}/preview/` and `GET /api/reports/{id}/diagnostics/`. |
| Report export | `report_export` privilege | Allowed/blocked behavior for `POST /api/reports/{id}/exports/`. |
| Report scheduling | `report_schedule` privilege | Allowed/blocked behavior for `POST /api/reports/{id}/scheduled-dry-run/` and schedule toggle. |
| Report edit/create/template | `report_edit` privilege | Allowed/blocked behavior for edits and SLB template creation. |
| Report delete | `report_delete` privilege | Delete blocked for non-delete roles; audited when allowed. |
| Preview quota | `REPORT_PREVIEW_CALLS_PER_HOUR = 120` | Local/staging quota test returns HTTP 429 with sanitized message after threshold. |
| Export quota | `REPORT_EXPORTS_PER_HOUR = 24` | Local/staging quota test returns HTTP 429 with sanitized message after threshold. |
| Scheduled dry-run quota | `REPORT_SCHEDULED_DRY_RUNS_PER_HOUR = 12` | Local/staging quota test returns HTTP 429 with sanitized message after threshold. |
| Tenant-scoped report querysets | `ReportDefinitionViewSet.get_queryset()` | Cross-tenant report ID cannot be retrieved, previewed, diagnosed, exported, scheduled, edited, or deleted. |
| Tenant-scoped export history | `report.export_jobs.filter(tenant_id=report.tenant_id)` | Cross-tenant export job is absent from report export history. |
| Parity evidence tenant context | `slb_report_parity_evidence` command uses report tenant context | Output contains only the target report tenant and aggregate rows. |
| Evidence bundle tenant context | `slb_report_evidence_bundle` command uses report tenant context | Output contains the target report/date range, sanitized preview/diagnostics/export summaries, and aggregate parity rows. |
| Parity comparator file boundary | `slb_report_parity_compare` command reads redacted local JSON files | Output computes deltas without live providers and redacts sensitive-looking source references. |

## Implementation Safety Audit: Preview/Export Data Boundary

Status: implementation evidence captured; fixed-target payload inspection still pending.

Audit date: 2026-06-16

Commands used:

```bash
rg -n "MetaDirect|Graph|requests\\.|httpx|urllib|facebook|provider|token|decrypt|access_token|page_token|secret|raw_payload|user_id|profile|email|permalink|message|comments|reactions|viewer|actor|live" \
  backend/analytics/reporting_catalog.py \
  backend/analytics/reporting_preview.py \
  backend/analytics/reporting_report_preview.py \
  backend/analytics/reporting_delivery.py \
  backend/analytics/reporting_templates.py \
  backend/analytics/phase2_views.py \
  backend/analytics/tasks.py \
  backend/analytics/management/commands/slb_report_parity_evidence.py \
  backend/analytics/management/commands/slb_report_evidence_bundle.py \
  backend/analytics/management/commands/slb_report_parity_compare.py \
  backend/tests/test_phase2_api.py \
  backend/tests/test_reporting_catalog.py

rg -n "MetaDirect|ENABLE_META_DIRECT|Graph|requests\\.|httpx|facebook|access_token|page_token|decrypt|token" \
  backend/analytics backend/content_ops backend/adapters backend/integrations
```

Findings:

| Area | Evidence | Result |
| --- | --- | --- |
| Widget preview provider boundary | `backend/analytics/reporting_preview.py` imports Django ORM models and reads `TenantMetricsSnapshot`, `MetaInsightPoint`, `MetaPostInsightPoint`, `MetaPage`, `AdAccount`, and Content Ops aggregate models. It does not import `httpx`, `requests`, Meta Graph clients, `MetaDirectAdapter`, token decryptors, or provider adapters. | Supports stored-data-only implementation claim. |
| Paid dataset preview | `_preview_paid_dataset` reads the latest stored warehouse/upload `TenantMetricsSnapshot` and builds coverage from the snapshot payload. | No live provider call found. |
| Organic Facebook/Page preview | `_preview_organic_page_dataset`, `_page_metric_rows`, and `_post_rows` read stored Page/Post Insight rows via ORM filters scoped by tenant/date/page. | No live provider call found. |
| Content Ops preview | `_preview_content_ops_dataset` reads stored `OrganicPostMetricSnapshot` rows and `PublishedPost` counts. | No live provider call found. |
| Report preview/snapshot | `backend/analytics/reporting_report_preview.py` builds `report.v1` previews by validating the layout and calling `build_widget_preview`; it stores coverage summary, blocking reasons, and preview hash. | No provider client import or token path found. |
| Export preflight | `build_report_export_metadata` builds a server-side `report_snapshot` before queueing export and blocks when coverage policy prevents export. | Supports preview/export consistency claim. |
| Scheduled dry-run | `backend/analytics/reporting_delivery.py` creates a dry-run `ReportExportJob` with sanitized `delivery_status`; it does not send email. | Supports no-client-send implementation claim; fixed runtime proof still required. |
| API redaction | `backend/analytics/phase2_views.py` audit events for diagnostics/export/dry-run use `metadata.redacted == true` or limited safe fields; enqueue failures store exception type, not exception message. | Supports sanitized operational metadata claim. |
| Export artifact safety | `backend/analytics/tasks.py` verifies `/exports/` path prefix, rooted path containment, and non-empty artifacts; CSV values with formula-leading characters are prefixed. | Supports artifact safety implementation claim. |
| Test coverage | `backend/tests/test_phase2_api.py` covers report preview, export metadata snapshot hash, diagnostics audit event, dry-run metadata, viewer export block, parity output placeholders/audit event, coverage-blocked export, sanitized enqueue failure, report action quotas, role separation, cross-tenant report rejection, export-history tenant filtering, redacted SLB workflow audit metadata, non-empty download, empty/cross-tenant download rejection, and path traversal rejection. | Supports implementation readiness, not fixed-runtime cancellation proof. |

Sensitive-data notes:

- Provider-capable modules exist elsewhere (`backend/integrations/*`, `backend/content_ops/facebook_graph.py`,
  `backend/adapters/meta_direct.py`), but the `report.v1` preview/export-preflight path inspected
  above does not import or call those provider clients.
- `_post_rows` internally selects stored post ID and stored post message while building organic
  post rows. Under the governed widget projection, valid report widgets project approved dimensions
  and metrics; raw provider payloads, comments, reaction identities, viewer identities, and tokens
  are not returned. Fixed-target G9 evidence must still inspect the actual SLB preview/export
  payloads to confirm no unexpected post text, raw provider fields, or recipient data appear.
- This audit does not prove the fixed SLB runtime target because G1 is still blocked. It reduces
  implementation risk only.

No-live-provider regression evidence:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_report_preview_export_dry_run_and_parity_do_not_call_live_providers
```

Result: `1 passed`.

The regression authenticates first, then blocks socket connections, `urllib.request.urlopen`,
`requests.sessions.Session.request`, and `httpx` client requests while executing:

- `POST /api/reports/{id}/preview/`
- `POST /api/reports/{id}/exports/`
- `POST /api/reports/{id}/scheduled-dry-run/`
- `backend/manage.py slb_report_parity_evidence`
- `backend/manage.py slb_report_evidence_bundle`
- `backend/manage.py slb_report_parity_compare`

The test also stubs the async export queue dispatch so it verifies report preview/export preflight,
scheduled dry-run metadata, and parity evidence generation, not renderer subprocess behavior. This
is executable implementation evidence that those report paths do not open live network/provider
connections. It still does not replace fixed-target runtime payload inspection or reviewer
clearance.

Combined evidence bundle regression evidence:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_slb_report_evidence_bundle_command_outputs_fixed_target_bundle \
  backend/tests/test_phase2_api.py::test_report_preview_export_diagnostics_dry_run_and_parity_outputs_are_redacted \
  backend/tests/test_phase2_api.py::test_report_preview_export_dry_run_and_parity_do_not_call_live_providers
```

Result: `3 passed`.

The regression verifies `slb_report_evidence_bundle` produces a redacted
`slb_evidence_bundle.v1` payload with preview, diagnostics, rendering summary, export summary, and
parity rows for the same custom date range. Export delivery metadata is reduced to safe status
fields, artifact evidence is represented as presence and byte count, and audit metadata stores only
date range, preview hash, parity row count, and `redacted`. This is implementation evidence only;
fixed-target G9 still requires runtime payload and artifact hygiene review.

Parity comparator regression evidence:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_slb_report_parity_compare_command_computes_deltas_and_blocks_missing_values \
  backend/tests/test_phase2_api.py::test_slb_report_parity_compare_command_does_not_call_live_providers
```

Result: `2 passed`.

The regression verifies `slb_report_parity_compare` reads only local JSON evidence files, computes
deltas and pass/fail/blocked outcomes, redacts sensitive-looking source references, and completes
while live network/provider calls are blocked. The broader reporting slice, `make backend-lint`,
and `make backend-test` also passed. This is implementation evidence only; fixed-target G9 still
requires runtime payload and evidence-file hygiene review.

Post-change validation also passed:

```bash
backend/.venv/bin/pytest -q backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py
make backend-lint
make backend-test
```

Post-regression gate:

```bash
backend/.venv/bin/pytest -q backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py
make backend-lint && make backend-test
```

Result: reporting slice passed; canonical backend gate passed.

## Permission Evidence Matrix

Record actual role names from the target environment. If the environment does not define the exact
viewer/editor/admin labels, replace them with the configured role or privilege set.

| Action | Required privilege | Viewer result | Analyst/editor result | Admin/result owner result | Evidence link or command output | Pass/fail |
| --- | --- | --- | --- | --- | --- | --- |
| Retrieve report | `report_view` | Local test: allowed (`200`) | Local test: not separately asserted | Admin fixture covered by existing report CRUD paths | `test_report_privileges_allow_viewer_read_but_block_export`; `test_report_privileges_separate_view_preview_export_edit_schedule_delete` | Implementation pass; runtime pending |
| List export history | `report_view` | Local test: allowed (`200`) | Local test: not separately asserted | Admin fixture covered by existing report CRUD paths | `test_report_privileges_separate_view_preview_export_edit_schedule_delete` | Implementation pass; runtime pending |
| Preview report | `report_preview` | Local test: blocked (`403`) | Local test: analyst allowed (`200`) | Admin fixture covered by preview tests | `test_report_privileges_separate_view_preview_export_edit_schedule_delete`; `test_report_preview_returns_ordered_report_v1_pages` | Implementation pass; runtime pending |
| View diagnostics | `report_preview` | Local test: blocked (`403`) | Local test: not separately asserted | Admin fixture covered by diagnostics test | `test_report_privileges_separate_view_preview_export_edit_schedule_delete`; `test_report_diagnostics_returns_aggregate_dataset_status` | Partial implementation pass; runtime pending |
| Create export | `report_export` | Local test: blocked (`403`) | Local test: analyst allowed (`201`) | Admin fixture covered by export tests | `test_report_privileges_allow_viewer_read_but_block_export`; `test_report_privileges_separate_view_preview_export_edit_schedule_delete` | Implementation pass; runtime pending |
| Scheduled dry-run | `report_schedule` | Local test: blocked (`403`) | Local test: analyst blocked (`403`) | Admin fixture covered by dry-run test | `test_report_privileges_separate_view_preview_export_edit_schedule_delete`; `test_scheduled_report_dry_run_creates_sanitized_export_evidence` | Implementation pass; runtime pending |
| Toggle schedule | `report_schedule` | Local test: blocked (`403`) | Local test: not separately asserted | Local test: admin allowed and audited (`200`) | `test_report_privileges_separate_view_preview_export_edit_schedule_delete`; `test_report_admin_schedule_and_delete_are_audited_with_redacted_metadata` | Implementation pass; runtime pending |
| Edit report | `report_edit` | Local test: blocked (`403`) | Local test: analyst allowed (`200`) | Admin fixture covered by CRUD paths | `test_report_privileges_separate_view_preview_export_edit_schedule_delete` | Implementation pass; runtime pending |
| Delete report | `report_delete` | Local test: blocked (`403`) | Local test: analyst blocked (`403`) | Local test: admin allowed and audited (`204`) | `test_report_privileges_separate_view_preview_export_edit_schedule_delete`; `test_report_admin_schedule_and_delete_are_audited_with_redacted_metadata` | Implementation pass; runtime pending |

Pass rule: unauthorized actions return 403 or an equivalent permission-denied response; authorized
actions remain tenant-scoped and audited where the runtime emits audit events.

Focused permission/audit test evidence:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_report_privileges_allow_viewer_read_but_block_export \
  backend/tests/test_phase2_api.py::test_report_privileges_separate_view_preview_export_edit_schedule_delete \
  backend/tests/test_phase2_api.py::test_report_admin_schedule_and_delete_are_audited_with_redacted_metadata
```

Result: `3 passed`.

Broader reporting slice after adding permission/audit regressions:

```bash
backend/.venv/bin/pytest -q backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py
```

Result: `64 passed`.

Post-change backend gate:

```bash
make backend-lint && make backend-test
```

Result: passed.

## Tenant Isolation Evidence Matrix

Use two tenants in local or staging evidence. Never use production credentials for destructive
checks. The expected result for cross-tenant object IDs is 403 or 404; record the actual status.

| Check | Request shape | Expected result | Actual result | Evidence | Pass/fail |
| --- | --- | --- | --- | --- | --- |
| Tenant B retrieves Tenant A report | `GET /api/reports/{tenant-a-report-id}/` | 403/404 | Local test: `404` | `test_report_actions_reject_cross_tenant_report_ids` | Implementation pass; runtime pending |
| Tenant B previews Tenant A report | `POST /api/reports/{tenant-a-report-id}/preview/` | 403/404 | Local test: `404` | `test_report_actions_reject_cross_tenant_report_ids` | Implementation pass; runtime pending |
| Tenant B diagnoses Tenant A report | `GET /api/reports/{tenant-a-report-id}/diagnostics/` | 403/404 | Local test: `404` | `test_report_actions_reject_cross_tenant_report_ids` | Implementation pass; runtime pending |
| Tenant B creates Tenant A export | `POST /api/reports/{tenant-a-report-id}/exports/` | 403/404 | Local test: `404` | `test_report_actions_reject_cross_tenant_report_ids` | Implementation pass; runtime pending |
| Tenant B dry-runs Tenant A report | `POST /api/reports/{tenant-a-report-id}/scheduled-dry-run/` | 403/404 | Local test: `404` | `test_report_actions_reject_cross_tenant_report_ids` | Implementation pass; runtime pending |
| Tenant B sees Tenant A export history | `GET /api/reports/{tenant-a-report-id}/exports/` | 403/404 or empty | Local test: `404`; mismatched-tenant export jobs on an accessible report are filtered out | `test_report_actions_reject_cross_tenant_report_ids`; `test_report_export_history_filters_mismatched_tenant_jobs` | Implementation pass; runtime pending |
| Cross-tenant client/account/page filter | preview payload with another tenant's IDs | 400/403/404 | Account preview covered locally; client/page fixed-target proof pending | `test_dashboard_widget_preview_rejects_cross_tenant_account_reference`; fixed report runtime still pending | Partial implementation pass; runtime pending |

Pass rule: no response may include another tenant's metrics, report layout, export metadata, export
artifact path, recipient data, or diagnostics details.

Focused report tenant-isolation test evidence:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_report_actions_reject_cross_tenant_report_ids \
  backend/tests/test_phase2_api.py::test_report_export_history_filters_mismatched_tenant_jobs
```

Result: `10 passed`.

Broader reporting slice after adding tenant-isolation regressions:

```bash
backend/.venv/bin/pytest -q backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py
```

Result: passed.

Post-change backend gate:

```bash
make backend-lint && make backend-test
```

Result: passed.

## Audit Event Evidence Matrix

Capture the audit event row or sanitized admin/API summary for each action. Evidence should include
the event action, tenant, actor type, resource type, resource ID, timestamp, and confirmation that
metadata is redacted.

| Action | Expected audit event | Required redaction proof | Actual evidence | Pass/fail |
| --- | --- | --- | --- | --- |
| Report created | `report_created` | `metadata.redacted == true` or fields list only | Local regression verifies metadata stores only sorted field names plus `redacted`, with no report title, description text, layout widget values, recipient email, token, or secret strings. | Implementation pass; runtime pending |
| Report updated | `report_updated` | `metadata.redacted == true` or fields list only | Local regression verifies metadata stores only sorted field names plus `redacted`, with no updated description text, layout widget values, recipient email, token, or secret strings. | Implementation pass; runtime pending |
| Report deleted | `report_deleted` | No layout/data payload | Local regression verifies metadata is only `{"fields": [], "redacted": true}` and does not include report layout data. | Implementation pass; runtime pending |
| Schedule toggled | `report_schedule_toggled` | No recipients/secrets | Local regression verifies metadata is only `{"schedule_enabled": true}` and does not include layout or recipient data. | Implementation pass; runtime pending |
| SLB template created | `report_template_created` | Template key and safe fields only | Local regression verifies keys are only `template_key`, `fields`, and `redacted`, with no layout, widget/page snapshot, rows, delivery email, token, or secret strings. | Implementation pass; runtime pending |
| Report previewed | `report_previewed` | Schema/export/hash only; no widget data | Local regression verifies keys are only `schema_version`, `export_ready`, `preview_hash`, and `redacted`, with no layout, widget/page snapshot, rows, delivery email, token, or secret strings. | Implementation pass; runtime pending |
| Diagnostics viewed | `report_diagnostics_viewed` | Schema/export readiness only | Local regression verifies keys are only `schema_version`, `export_ready`, and `redacted`, with no diagnostics payload, layout, widget/page snapshot, rows, delivery email, token, or secret strings. | Implementation pass; runtime pending |
| Export requested | `report_export_requested` | Format/report ID only | Local regression verifies keys are only `fields`, `report_id`, and `redacted`, with no export snapshot, rows, delivery email, token, or secret strings. | Implementation pass; runtime pending |
| Export blocked | `report_export_blocked` | Blocking reasons only; no raw rows | Local regression verifies keys are only `blocking_reasons`, `export_format`, and `redacted`, with no raw rows, delivery email, token, or secret strings. | Implementation pass; runtime pending |
| Scheduled dry-run requested | `report_scheduled_dry_run_requested` | Sanitized delivery status only | Local regression verifies keys are only `delivery_status`, `export_format`, `report_id`, and `redacted`, with no recipient email, layout, report snapshot, raw rows, token, or secret strings. | Implementation pass; runtime pending |
| Parity evidence generated | `report_parity_evidence_generated` | Date range/hash/row count only | Local regression verifies keys are only `start_date`, `end_date`, `preview_hash`, `row_count`, and `redacted`; parity output still leaves DashThis/source values blank for manual comparison. | Implementation pass; runtime pending |

Pass rule: audit metadata must not contain access tokens, provider responses, raw metrics rows,
emails, export file paths outside the safe artifact abstraction, or user-level data.

Local implementation audit evidence now covers generic report mutation redaction, schedule/delete
redaction, and the main SLB reporting workflow audit events:

- `test_report_create_update_audit_events_store_field_names_only` verifies `report_created` and
  `report_updated` store field names only, without report text, layout widget values, recipient
  emails, tokens, or secrets.
- `test_report_admin_schedule_and_delete_are_audited_with_redacted_metadata` verifies
  `report_schedule_toggled` stores only `{"schedule_enabled": true}` and `report_deleted` stores
  `{"fields": [], "redacted": true}`.
- The same test verifies the schedule/delete audit metadata does not include report layout data.
- `test_report_workflow_audit_events_store_only_redacted_metadata` verifies
  `report_template_created`, `report_previewed`, `report_diagnostics_viewed`,
  `report_export_requested`, `report_export_blocked`, and
  `report_scheduled_dry_run_requested` store only the approved redacted metadata shape.
- `test_slb_report_parity_evidence_command_outputs_manual_comparison_rows` verifies
  `report_parity_evidence_generated` stores only date range, preview hash, row count, and
  `redacted`.

Focused audit-redaction test evidence:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_report_create_update_audit_events_store_field_names_only \
  backend/tests/test_phase2_api.py::test_report_workflow_audit_events_store_only_redacted_metadata \
  backend/tests/test_phase2_api.py::test_slb_report_parity_evidence_command_outputs_manual_comparison_rows
```

Result: `3 passed`.

All listed audit-event rows now have local implementation redaction coverage. Fixed-target runtime
capture is still required before G9 can pass.

## Quota Evidence Matrix

Run quota checks only in local or staging. Do not hammer production. If cache state makes the
threshold hard to hit safely, use a focused automated test with a reduced test setting or monkeypatch
instead of manual API loops.

| Quota | Scope | Limit | Expected blocked response | Actual evidence | Pass/fail |
| --- | --- | --- | --- | --- | --- |
| Report preview | tenant + report + hour | 120/hour | HTTP 429, sanitized `Report preview quota exceeded` message | Local regression `test_report_actions_return_sanitized_quota_blocks` monkeypatches quota denial and verifies 429 response excludes traceback, SQL, `access_token`, and `secret`. Fixed-runtime quota exercise still pending. | Implementation pass; runtime pending |
| Report export | tenant + report + hour | 24/hour | HTTP 429, sanitized `Report export quota exceeded` message | Local regression `test_report_actions_return_sanitized_quota_blocks` monkeypatches quota denial and verifies 429 response excludes traceback, SQL, `access_token`, and `secret`. Fixed-runtime quota exercise still pending. | Implementation pass; runtime pending |
| Scheduled dry-run | tenant + report + hour | 12/hour | HTTP 429, sanitized `Scheduled report dry-run quota exceeded` message | Local regression `test_report_actions_return_sanitized_quota_blocks` monkeypatches quota denial and verifies 429 response excludes traceback, SQL, `access_token`, and `secret`. Fixed-runtime quota exercise still pending. | Implementation pass; runtime pending |

Pass rule: quota responses must not leak stack traces, cache keys, SQL, provider data, token
material, or raw report contents.

Focused test evidence:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_report_actions_return_sanitized_quota_blocks \
  backend/tests/test_phase2_api.py::test_report_preview_returns_ordered_report_v1_pages \
  backend/tests/test_phase2_api.py::test_report_v1_export_stores_preview_metadata \
  backend/tests/test_phase2_api.py::test_scheduled_report_dry_run_creates_sanitized_export_evidence \
  backend/tests/test_phase2_api.py::test_report_privileges_allow_viewer_read_but_block_export
```

Result: `7 passed`.

Broader reporting slice:

```bash
backend/.venv/bin/pytest -q backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py
```

Result: `62 passed`.

These tests strengthen implementation readiness for G9. They do not replace fixed-target runtime
quota evidence or reviewer clearance.

Post-change backend gate:

```bash
make backend-lint && make backend-test
```

Result: passed.

## Aggregate-Only And Redaction Evidence Matrix

Inspect the fixed-range preview, diagnostics, export metadata, dry-run metadata, and parity output.

| Surface | Must contain | Must not contain | Actual evidence | Pass/fail |
| --- | --- | --- | --- | --- |
| Report preview | Aggregate widget data, coverage, warnings, blocking reasons | User-level metrics, tokens, raw provider payloads | Local regression injects sensitive-looking values into report filters and delivery config, then verifies preview output excludes token, secret, raw payload, user/profile/viewer/actor IDs, delivery emails, and recipient strings. | Implementation pass; runtime pending |
| Diagnostics | Dataset status, retained range, row count, source label, export history summary | Tokens, secrets, raw rows, emails, recipient lists | Local regression injects sensitive-looking values into old export metadata and verifies diagnostics output does not echo token, secret, raw payload, user/profile/viewer/actor IDs, delivery emails, or recipient strings. | Implementation pass; runtime pending |
| Export metadata | `report_snapshot`, `preview_hash`, coverage summary, blocking reasons | Raw provider payloads, secrets, unsafe paths | Local regression verifies manual export metadata includes report snapshot data while excluding injected token, secret, raw payload, user/profile/viewer/actor IDs, delivery emails, and recipient strings. | Implementation pass; runtime pending |
| Scheduled dry-run metadata | `delivery_status.mode == "dry_run"`, sanitized status | Real send proof, recipient secrets, provider payloads | Local regression verifies scheduled dry-run metadata uses sanitized queued delivery status and excludes injected recipient emails, token, secret, raw payload, and user-level strings. | Implementation pass; runtime pending |
| Parity command output | Aggregate rows and comparison placeholders | User-level records, secrets, raw source payloads | Local regression verifies `slb_report_parity_evidence` output excludes injected token, secret, raw payload, delivery emails, recipient strings, and user-level identifiers. | Implementation pass; runtime pending |
| Evidence files | Safe IDs, summarized values, redacted notes | OAuth tokens, credentials, private emails, raw provider payloads | Local scan of `docs/project/evidence/dashthis-replacement/` found no high-signal credential patterns and no email-address matches. Broader keyword hits were placeholders, route examples, `.env.sample` references, and policy/checklist text. | Implementation pass; fixed-target artifact scan pending |

Pass rule: any sensitive or user-level field found here is a G9 failure and must become a code fix,
test, redaction patch, or explicit blocker before cancellation review.

Focused aggregate-output redaction test evidence:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_report_preview_export_diagnostics_dry_run_and_parity_outputs_are_redacted
```

Result: `1 passed`.

Broader reporting slice after aggregate-output redaction coverage:

```bash
backend/.venv/bin/pytest -q backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py
```

Result: passed.

Post-change backend gate:

```bash
make backend-lint && make backend-test
```

Result: passed.

Evidence-file hygiene scan:

```bash
rg -n -i "(bearer\s+[a-z0-9._~+/=-]{20,}|access_token\s*[:=]\s*['\"]?[a-z0-9._~+/=-]{20,}|refresh_token\s*[:=]\s*['\"]?[a-z0-9._~+/=-]{20,}|client_secret\s*[:=]\s*['\"]?[a-z0-9._~+/=-]{20,}|page_token\s*[:=]\s*['\"]?[a-z0-9._~+/=-]{20,}|EAAG[A-Za-z0-9]+|EAA[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|ya29\.[0-9A-Za-z_-]{20,}|-----BEGIN (RSA |OPENSSH |EC |PGP )?PRIVATE KEY-----)" \
  docs/project/evidence/dashthis-replacement

rg -n -i "[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}" \
  docs/project/evidence/dashthis-replacement
```

Result: no matches.

Broader keyword scan:

```bash
rg -n -i "(example\.com|@|secret-token-value|super-secret-value|raw-provider-payload|access_token|refresh_token|client_secret|page_token|private key|bearer|password|xox|akia|AIza|ya29|EAAG|artifact_path|/tmp/|/exports/|\.env)" \
  docs/project/evidence/dashthis-replacement
```

Result: reviewed matches were placeholders such as `<operator-token>`, route examples, `.env.sample`
references, and policy/checklist text. No real credential, private recipient email, raw provider
payload, or unsafe artifact path was found in the current evidence docs. Future fixed-target
screenshots, exports, and copied runtime snippets still need their own G9 scan before cancellation
review.

## Tests And Gates To Attach

Required before G9 can pass:

```bash
make backend-lint
make backend-test
make frontend-guardrails
make frontend-lint
make frontend-test
make frontend-build
make adinsights-preflight PROMPT="Assess SLB reporting permissions tenant isolation audit quotas aggregate-only safety"
```

If runtime evidence uses local stack flows, also attach:

```bash
scripts/dev-healthcheck.sh
```

If new backend/frontend behavior is added to close a safety gap, add or update focused tests for the
specific gap before rerunning the relevant gates.

## Reviewer Route

- Sofia: permission checks, tenant isolation, API response safety, and backend tests.
- Nina: secrets, artifact safety, redaction, export metadata, and evidence-file safety.
- Omar: operational quota behavior, blocked states, and support diagnosis clarity.
- Hannah: support/evidence wording and runbook clarity.
- Raj: cross-stream cancellation gate and any unresolved safety tradeoff.
- Mira: required if closing G9 needs architecture, schema, or cross-boundary changes.
- Lina/Joel: required only if frontend role-based action hiding or safety UI changes are made.

## G9 Pass Rules

G9 can move to `passed` only when all are true:

- Permission matrix has pass results for every report action used by the SLB flow.
- Cross-tenant report/export/client/account/page checks are rejected or empty as expected.
- Audit events exist for report preview, diagnostics, export request/block, scheduled dry-run,
  parity evidence generation, and report mutation actions, with safe redacted metadata.
- Preview/export/scheduled dry-run quotas are proven by tests or controlled staging/local evidence.
- Preview, diagnostics, export metadata, scheduled dry-run metadata, parity output, and evidence docs
  are aggregate-only and contain no secrets or user-level metrics.
- Backend/frontend gates pass, or any gate failure is recorded as a blocker.
- Sofia and Nina clear the safety evidence, with Raj involved for cancellation readiness.

Current decision: G9 is not passed. DashThis cancellation remains no-go.
