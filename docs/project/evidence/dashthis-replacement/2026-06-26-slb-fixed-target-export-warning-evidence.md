# SLB Fixed-Target Export-Warning Evidence

Date: 2026-06-26
Timezone: America/Jamaica
Status: fixed-target exports now complete with selected-account paid no-data warnings; DashThis
cancellation remains no-go.

## Target

| Field       | Value                                              |
| ----------- | -------------------------------------------------- |
| Report ID   | `09c96ea9-a9e5-4283-aa29-401179ab05dc`             |
| Tenant ID   | `ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2`             |
| Report name | `LOCAL SMOKE - SLB Monthly Social Report May 2026` |
| Template    | `slb_monthly_social_report`                        |
| Schema      | `report.v1`                                        |
| Date range  | `2026-05-01` through `2026-05-31`                  |

## Account-Scope Recheck

Later on 2026-06-26, a truthfulness review found that the first local bundle was generated before
the report was pinned to the SLB paid Meta account. The paid rows in that earlier bundle came from
tenant-level retained Meta rows and included non-SLB campaigns, so the export-ready result below is
historical only and must not be used for G2-G12 cancellation evidence.

The fixed local report was updated to store:

- `account_id=act_791712443035541` for `Students' Loan Bureau (SLB)`.
- No `page_id`, because the local tenant currently has only an `AdTelligent` Page row; pinning that
  Page to SLB would be misleading.

Regenerated evidence was written to `/tmp/adinsights-slb-20260626-truthful-scope/`:

```bash
backend/.venv/bin/python backend/manage.py slb_report_evidence_bundle \
  --report-id 09c96ea9-a9e5-4283-aa29-401179ab05dc \
  --start-date 2026-05-01 \
  --end-date 2026-05-31 \
  > /tmp/adinsights-slb-20260626-truthful-scope/evidence-bundle.json

backend/.venv/bin/python backend/manage.py slb_report_parity_compare \
  --evidence-bundle /tmp/adinsights-slb-20260626-truthful-scope/evidence-bundle.json \
  --comparison-values docs/project/evidence/dashthis-replacement/2026-06-26-slb-may-source-comparison-values.json \
  --format json \
  > /tmp/adinsights-slb-20260626-truthful-scope/parity-comparison.json

backend/.venv/bin/python backend/manage.py slb_report_evidence_validate \
  --evidence-bundle /tmp/adinsights-slb-20260626-truthful-scope/evidence-bundle.json \
  --parity-comparison /tmp/adinsights-slb-20260626-truthful-scope/parity-comparison.json \
  > /tmp/adinsights-slb-20260626-truthful-scope/validation-with-partial-parity.json
```

Current warning-only recheck outcome:

- Preview hash: `0b5fcebe5f839ba46c28259d100e8f7a9676ee16367a6a21c4401743382afa66`.
- `export_ready=true`.
- Blocking reasons: `[]`.
- Coverage: `paid_meta_ads` has `row_count=0` for the selected account and renders
  `not_previously_synced` warnings in the report snapshot; organic Facebook and Content Ops remain
  `missing_history` warning states.
- `data_availability.datasets.paid_meta_ads.scope_diagnostic.credential_status.status=missing`, so
  the report is truthful no-data output, not paid coverage completion.
- Current-hash CSV/PDF/PNG exports are present and non-empty. They do not populate paid values and do
  not clear parity.

The source-backed comparison file
`docs/project/evidence/dashthis-replacement/2026-06-26-slb-may-source-comparison-values.json`
now contains twelve reviewed source rows. The current comparator matches nine active parity rows:

- three selected-account paid rows (`spend`, `reach`, `clicks`), all still missing approved May 1-31
  source values;
- one Page summary row (`page_follows=19`), still blocked on semantic/import prerequisites because
  no tenant-owned SLB Page row exists locally;
- three organic post rows (`post_reactions`, `post_comments`, `post_shares`), all still missing
  aggregate May source values;
- two Content Ops rows (`published_posts`, `content_items_created`), both still missing aggregate May
  source values.

The same file also records unmatched source facts such as Facebook reach/views/interactions, Facebook
visits, Facebook link clicks, top-performer creative metrics, and partial Meta receipt windows. Those
figures are visible for auditability without being misapplied to active paid Meta Ads, Page/Post, or
Content Ops parity rows.

Parity result summary:

```json
{
  "blocked_missing_adinsights_value": 1,
  "blocked_missing_source_value": 8
}
```

