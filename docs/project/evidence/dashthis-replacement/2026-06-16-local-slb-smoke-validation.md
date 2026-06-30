# Local SLB Report Smoke Validation

Date: 2026-06-16
Timezone: America/Jamaica
Status: local-only smoke validation; not cancellation-review evidence.

## Purpose

Validate that the local backend can create an SLB `report.v1` template target and run the
aggregate-only parity evidence command after local setup. This proves the local workflow path is
callable, but it does not prove DashThis parity, stored production coverage, retained history,
exports, delivery, or hardening.

## Scope Boundary

This packet must not be used to close G1-G12.

Reasons:

- It uses local SQLite, not an approved staging/production-like target runtime.
- It uses a local smoke report, not an operator-confirmed SLB `ReportDefinition.id`.
- It has no DashThis/source comparison values.
- It does not prove May 2026 stored SLB coverage.
- It does not prove CSV/PDF/PNG exports or scheduled delivery.
- DashThis remains active/no-go.

## Local Backup

Before local DB mutation, the SQLite database was backed up to:

`artifacts/local-runtime-backups/backend-db-before-slb-smoke-20260616.sqlite3`

## Local Setup Actions

Applied local Content Ops migrations:

```bash
backend/.venv/bin/python backend/manage.py migrate content_ops
```

Result:

```text
Applying content_ops.0001_initial... OK
Applying content_ops.0002_contentexportartifact... OK
```

Created one local-only SLB report target using the governed template builder and serializer
validation.

Local smoke report:

| Field                  | Value                                              |
| ---------------------- | -------------------------------------------------- |
| Report ID              | `09c96ea9-a9e5-4283-aa29-401179ab05dc`             |
| Tenant prefix          | `7f9b2f19`                                         |
| Name                   | `LOCAL SMOKE - SLB Monthly Social Report May 2026` |
| Template key           | `slb_monthly_social_report`                        |
| Schema version         | `report.v1`                                        |
| Date range             | `2026-05-01` through `2026-05-31`                  |
| Client ID              | Empty local placeholder                            |
| Delivery               | Disabled                                           |
| Cancellation evidence? | No                                                 |

## Smoke Command

```bash
backend/.venv/bin/python backend/manage.py slb_report_parity_evidence \
  --report-id 09c96ea9-a9e5-4283-aa29-401179ab05dc \
  --start-date 2026-05-01 \
  --end-date 2026-05-31 \
  --format markdown
```

Initial run failed because the local smoke report used a non-UUID placeholder client ID. The local
record was corrected to use an empty client ID. This was a local setup issue, not cancellation
evidence.

Second run succeeded.

## Smoke Result

```text
Preview hash: ba2a9703c40b76f6f929c1a3ee999bf17dedea5ea30e452bee7ed1d9fdafdae4
Export ready: True
```

Aggregate-only rows were emitted for:

- `paid_meta_ads`: spend, reach, clicks.
- `organic_facebook_page`: page reach, page impressions, page engagements, page follows.
- `content_ops`: published posts, content items created.

Local ADinsights values were zero or empty. At the time of this smoke run, rows used the historical
`pending_dashthis_value` placeholder; the current command now emits the governed
`blocked_missing_dashthis_value` result for rows without DashThis/source comparison values.

## Extended Local Reporting-Ops Smoke

Additional local service-level checks were run against the same smoke report without starting a dev
server:

- `build_report_preview`
- `build_report_diagnostics`
- `build_report_export_metadata`
- direct local `ReportExportJob` creation for `csv`, `pdf`, and `png`
- direct `run_report_export_job`
- `create_scheduled_report_dry_run`

Results:

| Check                                     | Result                              | Notes                                                                                                                   |
| ----------------------------------------- | ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Report preview                            | Passed locally                      | Preview hash `ba2a9703c40b76f6f929c1a3ee999bf17dedea5ea30e452bee7ed1d9fdafdae4`; `export_ready=True`.                   |
| Coverage status summary                   | Local-only mixed state              | `fresh=3`, `stale=3`, `missing_history=4`; not cancellation-grade coverage.                                             |
| Diagnostics                               | Passed locally                      | Diagnostics returned the same preview hash and 3 dataset summaries.                                                     |
| Export metadata/snapshot                  | Passed locally                      | Snapshot included 8 ordered report pages and the same preview hash.                                                     |
| CSV export                                | Passed locally                      | Job `899a1037-6c63-4b8a-be8f-79b4920a3218` completed; artifact size was 63 bytes.                                       |
| PDF export before Chromium install        | Failed locally                      | Job `73b5a6fd-b8da-45a6-836a-2575d0812be1` failed with sanitized `CalledProcessError`.                                  |
| PNG export before Chromium install        | Failed locally                      | Job `3548bb3e-8e73-4a96-a6bb-a2a52ce58c7f` failed with sanitized `CalledProcessError`.                                  |
| Scheduled dry-run before Chromium install | Created, then failed render locally | Job `d27f5f0b-a317-4372-b22b-1fb570bb2231`; `delivery_status.mode=dry_run`; renderer failed before artifact completion. |

