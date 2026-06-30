# SLB Product-Capability Recommendation

Date: 2026-06-30
Timezone: America/Jamaica
Status: product-capability recommendation; formal parity/cancellation review remains source-dependent.

## Purpose

This artifact separates the internal ADinsights product decision from the formal DashThis
cancellation evidence chain.

It does not mark G12 passed and does not claim DashThis/source parity. It records that the current
repo can render, diagnose, and export the local SLB monthly report truthfully with stored aggregate
data and explicit warning-only no-data states. The official G12 cancellation packet remains
`keep_dashthis_active` until parity/source values, owner sign-off, and any required waivers are
provided.

## Recommendation

Use ADinsights as the product path for the SLB-style monthly report. Stop treating missing
DashThis/source values as an internal product-build blocker.

For business operations, choose one of these two paths:

1. If the business owner accepts no historical parity evidence, proceed toward cancelling DashThis
   for this SLB-style report with the known warning-only source states documented below.
2. If historical parity is required, keep DashThis only as a parity/source archive until approved
   May 2026 source files or values are supplied and PFG-007/G6 can run.

Do not invent missing values, do not use partial receipts as full-month parity, and do not convert
unavailable metrics to zero.

## Evidence Used

Primary product-finish controller:

- `docs/project/evidence/dashthis-replacement/2026-06-30-product-finish-goals.md`

Current target:

| Field      | Value                                  |
| ---------- | -------------------------------------- |
| Report ID  | `09c96ea9-a9e5-4283-aa29-401179ab05dc` |
| Tenant ID  | `ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2` |
| Template   | `slb_monthly_social_report`            |
| Schema     | `report.v1`                            |
| Date range | `2026-05-01` through `2026-05-31`      |

Generated local proof:

- `/tmp/adinsights-slb-product-finish/target-intake.json`
- `/tmp/adinsights-slb-product-finish/history-probe.json`
- `/tmp/adinsights-slb-product-finish/export-evidence.json`
- `/tmp/adinsights-slb-product-finish/evidence-bundle.json`
- `/tmp/adinsights-slb-product-finish/evidence-validation-no-parity.json`
- `/tmp/adinsights-slb-product-finish/parity-comparison.json`
- `/tmp/adinsights-slb-product-finish/evidence-validation-with-parity.json`
- `docs/project/evidence/dashthis-replacement/2026-06-30-slb-target-intake.local-product-finish.json`
- `docs/project/evidence/dashthis-replacement/2026-06-30-g1-runtime-target-intake.local-draft.json`

Export artifacts:

- CSV:
  `/Users/thristannewman/ADinsights/integrations/exporter/out/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/6b63dfe9-14f9-4ee8-979e-b1ba78ce9b5d.csv`
- PDF:
  `/Users/thristannewman/ADinsights/integrations/exporter/out/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/da5ce4b8-3db0-44a1-aefe-284ea9c9dd04.pdf`
- PNG:
  `/Users/thristannewman/ADinsights/integrations/exporter/out/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/ea86ecd4-71a8-4913-8908-310dc5f12ffc.png`

Preview hash:

- `282132dd24f832932ef420e5218ef92fe4fa33bf5aeb8739e7ba87d987c13adf`

## Objective Mapping

| Objective                                 | Product-capability status                              | Evidence and remaining condition                                                                                                                                                                                                                                             |
| ----------------------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SLB-001 truthful organic metrics          | Done for product capability                            | The governed SLB report uses available Page follows and post reactions/comments/shares, keeps reach/impressions unavailable without `read_insights`, and renders no-data values as unavailable/null.                                                                         |
| SLB-002 paid May coverage                 | Done as warning-only product behavior                  | Selected-account May paid rows are not present locally because the selected Meta credential is missing. Other retained tenant rows stay excluded from the SLB account scope. This is truthful warning-only no-data behavior, not full paid coverage.                         |
| SLB-003 export with warnings              | Done                                                   | CSV/PDF/PNG and scheduled dry-run artifacts are completed and non-empty with `blocking_reasons=[]`.                                                                                                                                                                          |
| SLB-004 parity worksheet                  | Partially filled; not passing                          | The sanitized comparison file contains four real PDF-backed organic source values and eight intentionally missing approved source values. Read-only parity comparison has 0 passing rows, 1 missing ADinsights value, and 8 missing source values.                           |
| RPT-001 governed report builder           | Done for the SLB product path                          | The report builder route starts from governed preview/catalog data, persists report-scoped saved layouts, appends missing governed widgets for stale layouts, and filters saved layouts by report layout id. Broader release adoption still needs normal cross-scope review. |
| META-001 metric availability states       | Done for product path                                  | Availability states distinguish available, callable-no-data, permission-gated, and unsupported metric cases.                                                                                                                                                                 |
| META-002 organic fallback import          | Implemented but unused in this run                     | Manual organic CSV import exists for approved source files; PFG-007 did not run because no approved file appeared.                                                                                                                                                           |
| UX-001 client-facing SLB report           | Done for product capability                            | PNG inspection and focused frontend tests show a nonblank monthly report shell with diagnostics/controls out of the client-facing first impression.                                                                                                                          |
| OPS-001 evidence after product/data works | Product evidence complete; formal G1-G12 remains no-go | PFG-001 through PFG-006 are complete. Official G12 still cannot pass until parity/source values or explicit owner waivers exist.                                                                                                                                             |

