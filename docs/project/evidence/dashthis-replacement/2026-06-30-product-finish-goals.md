# SLB Product-Finish Goals

Date: 2026-06-30
Timezone: America/Jamaica
Status: active product-capability finish lane

## Purpose

This replaces the "wait for external proof" posture with a short set of product goals that can be
finished inside ADinsights. External target selection, runtime release configuration, missing
DashThis/source values, and final business sign-off are not product defects. They may still block a
formal parity or cancellation claim, but they should not stop us from proving the reporting system
works well enough to replace DashThis for the SLB-style report.

The finish line is:

- the SLB monthly report renders truthful stored aggregate data;
- unavailable metrics stay visibly unavailable, never zero;
- CSV/PDF/PNG exports and scheduled dry-run evidence are non-empty;
- diagnostics and safety proof are support-ready;
- hardening/adversarial checks find no unresolved product blocker;
- the final recommendation can say either "cancel DashThis" or "keep only for parity/source archive"
  based on product evidence, without inventing missing source values.

## Working Target

Use the current local fixed target unless a later product-finish run intentionally changes it.

| Field      | Value                                  |
| ---------- | -------------------------------------- |
| Report ID  | `09c96ea9-a9e5-4283-aa29-401179ab05dc` |
| Tenant ID  | `ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2` |
| Template   | `slb_monthly_social_report`            |
| Schema     | `report.v1`                            |
| Date range | `2026-05-01` through `2026-05-31`      |

Reference evidence:

- `docs/project/evidence/dashthis-replacement/2026-06-26-slb-fixed-target-export-warning-evidence.md`
- `docs/project/report-builder-handover.md`
- `docs/project/evidence/dashthis-replacement/2026-06-16-g2-g9-evidence-execution-checklist.md`
- `docs/project/evidence/dashthis-replacement/2026-06-30-slb-product-capability-recommendation.md`

## Evidence Run: 2026-06-30 Local Product Finish

Status: PFG-001 through PFG-006 are done for the current local product-finish lane. PFG-007 was not
run as a write-capable import because no approved DashThis/source files were provided. A read-only
parity comparison was run against the existing sanitized May 2026 comparison-values JSON and remains
blocked, with no passing rows.

Generated artifacts:

- `/tmp/adinsights-slb-product-finish/target-intake.json`
- `/tmp/adinsights-slb-product-finish/history-probe.json`
- `/tmp/adinsights-slb-product-finish/export-evidence.json`
- `/tmp/adinsights-slb-product-finish/evidence-bundle.json`
- `/tmp/adinsights-slb-product-finish/evidence-validation-product-finish.json`
- `/tmp/adinsights-slb-product-finish/evidence-validation-product-finish-with-parity.json`
- `/tmp/adinsights-slb-product-finish/evidence-validation-no-parity.json`
- `/tmp/adinsights-slb-product-finish/parity-comparison.json`
- `/tmp/adinsights-slb-product-finish/evidence-validation-with-parity.json`
- `docs/project/evidence/dashthis-replacement/2026-06-30-slb-target-intake.local-product-finish.json`
- `docs/project/evidence/dashthis-replacement/2026-06-30-g1-runtime-target-intake.local-draft.json`
- `/Users/thristannewman/ADinsights/integrations/exporter/out/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/6b63dfe9-14f9-4ee8-979e-b1ba78ce9b5d.csv`
- `/Users/thristannewman/ADinsights/integrations/exporter/out/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/da5ce4b8-3db0-44a1-aefe-284ea9c9dd04.pdf`
- `/Users/thristannewman/ADinsights/integrations/exporter/out/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/ea86ecd4-71a8-4913-8908-310dc5f12ffc.png`

Proof summary:

- Target intake recognizes report `09c96ea9-a9e5-4283-aa29-401179ab05dc` as `report.v1` using
  template `slb_monthly_social_report`, with the May 1-31, 2026 custom date range and selected SLB
  account scope.