The local export task emitted warnings that `vw_dashboard_aggregate_snapshot` is missing and fell
back to default snapshot payloads. That reinforces that this is local workflow smoke only, not stored
SLB coverage proof.

Manual exporter check for the failed PDF/PNG path showed the concrete local dependency gap:

```text
Failed to launch chromium because executable doesn't exist at
/Users/thristannewman/Library/Caches/ms-playwright/chromium-1208/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing
```

Interpretation:

- CSV export can complete locally through the generic export path.
- PDF/PNG export and scheduled dry-run artifact rendering initially needed the Playwright Chromium
  runtime installed/configured locally before local artifact smoke could pass.
- G5 still needs staging/production-like CSV/PDF/PNG non-empty artifact evidence from the fixed G1
  target before DashThis cancellation review.

## Post-Chromium Local Export Smoke

Installed the missing local Playwright Chromium cache with:

```bash
npm --prefix integrations/exporter exec -- playwright-core install chromium
```

Then reran local PDF, PNG, and scheduled dry-run artifact generation with fresh job IDs.

| Check                 | Result         | Artifact proof                                                                                                               |
| --------------------- | -------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| PDF export            | Passed locally | Job `9a355a57-2573-4bbe-bc77-eb0f7a606117`; 62,136 bytes; `file` reports PDF document version 1.4.                           |
| PNG export            | Passed locally | Job `76f6a417-b101-4743-af90-507e9f2f9bc4`; 37,160 bytes; `file` reports PNG image data 1280 x 720.                          |
| Scheduled dry-run PDF | Passed locally | Job `b36d8529-d3b4-40d2-9963-26826967060c`; 62,136 bytes; `delivery_status.mode=dry_run`; `delivery_status.status=rendered`. |

All three post-install jobs preserved preview hash
`ba2a9703c40b76f6f929c1a3ee999bf17dedea5ea30e452bee7ed1d9fdafdae4`.

The export task still warned that `vw_dashboard_aggregate_snapshot` is missing and returned default
payloads. That means the local artifact smoke proves rendering mechanics only; it does not prove
stored SLB coverage or DashThis parity.

## Focused Backend Reporting Test Gate

Ran the focused backend reporting tests locally:

```bash
backend/.venv/bin/pytest -q backend/tests/test_reporting_catalog.py backend/tests/test_phase2_api.py
```

Result:

```text
59 passed
```

Covered implementation areas include:

- reporting catalog registry validation
- `dashboard.v1` validation
- `report.v1` validation
- SLB monthly template creation
- report preview
- diagnostics
- export metadata/report snapshots
- scheduled dry-run evidence creation
- parity command output
- report privileges and export download safety
- widget preview endpoint behavior

This is local implementation-gate evidence. It does not prove fixed SLB runtime data coverage,
DashThis/source parity values, staging/production export delivery, or hardening.

## Focused Frontend Reporting Test Gate

Ran the focused frontend reporting tests locally:

```bash
npm --prefix frontend test -- --run \
  src/lib/phase2Api.test.ts \
  src/routes/__tests__/DashboardCreate.test.tsx \
  src/routes/__tests__/SavedDashboardPage.test.tsx \
  src/routes/__tests__/ReportDetailPage.test.tsx \
  src/routes/__tests__/ReportsPage.test.tsx
```

Result:

```text
5 test files passed
40 tests passed
```

Covered implementation areas include:

- reporting catalog API client
- dashboard widget preview API client
- SLB monthly template API client
- catalog-driven `DashboardCreate`
- saved `dashboard.v1` rendering through governed previews
- `ReportsPage` SLB monthly report creation action
- `ReportDetailPage` `report.v1` preview rendering
- export snapshot/diagnostics display
- scheduled dry-run action
- blocked export UI state

This is local frontend implementation-gate evidence. It does not prove fixed SLB runtime data,
DashThis/source parity, real browser screenshots, responsive visual review, or cancellation
readiness.

## Frontend Build/Lint Gate

Ran the broader frontend implementation gates locally:

```bash
make frontend-guardrails
make frontend-lint
make frontend-build
```

Results:

| Gate                       | Result | Notes                                                              |
| -------------------------- | ------ | ------------------------------------------------------------------ |
| `make frontend-guardrails` | Passed | Reported `Frontend guardrail check passed.`                        |
| `make frontend-lint`       | Passed | ESLint completed with `--max-warnings=0`.                          |
| `make frontend-build`      | Passed | `tsc -p tsconfig.build.json && vite build` completed successfully. |