Fresh bundle/parity/validation files were written under `/tmp/adinsights-slb-parity-20260626/`.
Validator blockers are now limited to unresolved parity:

```json
{
  "readiness_status": "blocked",
  "blocker_count": 2,
  "warning_count": 6,
  "blockers": [
    {
      "code": "parity_results",
      "message": "Parity comparison must include at least one passing row."
    },
    {
      "code": "parity_results",
      "message": "Parity has unresolved rows: {'blocked_missing_adinsights_value': 1, 'blocked_missing_source_value': 8}."
    }
  ]
}
```

The regenerated validation JSON also includes `unresolved_parity` so reviewers do not have to infer
the remaining work from the summary alone:

- `paid_meta_ads`: three `blocked_missing_source_value` rows for spend, reach, and clicks.
- `organic_facebook_page`: one `blocked_missing_adinsights_value` Page follows row with a source
  value present but no retained matching ADinsights report value, plus three
  `blocked_missing_source_value` post engagement rows.
- `content_ops`: two `blocked_missing_source_value` rows for published posts and content items
  created.

Missing paid/organic/content rows are warning-only evidence states, not export blockers.

## Source Artifact Search

On 2026-06-26, the local workspace, Codex attachments, and Downloads were searched for additional
May 2026 SLB source exports using SLB/client, Meta account, paid, source, and date patterns. No
approved CSV/XLSX/PDF/JSON source artifact was found for selected-account paid spend/reach/clicks or
Content Ops totals beyond the already reviewed May 2026 SLB PDF. The only separate local paid rows
found remain tenant-level/non-SLB retained rows and must not be used to clear the fixed SLB report.

Connected Gmail/Drive searches were also checked on 2026-06-26:

- Gmail selected-account search for `791712443035541` / `act_791712443035541` found Meta billing
  receipts and an ad-account disabled notice for Students' Loan Bureau. Those messages prove billing
  activity/account state, but they are not daily paid performance exports and do not provide paid reach
  or clicks.
- Gmail searches for SLB May 2026 report/export/DashThis/paid terms found the same May 2026 SLB PDF
  already reviewed, plus operational, procurement, creative, and client-reply threads. No separate
  approved CSV/XLSX or DashThis/source export was found.
- Google Drive searches for `SLB May 2026`, `DashThis SLB`, `791712443035541`, `SLB paid May`, and
  `SLB Monthly Report` found operations reports, proposal/rate-sheet spreadsheets, budget documents,
  and creative treatments. No approved May 2026 source export for selected-account paid
  spend/reach/clicks or Content Ops totals was found.

A narrowed 2026-06-27 connected-source pass rechecked Gmail and Drive with low-result-limit queries
for the selected paid account, SLB May report names, paid/source/export terms, Content Ops terms, and
DashThis/source wording. It found the exact May 2026 SLB report email with the already reviewed PDF
attachment, Meta receipts for partial billing windows May 21-24 and May 26-31, the selected-account
disabled notice, daily task/status notes, proposals, operational documents, and creative assets. The
receipts show partial billed spend/impression subtotals only; they are not approved May 1-31 paid
performance exports and do not provide paid reach or clicks, so paid parity rows remain null. No
approved full-month paid Meta Ads export, DashThis/source export, aggregate Page/Post export, or
aggregate Content Ops total export was found.

A 2026-06-28 Gmail current-state recheck repeated the selected-account, paid/source attachment,
organic/content aggregate, and DashThis/source report queries. The selected-account query still
returned only Meta receipts and the disabled-account notice. The paid/source attachment search
remained noisy with creative, quotation, treatment, podcast, and March-April report threads. The
organic/content aggregate query returned no messages. The DashThis/source report query found the
already reviewed May 2026 SLB report PDF email plus task notes and drafts/previews. No approved
May 1-31 paid Meta Ads export, DashThis/source export, aggregate Page/Post export, or aggregate
Content Ops total export was found, so no additional parity values were added.

A second narrowed 2026-06-28 Drive/Gmail recheck used exact unresolved-row terms for reactions,
comments, shares, exports, the selected paid account, Content Ops, and published posts. Drive
returned creative treatments/storyboards/proposals, rate sheets/quotes, task logs, operational
trackers/maps, an operations report, and budget collections; the account-id query returned no files.
Gmail returned no messages for the organic/content/export query, while the paid/account attachment
query returned banner, creative-treatment, podcast quotation/treatment, unrelated bid, and March-April
report threads. No approved May 1-31 selected-account paid export, aggregate Page/Post export,
DashThis/source export, or aggregate Content Ops total export was found, so the unresolved parity rows
remain null.