- History/source proof reports `stored_aggregate_only=true` and `no_live_provider_calls=true`.
- Export evidence reports `export_ready=true`, `blocking_reasons=[]`, and preview hash
  `282132dd24f832932ef420e5218ef92fe4fa33bf5aeb8739e7ba87d987c13adf`.
- CSV, PDF, and PNG completed with non-empty artifacts using `report_v1_snapshot` and
  `shared_saved_layout`; the scheduled dry-run PDF also rendered.
- Product-finish evidence validation uses `--validation-mode product_finish` and returns
  `readiness_status=warning`, `blocker_count=0`, and warning-only notes for no retained selected
  paid/organic/content rows plus optional parity. Strict cancellation validation still blocks on
  parity, which belongs to optional PFG-007.
- Read-only parity comparison with
  `docs/project/evidence/dashthis-replacement/2026-06-26-slb-may-source-comparison-values.json`
  produces `row_count=9`, `blocked_missing_adinsights_value=1`, and
  `blocked_missing_source_value=8`. Validation with that parity file reports two blockers:
  `Parity comparison must include at least one passing row` and unresolved parity rows.
- Visual PNG inspection found a nonblank monthly-client-report shell with visible warning-only data
  notes, null placeholders for unavailable metrics, and no obvious overlap or clipping.
- A report-builder regression was fixed so the saved-layout selector filters returned rows by the
  generated report layout id before rendering options.

Remaining warning-only states:

- `paid_meta_ads` has no retained selected-account rows for May 2026; the local diagnostic says the
  selected Meta credential is missing, while 116 retained rows for other tenant scope remain
  excluded.
- `organic_facebook_page`, `organic_facebook_posts`, and `content_ops` have no retained rows for the
  requested range and export as explicit warning-only no-data sections.
- The May 2026 source comparison file contains four real PDF-backed organic source values:
  Facebook reach `63.7K`, Facebook views `145K`, Facebook content interactions `55`, and Facebook
  follows `19`. Only follows currently matches an active parity row, and it is blocked by a missing
  retained/imported ADinsights value for a tenant-owned SLB Page.
- The same comparison file records eight missing approved source values: selected-account paid
  spend/reach/clicks, aggregate post reactions/comments/shares, published posts, and content items
  created.
- These states are not product blockers for PFG-001 through PFG-006 because unavailable values stay
  visible as unavailable/null and exports proceed with warnings. They still prevent a truthful
  full-data parity claim unless approved source files appear or the selected sources are
  reconnected/backfilled.

Validation commands completed:

- `ruff check backend/analytics/reporting_availability.py backend/analytics/reporting_preview.py backend/analytics/reporting_report_preview.py backend/analytics/reporting_templates.py backend/integrations/services/metric_registry.py`
- `cd backend && pytest -q tests/test_meta_organic_csv_import.py tests/test_meta_paid_csv_import.py tests/test_phase2_api.py -k 'report_data_availability or dashboard_widget_preview or report_preview or meta_paid_csv or meta_organic_csv'`
- `cd frontend && npm run lint`
- `cd frontend && npx vitest run src/routes/__tests__/ReportDetailPage.test.tsx src/routes/__tests__/ReportLayoutPreview.test.tsx src/components/report-layout/__tests__/reportPreviewAdapter.test.ts`
- `cd frontend && npm run build`
- `cd backend && pytest -q tests/test_phase2_api.py tests/test_meta_page_api.py -k 'tenant or report_layout or export or source_health or audit or permission'`
- `ruff check backend scripts`
- `PYTHONPATH=backend:. pytest -q scripts/tests/test_slb_cancellation_readiness_doctor.py scripts/tests/test_validate_slb_cancellation_readiness_status.py`
- `npx prettier --check docs/project/evidence/dashthis-replacement/2026-06-30-product-finish-goals.md`
- `git diff --check`
- `make adinsights-preflight PROMPT="Assess SLB product-finish readiness with external source values treated as comparison inputs, not product defects."`
- `backend/.venv/bin/python backend/manage.py slb_report_evidence_validate --evidence-bundle /tmp/adinsights-slb-product-finish/evidence-bundle.json --validation-mode product_finish --expected-start-date 2026-05-01 --expected-end-date 2026-05-31 --format json > /tmp/adinsights-slb-product-finish/evidence-validation-product-finish.json`
- `backend/.venv/bin/python backend/manage.py slb_report_parity_compare --evidence-bundle /tmp/adinsights-slb-product-finish/evidence-bundle.json --comparison-values docs/project/evidence/dashthis-replacement/2026-06-26-slb-may-source-comparison-values.json --format json > /tmp/adinsights-slb-product-finish/parity-comparison.json`
- `backend/.venv/bin/python backend/manage.py slb_report_evidence_validate --evidence-bundle /tmp/adinsights-slb-product-finish/evidence-bundle.json --parity-comparison /tmp/adinsights-slb-product-finish/parity-comparison.json --validation-mode product_finish --expected-start-date 2026-05-01 --expected-end-date 2026-05-31 --format json > /tmp/adinsights-slb-product-finish/evidence-validation-product-finish-with-parity.json`
- `backend/.venv/bin/python backend/manage.py slb_report_evidence_validate --evidence-bundle /tmp/adinsights-slb-product-finish/evidence-bundle.json --parity-comparison /tmp/adinsights-slb-product-finish/parity-comparison.json --expected-start-date 2026-05-01 --expected-end-date 2026-05-31 --format json > /tmp/adinsights-slb-product-finish/evidence-validation-with-parity.json`