## Validation Summary

Completed commands:

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

Evidence validation result:

- Product-finish validation command:
  `backend/.venv/bin/python backend/manage.py slb_report_evidence_validate --evidence-bundle /tmp/adinsights-slb-product-finish/evidence-bundle.json --validation-mode product_finish --expected-start-date 2026-05-01 --expected-end-date 2026-05-31 --format json > /tmp/adinsights-slb-product-finish/evidence-validation-product-finish.json`
- Product-finish validation result: `readiness_status=warning`, `blocker_count=0`, and seven
  warnings: six warning-only coverage notes for no retained selected-account paid, organic Page/Post,
  and Content Ops rows, plus optional parity.
- Strict cancellation validation without product-finish mode still blocks when parity is absent or
  unresolved; this is intentional and keeps formal G6/G12 evidence strict.

Read-only parity result:

- Command:
  `backend/.venv/bin/python backend/manage.py slb_report_parity_compare --evidence-bundle /tmp/adinsights-slb-product-finish/evidence-bundle.json --comparison-values docs/project/evidence/dashthis-replacement/2026-06-26-slb-may-source-comparison-values.json --format json > /tmp/adinsights-slb-product-finish/parity-comparison.json`
- Source comparison file: 12 rows, 4 real PDF-backed source values, 8 missing approved source
  values, and 7 recorded source-search provenance entries.
- Real PDF-backed values found: Facebook reach `63.7K`, Facebook views `145K`, Facebook content
  interactions `55`, and Facebook follows `19`.
- Current parity comparison: 9 rows, 0 passing rows, 1 `blocked_missing_adinsights_value`, and 8
  `blocked_missing_source_value`.
- Validation with parity:
  `readiness_status=blocked`, `blocker_count=2`, with blockers for no passing parity row and
  unresolved parity rows.
- No write-capable import was run.

Preflight result:

- Release status: `GATE_WARN`
- Release-blocking issues: none
- Warnings: cross-scope control, possible contract follow-up, and security/PII verification.

## Remaining Non-Product Inputs

These are not internal product-build blockers, but they still matter for a formal cancellation claim:

| Input                                    | Current state                                               | Required to clear                                                                                                      |
| ---------------------------------------- | ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Approved paid source values              | Missing for May 1-31 selected account `act_791712443035541` | Provide selected-account daily paid export or reconnect/backfill the selected account.                                 |
| Approved organic Page/Post source values | Missing for a tenant-owned SLB Facebook Page                | Select/connect the tenant-owned SLB Page and provide approved organic export/import if reach/impressions are required. |
| Approved Content Ops totals              | Missing                                                     | Provide aggregate May 2026 source values for required content counts.                                                  |
| Formal parity comparison                 | Read-only comparison rerun is blocked with 0 passing rows   | Run PFG-007 imports only after approved source files/values and correct tenant-owned source scopes appear.             |
| Business owner decision                  | Not recorded                                                | Decide whether no historical parity is acceptable for DashThis cancellation.                                           |
| Official G12 pass                        | Not claimed                                                 | Keep the formal G12 packet at `keep_dashthis_active` unless parity/source evidence or explicit waivers are accepted.   |

G1 draft status:

- `2026-06-30-g1-runtime-target-intake.local-draft.json` is `pending_operator_input`.
- It intentionally fails G1 validation until backend/frontend URLs, currency, tenant-owned SLB Page
  scope, Content Ops workspace scope, comparison owner, tolerance confirmation, and Page/workspace
  source-scope evidence are supplied.

## Exact Current Parity Blockers

| Dataset                 | Metric(s)                                        | Result                             | Required unblock                                                                                                                     |
| ----------------------- | ------------------------------------------------ | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `paid_meta_ads`         | `spend`, `reach`, `clicks`                       | `blocked_missing_source_value`     | Provide an approved selected-account May 2026 paid source export for `act_791712443035541`; partial billing receipts do not qualify. |
| `organic_facebook_page` | `page_follows`                                   | `blocked_missing_adinsights_value` | Select/connect the tenant-owned SLB Facebook Page and dry-run approved organic import/backfill before writing values.                |
| `organic_facebook_page` | `post_reactions`, `post_comments`, `post_shares` | `blocked_missing_source_value`     | Provide approved aggregate Page/Post values; top-post examples remain unmatched audit facts, not monthly totals.                     |
| `content_ops`           | `published_posts`, `content_items_created`       | `blocked_missing_source_value`     | Provide approved aggregate May 2026 Content Ops totals; do not infer totals from a numbered content-support list.                    |

## Decision Boundary

Product capability: pass.

Formal DashThis cancellation evidence: no-go until the business owner either supplies approved
source values for parity or explicitly accepts cancellation without historical parity.

This distinction is intentional. It prevents missing external source artifacts from being mistaken
for ADinsights product defects while preserving the no-invented-values rule for parity and business
sign-off.