The partial receipt facts are preserved in the comparison-values JSON as unmatched source inventory,
not parity rows:

- May 21-24 receipt window: USD 31.74 billed spend and 63,900 receipt impressions across two
  campaign receipt rows.
- May 26-31 receipt window: USD 44.16 billed spend and 82,669 receipt impressions across two
  campaign receipt rows.

Those facts are useful for diagnosing paid activity/coverage, but they do not cover May 1-31, do
not include paid reach or paid clicks, and are billing receipts rather than approved paid
performance exports. They must not be copied into the paid parity rows.

The local tenant also has only one analyzable `MetaPage`, named `AdTelligent`
(`page_id=1149538181749811`). The manual organic import was intentionally not run because importing
SLB PDF organic values into that Page row would attach SLB evidence to the wrong Page.
`import_meta_organic_csv --dry-run` is now available for validating an approved organic source file
before writes, but it still requires the correct tenant-owned SLB Facebook Page mapping; it does not
permit validating or importing SLB values against the local AdTelligent Page.
The regenerated evidence bundle now carries this as redacted machine-readable support state:
`source_health.report_scope.organic_facebook_page.page_scope_present=false`,
`matched_page_count=0`, `available_page_count=1`, and
`backfill_status=blocked_missing_scope`. Organic import/backfill remediation actions include a
prerequisite to select the tenant-owned SLB Facebook Page first and avoid importing SLB source values
into another Page.

Paid backfill dry-run for the scoped SLB account:

```bash
backend/.venv/bin/python backend/manage.py slb_backfill_meta_reporting \
  --report-id 09c96ea9-a9e5-4283-aa29-401179ab05dc \
  --start-date 2026-05-01 \
  --end-date 2026-05-31 \
  --datasets paid_meta_ads \
  --account-id act_791712443035541 \
  --dispatch-mode dry-run
```

Result: `paid_meta_ads.status=blocked`, `reason=meta_ad_account_credential_missing`. Required
action: reconnect Meta/Facebook and select the SLB ad account before attempting paid May backfill.
If an approved Meta Ads daily export for the selected SLB account is available before credentials
are repaired, the dry-run exposes `fallback_actions[].code=manual_meta_paid_csv_import` and
`post_backfill_commands.manual_paid_csv_import`; the paired
`dry_run_command_template` / `post_backfill_commands.manual_paid_csv_import_dry_run` values should
be run before any write-capable import. Do not use monthly aggregate rows or unrelated tenant paid
rows to clear this blocker.
`import_meta_paid_csv --dry-run` is available for validating a candidate selected-account daily paid
export before writes, but it does not create paid coverage or clear parity until the approved daily
rows are actually imported for `act_791712443035541`.
`slb_backfill_meta_reporting --dispatch-mode dry-run` is also plan-only: it emits
`audit_event.status=skipped` and does not record `slb_backfill_meta_reporting_requested` until a
queued or inline run is requested. Organic post dry-runs also report planned edge enrichment under
`engagement_edges[page_id].status=planned` without calling Meta edge endpoints.

## Latest Fixed-Target Export Evidence

Command:

```bash
backend/.venv/bin/python backend/manage.py slb_report_export_evidence \
  --report-id 09c96ea9-a9e5-4283-aa29-401179ab05dc \
  --start-date 2026-05-01 \
  --end-date 2026-05-31
```

Outcome:

- `export_ready=true`
- `blocking_reasons=[]`
- `data_availability.blocking_datasets=[]`
- `data_availability.warning_datasets=["paid_meta_ads","organic_facebook_page","organic_facebook_posts","content_ops"]`
- `data_availability.datasets.paid_meta_ads.row_count=0`
- selected-account diagnostic code: `requested_account_no_rows`
- selected-account credential status: `missing`

Current-hash export artifacts:

| Format | Job ID                                 | Artifact path                                                                                                                 | Byte count |
| ------ | -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ---------: |
| CSV    | `f870e18b-984c-495c-964d-7184eb04f878` | `/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/f870e18b-984c-495c-964d-7184eb04f878.csv` |       4825 |
| PDF    | `9c4bbf77-6b7d-459d-9b91-3bf6858f6c8b` | `/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/9c4bbf77-6b7d-459d-9b91-3bf6858f6c8b.pdf` |     139963 |
| PNG    | `d88ab648-d0df-4e40-bb4f-e8c68b60544f` | `/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/d88ab648-d0df-4e40-bb4f-e8c68b60544f.png` |     247024 |