Preflight result: release status `GATE_WARN`, with no release-blocking issues. Warnings remain for
cross-scope control, possible contract follow-up, and security/PII verification because the finish
lane spans backend, frontend, docs, scripts, and exporter behavior.

## Goal Status Key

- `todo` - not finished yet.
- `ready-to-run` - all repo prerequisites exist; execute and record evidence.
- `done` - current evidence proves the goal.
- `optional-parity` - useful for cancellation confidence, but not required to prove product
  capability.

## PFG-001: Freeze The Product Target

Status: `done`

Make the local SLB report the product target for the finish lane. This is not a human handoff; it is
the target we use to prove the system behavior.

Acceptance criteria:

- `slb_report_target_intake` recognizes the report as `report.v1` and `slb_monthly_social_report`.
- The report filters stay pinned to the SLB paid account scope.
- The evidence bundle, export evidence, and history probe all use the same report ID and May 2026
  date range.
- Any missing Page scope remains an explicit warning/diagnostic, not a substituted Page.

Commands:

```bash
export SLB_REPORT_ID="09c96ea9-a9e5-4283-aa29-401179ab05dc"
export SLB_START_DATE="2026-05-01"
export SLB_END_DATE="2026-05-31"
export SLB_HISTORY_START_DATE="2026-03-03"
export SLB_HISTORY_END_DATE="2026-05-31"
export SLB_FINISH_TMP="/tmp/adinsights-slb-product-finish"
mkdir -p "$SLB_FINISH_TMP"

backend/.venv/bin/python backend/manage.py slb_report_target_intake \
  --report-id "$SLB_REPORT_ID" \
  > "$SLB_FINISH_TMP/target-intake.json"

backend/.venv/bin/python backend/manage.py slb_report_history_probe \
  --report-id "$SLB_REPORT_ID" \
  --primary-start-date "$SLB_START_DATE" \
  --primary-end-date "$SLB_END_DATE" \
  --history-start-date "$SLB_HISTORY_START_DATE" \
  --history-end-date "$SLB_HISTORY_END_DATE" \
  > "$SLB_FINISH_TMP/history-probe.json"
```

## PFG-002: Prove Truthful Data Semantics

Status: `done`

The report must be truthful with available organic metrics and selected-account paid warning states.
This is the core "system works" goal.

Acceptance criteria:

- No report preview/export path calls live Meta.
- No code path requires `read_insights`.
- Organic reach/impression/click widgets are downgraded, permission-gated, or explanatory notes.
- Available organic metrics use Page follows plus post reactions/comments/shares.
- Selected-account paid May rows are either real full-range rows or explicit warning-only no-data /
  partial-coverage states.