This supports frontend implementation readiness only. It does not prove fixed SLB runtime data,
real-browser screenshot review, DashThis/source parity, or cancellation readiness.

## Canonical Backend And Frontend Gates

Ran the broader backend/frontend implementation gates locally:

```bash
make backend-lint
make backend-test
make frontend-test
```

Results:

| Gate                 | Result | Notes                                                           |
| -------------------- | ------ | --------------------------------------------------------------- |
| `make backend-lint`  | Passed | Ruff completed with `All checks passed!`.                       |
| `make backend-test`  | Passed | Full backend pytest suite completed successfully.               |
| `make frontend-test` | Passed | Vitest reported `139 passed` test files and `893 passed` tests. |

The frontend test run emitted existing non-fatal console warnings from jsdom navigation, React
`act(...)` warnings, OAuth callback fallback warnings, and relative `/api/clients/` URL parsing in
tests. They did not fail the gate, but they should not be interpreted as browser UX proof.

This supports implementation readiness across backend and frontend. It still does not prove fixed
SLB runtime data coverage, retained history, real DashThis/source parity values, real browser
screenshots, or cancellation readiness.

## Release And Contract Prerequisite Gates

Ran additional local release-readiness checks:

```bash
backend/.venv/bin/python backend/manage.py backend_release_preflight
python3 infrastructure/airbyte/scripts/check_data_contracts.py
python3 infrastructure/airbyte/scripts/verify_observability_prereqs.py
python3 infrastructure/airbyte/scripts/verify_production_readiness.py
```

Results:

| Gate                              | Result | Notes                                                                                                                                                                                                                 |
| --------------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend_release_preflight`       | Passed | Local deterministic backend preflight returned `ok: true`; `/api/health/airbyte/` returned `502 sync_failed` and `/api/health/dbt/` returned `503 missing_run_results`, both within allowed local preflight statuses. |
| `check_data_contracts.py`         | Passed | Reported `Data-contract validation passed.`                                                                                                                                                                           |
| `verify_observability_prereqs.py` | Passed | Reported `Observability prerequisite validation passed.`                                                                                                                                                              |
| `verify_production_readiness.py`  | Failed | Still missing `AIRBYTE_TEMPLATE_META_METRICS_CONNECTION_ID` for bootstrap connection validation.                                                                                                                      |

This narrows the release warning surface: backend deterministic preflight, data-contract validation,
and observability prerequisites are green locally. Production readiness remains blocked by the
Airbyte template connection prerequisite, and none of these gates prove fixed SLB runtime data,
DashThis/source parity, or cancellation readiness.

## G9 Quota Regression Gate

Added and ran focused backend tests for sanitized report action quota blocks:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_report_actions_return_sanitized_quota_blocks \
  backend/tests/test_phase2_api.py::test_report_preview_returns_ordered_report_v1_pages \
  backend/tests/test_phase2_api.py::test_report_v1_export_stores_preview_metadata \
  backend/tests/test_phase2_api.py::test_scheduled_report_dry_run_creates_sanitized_export_evidence \
  backend/tests/test_phase2_api.py::test_report_privileges_allow_viewer_read_but_block_export
```

Result: `7 passed`.

Also reran:

```bash
backend/.venv/bin/pytest -q backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py
```

Result: `62 passed`.

This proves local implementation behavior for sanitized quota responses. It does not prove
fixed-target runtime quota behavior, tenant isolation, or cancellation readiness.

Post-change backend canonical gate:

```bash
make backend-lint && make backend-test
```

Result: passed.

## G9 Permission/Audit Regression Gate

Added and ran focused backend tests for report role separation and schedule/delete audit redaction:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_report_privileges_allow_viewer_read_but_block_export \
  backend/tests/test_phase2_api.py::test_report_privileges_separate_view_preview_export_edit_schedule_delete \
  backend/tests/test_phase2_api.py::test_report_admin_schedule_and_delete_are_audited_with_redacted_metadata
```

Result: `3 passed`.

Also reran:

```bash
backend/.venv/bin/pytest -q backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py
make backend-lint && make backend-test
```

Results: reporting slice `64 passed`; canonical backend gate passed.

This proves local implementation behavior for report privileges and schedule/delete audit metadata.
It does not prove fixed-target runtime permissions, audit capture, tenant isolation, or
cancellation readiness.

## G9 Tenant-Isolation Regression Gate

Added and ran focused backend tests for cross-tenant report action rejection and export-history
tenant filtering:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_report_actions_reject_cross_tenant_report_ids \
  backend/tests/test_phase2_api.py::test_report_export_history_filters_mismatched_tenant_jobs
```

Result: `10 passed`.

Also reran:

```bash
backend/.venv/bin/pytest -q backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py
make backend-lint && make backend-test
```

Results: reporting slice passed; canonical backend gate passed.

This proves local implementation behavior for report object isolation and export-history tenant
filtering. It does not prove fixed-target runtime tenant isolation or cancellation readiness.

## G9 Audit-Redaction Regression Gate

Added and ran focused backend tests for redacted SLB workflow and parity audit metadata:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_report_create_update_audit_events_store_field_names_only \
  backend/tests/test_phase2_api.py::test_report_workflow_audit_events_store_only_redacted_metadata \
  backend/tests/test_phase2_api.py::test_slb_report_parity_evidence_command_outputs_manual_comparison_rows
```

Result: `3 passed`.

Also reran:

```bash
backend/.venv/bin/pytest -q backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py
make backend-lint && make backend-test
```

Results: reporting slice passed; canonical backend gate passed.

This proves local implementation behavior for field-name-only report create/update audit metadata
and redacted audit metadata on SLB template creation, preview, diagnostics, export request/block,
scheduled dry-run, and parity generation. It does not prove fixed-target runtime audit evidence or
cancellation readiness.

## G9 Aggregate-Output Redaction Regression Gate

Added and ran focused backend tests for redaction across report preview, diagnostics, manual export
metadata, scheduled dry-run metadata, and parity output:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_report_preview_export_diagnostics_dry_run_and_parity_outputs_are_redacted
```

Result: `1 passed`.

Also reran:

```bash
backend/.venv/bin/pytest -q backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py
make backend-lint && make backend-test
```

Results: reporting slice passed; canonical backend gate passed.

This proves local implementation behavior for excluding injected token, secret, raw payload,
delivery email, recipient, and user-level identifier strings from report output surfaces. It does
not prove fixed-target runtime payload evidence, evidence-file hygiene, or cancellation readiness.

## G9 No-Live-Provider Regression Gate

Added and ran focused backend tests proving report preview, manual export preflight, scheduled
dry-run metadata, and parity evidence generation complete without live network/provider calls:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_report_preview_export_dry_run_and_parity_do_not_call_live_providers
```

Result: `1 passed`.

Also reran:

```bash
backend/.venv/bin/pytest -q backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py
make backend-lint && make backend-test
```

Results: reporting slice passed; canonical backend gate passed.

The regression blocks socket connections, `urllib.request.urlopen`, `requests`, and `httpx` after
authentication, then runs report preview, export preflight, scheduled dry-run, and parity evidence.
This proves local implementation behavior for the stored-aggregate-only reporting boundary. It does
not prove fixed-target runtime payload evidence, reviewer clearance, or cancellation readiness.

## G9 Evidence-File Hygiene Scan

Ran targeted scans across the current DashThis evidence folder:

```bash
rg -n -i "(bearer\s+[a-z0-9._~+/=-]{20,}|access_token\s*[:=]\s*['\"]?[a-z0-9._~+/=-]{20,}|refresh_token\s*[:=]\s*['\"]?[a-z0-9._~+/=-]{20,}|client_secret\s*[:=]\s*['\"]?[a-z0-9._~+/=-]{20,}|page_token\s*[:=]\s*['\"]?[a-z0-9._~+/=-]{20,}|EAAG[A-Za-z0-9]+|EAA[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|ya29\.[0-9A-Za-z_-]{20,}|-----BEGIN (RSA |OPENSSH |EC |PGP )?PRIVATE KEY-----)" \
  docs/project/evidence/dashthis-replacement

rg -n -i "[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}" \
  docs/project/evidence/dashthis-replacement
```

Result: no matches.

A broader keyword scan returned only placeholders such as `<operator-token>`, route examples,
`.env.sample` references, and policy/checklist text. No real credential, private recipient email,
raw provider payload, or unsafe artifact path was found in the current evidence docs. This does not
cover future fixed-target screenshots, exports, copied runtime snippets, or cancellation readiness.

## Decision

Local smoke validation passes only this narrow claim:

> The local backend can create an SLB `report.v1` smoke report, build preview/diagnostics/export
> metadata, complete CSV/PDF/PNG local exports after installing Playwright Chromium, run a scheduled
> dry-run render, and run the aggregate-only parity evidence command without live provider calls.

It does not close:

- G1 fixed SLB proof target.
- G2/G3 stored coverage or retained-history proof.
- G4/G5 render/export proof.
- G6 DashThis/source parity.
- G7/G8 delivery/diagnostics proof.
- G9 safety proof.
- G10-G12 cancellation review, hardening, or recommendation.

## Follow-Up

Use this smoke result to reduce implementation uncertainty only. The next cancellation-readiness
step is still to fill the G1 runtime checklist with an approved staging/production-like SLB target
and then run the G2-G9 fixed-range execution checklist against that target.