Scheduled dry-run evidence:

- Job ID: `9bc382f0-a6c6-4b42-ac9f-dd4b140bf968`
- Format: PDF
- Status: `completed`
- Delivery status: `mode=dry_run`, `status=rendered`, `sanitized=true`
- Artifact byte count: `140250`

## 2026-06-27 Layout-Backed Export Rerun

After `slb_report_evidence_bundle` was updated to preserve saved-layout proof fields, a local-only
shared saved layout was added for the `LOCAL SMOKE` report so the fixed target exercises the same
saved-layout export path as API exports:

- Saved layout ID: `1cc3beaa-a4e1-42b1-b490-9bc030ffae46`
- Config ID: `report-09c96ea9-a9e5-4283-aa29-401179ab05dc`
- Source in export evidence: `shared_saved_layout`

The rerun used the same fixed target and date range:

```bash
backend/.venv/bin/python backend/manage.py slb_report_export_evidence \
  --report-id 09c96ea9-a9e5-4283-aa29-401179ab05dc \
  --start-date 2026-05-01 \
  --end-date 2026-05-31
```

Outcome:

- Preview hash: `33f302ff8a2bac2cb886e380219f649ff9e31a8813470ec988f7028adf26e6a8`
- `export_ready=true`
- `blocking_reasons=[]`
- `data_availability.warning_datasets=["paid_meta_ads","organic_facebook_page","organic_facebook_posts","content_ops"]`
- `data_availability.datasets.paid_meta_ads.scope_diagnostic.credential_status.status=missing`
- Every fresh export row has `report_layout_source=shared_saved_layout`.
- Every fresh export row has `report_layout_governed_widget_append_count=17`, proving stale/custom
  saved layouts are augmented with governed report widgets before rendering.

Fresh layout-backed export artifacts:

| Format | Job ID                                 | Artifact path                                                                                                                 | Byte count | Layout source         | Append count |
| ------ | -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ---------: | --------------------- | -----------: |
| CSV    | `2db1809a-996b-4806-ad62-ab3019729c15` | `/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/2db1809a-996b-4806-ad62-ab3019729c15.csv` |       5292 | `shared_saved_layout` |           17 |
| PDF    | `66c7c7d4-a140-4504-967a-c098a02167b5` | `/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/66c7c7d4-a140-4504-967a-c098a02167b5.pdf` |     221463 | `shared_saved_layout` |           17 |
| PNG    | `a35f8961-ba8f-4aeb-8f32-81acdc6847ea` | `/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/a35f8961-ba8f-4aeb-8f32-81acdc6847ea.png` |     152542 | `shared_saved_layout` |           17 |

Scheduled dry-run evidence:

- Job ID: `7b4a1879-6881-4849-aac7-8d2da913920a`
- Format: PDF
- Status: `completed`
- Delivery status: `mode=dry_run`, `status=rendered`, `sanitized=true`
- Artifact byte count: `221195`
- Layout source: `shared_saved_layout`
- Governed widget append count: `17`

The current rerun bundle, parity, and validation files were written to:

- `/tmp/adinsights-slb-current-bundle-layout.json`
- `/tmp/adinsights-slb-current-parity-layout.json`
- `/tmp/adinsights-slb-current-validation-layout.json`

The evidence bundle now preserves the same layout fields in its export summary. It lists both fresh
layout-backed jobs and older same-hash jobs; use the rows with `report_layout_source=shared_saved_layout`
as the current saved-layout proof.
`slb_report_evidence_validate` now reports the selected newest reproducible rows in
`export_evidence.selected_completed_exports`, which avoids treating older same-hash rows as the
current proof set. Scheduled dry-run rows remain separate evidence and do not satisfy completed
CSV/PDF/PNG export proof.

Offline validation remains blocked only by parity/source-value results:

```json
{
  "readiness_status": "blocked",
  "blocker_count": 2,
  "warning_count": 6,
  "blocker_codes": ["parity_results"],
  "export_evidence": {
    "selected_completed_format_count": 3,
    "selected_layout_source_count": 3
  },
  "parity_summary": {
    "blocked_missing_adinsights_value": 1,
    "blocked_missing_source_value": 8
  }
}
```