- Missing values render as `null` / no data, never `0`.
- Coverage notes name missing internal date spans when endpoint-only rows exist.

Commands:

```bash
ruff check \
  backend/analytics/reporting_availability.py \
  backend/analytics/reporting_preview.py \
  backend/analytics/reporting_report_preview.py \
  backend/analytics/reporting_templates.py \
  backend/integrations/services/metric_registry.py

cd backend && pytest -q \
  tests/test_meta_organic_csv_import.py \
  tests/test_meta_paid_csv_import.py \
  tests/test_phase2_api.py \
  -k 'report_data_availability or dashboard_widget_preview or report_preview or meta_paid_csv or meta_organic_csv'
```

## PFG-003: Prove Exports And Dry-Run Delivery

Status: `done`

Export is a product capability. It should pass even when parity values are missing, as long as the
report carries visible warnings.

Acceptance criteria:

- `export_ready=true`.
- `blocking_reasons=[]`.
- CSV, PDF, and PNG artifacts are completed and non-empty.
- PDF/PNG use the saved report layout when present.
- Stale saved layouts append missing governed widgets before rendering.
- Scheduled dry-run renders a non-empty artifact and is not counted as manual CSV/PDF/PNG export
  proof.

Commands:

```bash
backend/.venv/bin/python backend/manage.py slb_report_export_evidence \
  --report-id "$SLB_REPORT_ID" \
  --start-date "$SLB_START_DATE" \
  --end-date "$SLB_END_DATE" \
  > "$SLB_FINISH_TMP/export-evidence.json"

backend/.venv/bin/python backend/manage.py slb_report_evidence_bundle \
  --report-id "$SLB_REPORT_ID" \
  --start-date "$SLB_START_DATE" \
  --end-date "$SLB_END_DATE" \
  > "$SLB_FINISH_TMP/evidence-bundle.json"
```

## PFG-004: Prove Client-Facing Report UX

Status: `done`

The first screen should read like a client monthly report, not an engineering diagnostic page.

Acceptance criteria:

- Report detail header/actions do not dominate the first viewport.
- Operator controls, diagnostics, source health, and evidence details are collapsed by default.
- Visible report notes explain unavailable reach/impressions without sounding like a stack trace.
- PDF/PNG report shell is nonblank and has no obvious overlap or clipping.
- The Report Detail and builder tests cover saved-layout rebinding and governed widget append.

Suggested checks:

```bash
cd frontend && npm run lint
cd frontend && npx vitest run \
  src/routes/__tests__/ReportDetailPage.test.tsx \
  src/routes/__tests__/ReportLayoutPreview.test.tsx \
  src/components/report-layout/__tests__/reportPreviewAdapter.test.ts
cd frontend && npm run build
```

Visual proof can use the latest PNG export from `PFG-003`; inspect it before marking this done.

## PFG-005: Prove Safety And Supportability

Status: `done`

Cancellation confidence needs tenant-safe, support-ready behavior, not just pretty exports.

Acceptance criteria:

- Tenant isolation tests pass for report preview, builder, saved layouts, exports, and evidence
  commands.
- Evidence artifacts contain aggregate metrics only; no user-level rows, emails, tokens, raw provider
  payloads, or secrets.
- Source-health diagnostics give actionable next steps for selected-account paid no-data and missing
  SLB Page scope.
- Audit and permission behavior is covered for report/export/saved-layout actions.
- Rate/quotas or bounded execution checks are documented where applicable.

Suggested checks:

```bash
cd backend && pytest -q \
  tests/test_phase2_api.py \
  tests/test_meta_page_api.py \
  -k 'tenant or report_layout or export or source_health or audit or permission'

backend/.venv/bin/python backend/manage.py slb_report_evidence_validate \
  --evidence-bundle "$SLB_FINISH_TMP/evidence-bundle.json" \
  --validation-mode product_finish \
  --expected-start-date "$SLB_START_DATE" \
  --expected-end-date "$SLB_END_DATE" \
  --format json \
  > "$SLB_FINISH_TMP/evidence-validation-product-finish.json"
```