The validator also emits `blocking_next_actions` from those parity completion requirements. For the
current fixed target, every action has `can_run_now=false`: no approved full-month selected-account
paid source export is available; no tenant-owned SLB Facebook Page is selected locally for the Page
Follows import; no approved monthly aggregate post reactions/comments/shares source export is
available; and no approved Content Ops aggregate totals are available. This keeps G6/G11/G12 blocked
without making reviewers infer the missing prerequisites from narrative text.

## 2026-06-28 Current-State Gmail + Export Rerun

After the 2026-06-28 Gmail source recheck was added to the comparison-values worksheet, the fixed
target was regenerated again for the same May 1-31 range:

```bash
backend/.venv/bin/python backend/manage.py slb_report_export_evidence \
  --report-id 09c96ea9-a9e5-4283-aa29-401179ab05dc \
  --start-date 2026-05-01 \
  --end-date 2026-05-31 \
  > /tmp/adinsights-slb-20260628-current-state/export-evidence.json
```

Outcome:

- Preview hash: `69f5117e93e3883958596f479a0a73dd951ed94eabc50a5a6e5cf29054836344`
- `export_ready=true`
- `blocking_reasons=[]`
- every fresh manual export row has `source=report_v1_snapshot`,
  `report_layout_source=shared_saved_layout`, and
  `report_layout_governed_widget_append_count=17`

Fresh manual export artifacts:

| Format | Job ID                                 | Artifact path                                                                                                                 | Byte count | Layout source         | Append count |
| ------ | -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ---------: | --------------------- | -----------: |
| CSV    | `8ca30832-3159-47cc-b604-ea506cceef28` | `/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/8ca30832-3159-47cc-b604-ea506cceef28.csv` |       5292 | `shared_saved_layout` |           17 |
| PDF    | `33397b0d-68d0-44fb-ad5f-6009cc246a2b` | `/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/33397b0d-68d0-44fb-ad5f-6009cc246a2b.pdf` |     221012 | `shared_saved_layout` |           17 |
| PNG    | `1215d72c-9d6e-4d0b-a8a8-85cff889c343` | `/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/1215d72c-9d6e-4d0b-a8a8-85cff889c343.png` |     152293 | `shared_saved_layout` |           17 |

Scheduled dry-run evidence:

- Job ID: `2fc0730b-51ca-429c-9be6-92a31a211ec0`
- Format: PDF
- Status: `completed`
- Delivery status: `mode=dry_run`, `status=rendered`, `sanitized=true`
- Artifact byte count: `220940`
- Layout source: `shared_saved_layout`
- Governed widget append count: `17`

Post-export bundle/parity/validation files were written to:

- `/tmp/adinsights-slb-20260628-current-state/evidence-bundle-after-export.json`
- `/tmp/adinsights-slb-20260628-current-state/parity-comparison-after-export.json`
- `/tmp/adinsights-slb-20260628-current-state/validation-after-export.json`

After tightening the validator so scheduled dry-runs cannot be selected as completed export proof,
the same post-export evidence was regenerated to:

- `/tmp/adinsights-slb-20260628-current-state/evidence-bundle-after-export-manual-selected.json`
- `/tmp/adinsights-slb-20260628-current-state/parity-comparison-after-export-manual-selected.json`
- `/tmp/adinsights-slb-20260628-current-state/validation-after-export-manual-selected.json`

The current validator sees completed non-empty manual CSV/PDF/PNG evidence and layout proof. The
selected completed export inventory is CSV `5292` bytes, PDF `221012` bytes, and PNG `152293` bytes.
The scheduled dry-run PDF remains present at `220940` bytes, but is counted only as rendered
scheduled dry-run evidence. Validation remains blocked only by parity/source-value requirements:

```json
{
  "readiness_status": "blocked",
  "blocker_count": 2,
  "warning_count": 6,
  "blocker_codes": ["parity_results"],
  "parity_summary": {
    "blocked_missing_adinsights_value": 1,
    "blocked_missing_source_value": 8
  },
  "blocking_next_actions": {
    "action_count": 4,
    "ready_to_run_action_count": 0,
    "blocked_prerequisite_count": 4
  }
}
```

The 2026-06-28 Gmail/Drive rechecks increased `source_search_provenance_count` to 7 but did not add
approved parity values. The remaining blocking actions are still selected-account paid source export,
approved aggregate Page/Post source values, tenant-owned SLB Page selection before Page Follows import,
and approved Content Ops source totals.

Earlier bundle/parity/validation files were written under
`/tmp/adinsights-slb-20260626-warning-paid-rerun/`. Offline validation was blocked only by parity:

```json
{
  "readiness_status": "blocked",
  "blocker_count": 2,
  "warning_count": 6,
  "blockers": [
    {
      "code": "parity_results",
      "message": "Parity comparison must include at least one passing row."
    },
    {
      "code": "parity_results",
      "message": "Parity has unresolved rows: {'blocked_metric_semantics': 4, 'blocked_missing_dashthis_value': 5}."
    }
  ]
}
```

This JSON block is superseded by the current `/tmp/adinsights-slb-parity-20260626/` validation
summary above. Keep it only as historical context for the warning-paid rerun, not as the current
parity state.

## Earlier Warning Run Commands (Superseded)

```bash
backend/.venv/bin/python backend/manage.py slb_report_evidence_bundle \
  --report-id 09c96ea9-a9e5-4283-aa29-401179ab05dc \
  --start-date 2026-05-01 \
  --end-date 2026-05-31 \
  > /tmp/adinsights-slb-20260626-export-warning/evidence-bundle.json

backend/.venv/bin/python backend/manage.py slb_report_parity_evidence \
  --report-id 09c96ea9-a9e5-4283-aa29-401179ab05dc \
  --start-date 2026-05-01 \
  --end-date 2026-05-31 \
  --format json \
  > /tmp/adinsights-slb-20260626-export-warning/parity-evidence.json

backend/.venv/bin/python backend/manage.py slb_report_evidence_validate \
  --evidence-bundle /tmp/adinsights-slb-20260626-export-warning/evidence-bundle.json \
  --expected-start-date 2026-05-01 \
  --expected-end-date 2026-05-31 \
  --format json \
  > /tmp/adinsights-slb-20260626-export-warning/validation-no-parity-after-validator-fix.json
```

The raw JSON files were left in `/tmp` and not committed.

## Earlier Warning Run Summary (Superseded)

- Preview hash: `75e9686a0e96ad17dc7f575fd47b25b9e714a20ab5aecc078cd2bb79fe89a064`.
- `export_ready=true`.
- `blocking_reasons=[]`.
- Coverage warnings:
  - the earlier unpinned warning run saw tenant-level paid rows outside the selected SLB account scope
    for `2026-05-02` through `2026-05-31`; those rows are non-SLB/out-of-scope for the fixed report
    and must not be treated as selected-account paid coverage.
  - Facebook Page Insights stored rows have no retained rows for the requested range.
  - Facebook Page synced posts have no retained rows for the requested range.
  - Content Ops imported post activity has no retained rows for the requested range.
- Parity evidence generated 55 aggregate rows. Every row is
  `blocked_missing_dashthis_value` because no real May 2026 DashThis/source comparison values were
  found locally.

## Earlier Export Artifacts (Superseded)

All listed export rows are completed, non-empty, and carry that run's preview hash and snapshot
preview hash.

| Format | Job ID                                 | Artifact path                                                                                                                 | Byte count |
| ------ | -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ---------: |
| CSV    | `5b06fb04-47c8-494e-a00c-15f27be923fb` | `/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/5b06fb04-47c8-494e-a00c-15f27be923fb.csv` |      31520 |
| PDF    | `9d42aceb-e807-41f9-8c5d-4b8a727927a8` | `/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/9d42aceb-e807-41f9-8c5d-4b8a727927a8.pdf` |     416132 |
| PNG    | `31c9416d-2d80-4c20-86ce-0246f4b832db` | `/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/31c9416d-2d80-4c20-86ce-0246f4b832db.png` |    1137698 |

Scheduled dry-run evidence:

- Job ID: `5ce2f2f0-b0e6-4081-a7e9-951af3358986`
- Format: PDF
- Status: `completed`
- Delivery status: `mode=dry_run`, `status=rendered`, `sanitized=true`
- Artifact byte count: 416140

## Validator Result

After updating `slb_report_evidence_validate` to honor the SLB template warning-only export policy
and ignore stale historical export rows from older preview hashes, the fixed-target bundle validates
with only the expected parity blocker:

```json
{
  "readiness_status": "blocked",
  "blocker_count": 1,
  "warning_count": 5,
  "blockers": [
    {
      "code": "parity",
      "message": "Parity comparison artifact is required."
    }
  ]
}
```

Passed checks: bundle schema, custom date range, required datasets, source health, rendering,
current-hash exports plus scheduled dry-run, Instagram deferral, and sensitive-payload scan.