This validation must return `blocker_count=0`. It may return warnings for warning-only no-data
sections and optional parity, but those are not product/safety/export blockers.

## PFG-006: Run Product Confidence Hardening

Status: `done`

This is the final internal goal. It replaces a time-based hardening ritual with direct proof that
the product behavior is stable.

Acceptance criteria:

- PFG-001 through PFG-005 are done or have a written waiver for a non-product input.
- Focused backend/frontend tests pass.
- `git diff --check` passes.
- Prettier passes for changed docs.
- ADinsights preflight has no release-blocking issues.
- A final product-confidence note records any remaining warning-only states and why they do not
  prevent using ADinsights instead of DashThis for the SLB report.

Commands:

```bash
ruff check backend scripts
PYTHONPATH=backend:. pytest -q scripts/tests/test_slb_cancellation_readiness_doctor.py \
  scripts/tests/test_validate_slb_cancellation_readiness_status.py
npx prettier --check docs/project/evidence/dashthis-replacement/2026-06-30-product-finish-goals.md
git diff --check
make adinsights-preflight PROMPT="Assess SLB product-finish readiness with external source values treated as comparison inputs, not product defects."
```

## PFG-007: Optional Parity Import/Compare

Status: `optional-parity`; read-only comparison rerun is blocked.

Run this only if approved source files appear. Do not invent values and do not promote partial
receipts, proposals, creative docs, screenshots, or unrelated tenant rows into parity facts.

Current read-only result:

- Source comparison rows: 12 total, 4 with real PDF-backed source values, 8 intentionally missing.
- Current parity comparison rows: 9.
- Passing rows: 0.
- Blocked rows: 1 `blocked_missing_adinsights_value`, 8 `blocked_missing_source_value`.
- Primary next action: provide an approved selected-account May 2026 Meta Ads source export, then
  dry-run `import_meta_paid_csv` if retained ADinsights rows are still missing.
- No write-capable import was run.

Acceptance criteria:

- Candidate paid CSV is selected-account daily data for `act_791712443035541`.
- Candidate organic CSV is mapped to a tenant-owned SLB Facebook Page, not the local AdTelligent
  Page.
- Candidate Content Ops totals are approved aggregate May 2026 source values.
- Dry-runs pass before any write-capable import.
- Parity compare either passes rows or leaves explicit missing-source / missing-ADinsights blockers.

Commands:

```bash
backend/.venv/bin/python backend/manage.py import_meta_paid_csv \
  --tenant-id "ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2" \
  --account-id "act_791712443035541" \
  --file "<approved-selected-account-daily-paid-export.csv>" \
  --dry-run

backend/.venv/bin/python backend/manage.py slb_report_parity_compare \
  --evidence-bundle "$SLB_FINISH_TMP/evidence-bundle.json" \
  --comparison-values docs/project/evidence/dashthis-replacement/2026-06-26-slb-may-source-comparison-values.json \
  --format json \
  > "$SLB_FINISH_TMP/parity-comparison.json"
```

## Finish Decision

After PFG-001 through PFG-006 pass, the recommended decision can be written without waiting for
external source values:

- If product proof is clean and the only remaining issue is missing comparison values, recommend
  cancelling DashThis with a note that historical parity was not available from approved source
  exports.
- If product proof still has an internal blocker, keep DashThis active and name the product blocker.
- If approved source values appear later, run PFG-007 and update the recommendation with parity
  deltas.

Do not call the product finished while any PFG-001 through PFG-006 acceptance criterion is unproven.
Do not use PFG-007 to mask a product blocker.

The current product-capability recommendation is recorded in
`docs/project/evidence/dashthis-replacement/2026-06-30-slb-product-capability-recommendation.md`.
It recommends using ADinsights as the SLB report product path while keeping formal
DashThis/source parity and cancellation sign-off source-dependent.