## 2026-06-28 Client-Facing Export Template Rerun

After polishing the `report_v1_snapshot` PDF/PNG shell, the fixed SLB target was regenerated with
the same report scope:

```bash
backend/.venv/bin/python backend/manage.py slb_report_export_evidence \
  --report-id 09c96ea9-a9e5-4283-aa29-401179ab05dc \
  --start-date 2026-05-01 \
  --end-date 2026-05-31 \
  > /tmp/adinsights-slb-20260628-client-export/export-evidence.json
```

Generated evidence artifacts:

- Export run: `/tmp/adinsights-slb-20260628-client-export/export-evidence.json`
- Evidence bundle: `/tmp/adinsights-slb-20260628-client-export/evidence-bundle.json`
- Parity comparison:
  `/tmp/adinsights-slb-20260628-client-export/parity-comparison.json`
- Offline validation: `/tmp/adinsights-slb-20260628-client-export/validation.json`

Run summary:

- Preview hash:
  `69f5117e93e3883958596f479a0a73dd951ed94eabc50a5a6e5cf29054836344`
- `export_ready=true`
- `blocking_reasons=[]`
- Completed manual exports all use `source=report_v1_snapshot`,
  `report_layout_source=shared_saved_layout`, and
  `report_layout_governed_widget_append_count=17`.

| Format | Job ID                                 | Artifact path                                                                                                                 | Byte count |
| ------ | -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ---------: |
| CSV    | `e89f3977-5c25-4436-8b23-41440a9ea5ff` | `/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/e89f3977-5c25-4436-8b23-41440a9ea5ff.csv` |       5292 |
| PDF    | `4802fd3f-0bf3-458e-8911-c67382910ed6` | `/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/4802fd3f-0bf3-458e-8911-c67382910ed6.pdf` |     242725 |
| PNG    | `2a348f3e-6c10-4fe9-9c01-e3b6509569ff` | `/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/2a348f3e-6c10-4fe9-9c01-e3b6509569ff.png` |     164000 |

Scheduled dry-run evidence remains separate from completed export proof:

- Job ID: `a6b59cc1-3515-4607-9fd3-17b8a82b9d52`
- Format: PDF
- Status: `completed`
- Delivery status: `mode=dry_run`, `status=rendered`, `sanitized=true`
- Artifact byte count: 242479
- Layout evidence: `report_layout_source=shared_saved_layout`,
  `report_layout_governed_widget_append_count=17`

Validation summary:

- `readiness_status="blocked"`
- `blocker_count=2`
- `warning_count=6`
- Selected completed exports are the fresh manual CSV/PDF/PNG rows above, not the scheduled dry-run.
- Remaining blockers are parity/source prerequisites only:
  - parity must include at least one passing row;
  - unresolved parity rows remain
    `{"blocked_missing_adinsights_value": 1, "blocked_missing_source_value": 8}`.
- `blocking_next_actions` contains four non-runnable prerequisite groups:
  selected-account paid source export, approved aggregate organic Page/Post source values,
  tenant-owned SLB Page selection before organic import, and approved Content Ops source totals.

Visual check:

- Inspected
  `/Users/thristannewman/ADinsights/integrations/exporter/out/exports/ee1c8c78-d77f-4c65-ad37-ccf7a896f4c2/09c96ea9-a9e5-4283-aa29-401179ab05dc/2a348f3e-6c10-4fe9-9c01-e3b6509569ff.png`.
- The PNG is nonblank and uses the client-facing monthly report shell. It shows the "Monthly client
  report" header, visible data availability notes, saved-layout widgets, and the reach/impressions
  availability explanation. No obvious overlap or clipped content was visible in the rendered
  artifact.

No new DashThis/source values were added in this rerun, and no missing values were inferred.

## 2026-06-28 Source Recheck Parity Rerun

After the narrowed Drive/Gmail source recheck at `2026-06-28T18:00:15-0500`, the parity and
validation commands were rerun against the same client-facing evidence bundle:

```bash
backend/.venv/bin/python backend/manage.py slb_report_parity_compare \
  --evidence-bundle /tmp/adinsights-slb-20260628-client-export/evidence-bundle.json \
  --comparison-values docs/project/evidence/dashthis-replacement/2026-06-26-slb-may-source-comparison-values.json \
  > /tmp/adinsights-slb-20260628-source-recheck/parity-comparison.json

backend/.venv/bin/python backend/manage.py slb_report_evidence_validate \
  --evidence-bundle /tmp/adinsights-slb-20260628-client-export/evidence-bundle.json \
  --parity-comparison /tmp/adinsights-slb-20260628-source-recheck/parity-comparison.json \
  --expected-start-date 2026-05-01 \
  --expected-end-date 2026-05-31 \
  > /tmp/adinsights-slb-20260628-source-recheck/validation.json
```

Rerun summary:

- `source_search_provenance_count=7`
- Parity result summary remains
  `{"blocked_missing_adinsights_value": 1, "blocked_missing_source_value": 8}`.
- Validation remains `readiness_status="blocked"` with `blocker_count=2` and `warning_count=6`.
- Missing source value count remains 8; unmatched source value count remains 11.
- `blocking_next_actions` still contains four non-runnable prerequisite groups:
  selected-account paid source export, approved aggregate Page/Post source values, tenant-owned SLB
  Page selection before Page Follows import, and approved Content Ops source totals.

The recheck added search provenance only. No source values were invented or promoted from proposals,
partial receipts, top-post examples, creative files, or operational task artifacts.

## 2026-06-28 Parity Next-Action Payload Rerun

After `slb_report_parity_compare` was corrected to emit the same summarized
`blocking_next_actions` payload as the validator, parity and validation were rerun against the same
client-facing evidence bundle:

```bash
backend/.venv/bin/python backend/manage.py slb_report_parity_compare \
  --evidence-bundle /tmp/adinsights-slb-20260628-client-export/evidence-bundle.json \
  --comparison-values docs/project/evidence/dashthis-replacement/2026-06-26-slb-may-source-comparison-values.json \
  > /tmp/adinsights-slb-20260628-blocking-actions-fix/parity-comparison.json

backend/.venv/bin/python backend/manage.py slb_report_evidence_validate \
  --evidence-bundle /tmp/adinsights-slb-20260628-client-export/evidence-bundle.json \
  --parity-comparison /tmp/adinsights-slb-20260628-blocking-actions-fix/parity-comparison.json \
  --expected-start-date 2026-05-01 \
  --expected-end-date 2026-05-31 \
  > /tmp/adinsights-slb-20260628-blocking-actions-fix/validation.json
```

Rerun summary:

- Parity result summary remains
  `{"blocked_missing_adinsights_value": 1, "blocked_missing_source_value": 8}`.
- Parity now carries `blocking_next_actions.action_count=4`,
  `ready_to_run_action_count=0`, and `blocked_prerequisite_count=4`.
- The four parity next-action codes are:
  `approved_selected_account_paid_source_export_required`,
  `approved_organic_page_post_source_values_required`,
  `tenant_owned_slb_page_required_for_organic_import`, and
  `approved_content_ops_source_totals_required`.
- Validation remains `readiness_status="blocked"` with `blocker_count=2`,
  `warning_count=6`, and the same four non-runnable blocking next actions.

This rerun restores the parity artifact's reviewer-facing next-action summary. It does not change
any source value, ADinsights value, export artifact, or DashThis cancellation status.

## Remaining Blocker

SLB-004/G6 has been run with the source values that are currently available, and it is still blocked.
Do not claim parity completion or proceed to G10/G11/G12 until there is at least one substantive
passing parity row and the validator returns `readiness_status="pass"` with `blocker_count=0`.

The remaining data prerequisites are:

- create or restore the actual SLB Meta Page row, then backfill/import approved organic Page values
  into that Page instead of the local `AdTelligent` Page;
- reconnect/select the scoped SLB ad account `act_791712443035541` and run paid May backfill, or
  import an approved daily Meta paid CSV for that exact account;
- provide real May 2026 Content Ops totals for published posts and content items created, or import
  the matching Content Ops snapshots;
- provide approved aggregate Facebook Page/Post source values for post reactions, comments, and
  shares, or preserve reviewed top-post examples as unmatched values when they cannot represent
  monthly totals.

Next safe command after receiving a fuller real comparison file or importing approved source rows:

```bash
backend/.venv/bin/python backend/manage.py slb_report_parity_compare \
  --evidence-bundle /tmp/adinsights-slb-parity-20260626/evidence-bundle.json \
  --comparison-values <real-comparison-values.json> \
  --format json \
  > /tmp/adinsights-slb-parity-20260626/parity-comparison.json
```

Then rerun `slb_report_evidence_validate` with `--parity-comparison`. Do not proceed to G10/G11/G12
unless the validator returns `readiness_status="pass"` and `blocker_count=0`.
