# G0 Raj/Mira Review Packet - SLB Cancellation Readiness

Date: 2026-06-16
Timezone: America/Jamaica
Goal ID: G0
Status: review pending
Decision requested: classify and clear the cross-stream architecture scope for continuing SLB
DashThis cancellation-readiness evidence work. Do not approve DashThis cancellation from this packet.

Machine-readable decision template:

`docs/project/evidence/dashthis-replacement/2026-06-16-g0-raj-mira-review-decision.template.json`

Validate a filled Raj/Mira decision:

```bash
python3 scripts/validate_slb_g0_raj_mira_review.py \
  --review-file <filled-g0-raj-mira-review-decision.json>
```

The validator checks Raj and Mira decisions, scope and architecture classification, whether G1-G11
evidence capture may proceed, reviewer routes, preflight interpretation, DashThis no-go status, and
sensitive-value hygiene.

## 2026-06-17 Local Runtime Addendum

After this packet was created, the local browser-visible SLB report was exercised at:

```text
https://localhost:5173/reports/a40abad9-9f1d-4e75-92b0-3e0feaed27b5
```

The local report proves useful implementation behavior, but it does not close G0 or G1:

- The `report.v1` route renders an SLB monthly report shell in the frontend.
- The preview uses stored aggregate data and visible coverage states.
- Paid Meta Ads renders retained aggregate rows, currently `source_disconnected`.
- Organic Facebook/Page and Content Ops correctly show `missing_history`/empty states for the local
  requested range.
- Export actions are present, and the report-level badge now shows `export with warnings` when
  export can run but coverage is stale, missing, partial, or disconnected.
- Desktop/mobile Playwright screenshots were captured under ignored local `output/playwright/`.

Local proof documents:

- `docs/project/evidence/dashthis-replacement/2026-06-17-local-browser-render-export-proof.md`
- `docs/project/evidence/dashthis-replacement/2026-06-17-local-demo-to-fixed-target-bridge.md`
- `docs/project/evidence/dashthis-replacement/2026-06-17-local-visual-render-proof.md`

Raj/Mira should treat this as implementation smoke evidence only. It is not DashThis parity
evidence, not a fixed G1 target, and not cancellation-review readiness.

## Scope Being Reviewed

ADinsights has implemented the first SLB reporting and reporting-ops slices:

- Governed `dashboard.v1` validation/rendering.
- Governed `report.v1` validation/rendering.
- Reporting catalog endpoint.
- Widget preview endpoint using stored aggregate data.
- Report preview endpoint using stored aggregate widget previews.
- Export coverage metadata and durable report snapshots.
- Diagnostics endpoint for support-safe retained-history/freshness/export states.
- Scheduled delivery dry-run evidence path.
- SLB parity evidence command.
- Report action privileges, audit events, and conservative quotas.
- Frontend Report Detail preview, coverage, diagnostics, snapshot, and dry-run UI.

The active cancellation-readiness goal remains SLB Monthly Social Report without Instagram in v1.
Instagram stays deferred unless source rows, scopes, metric catalog entries, and reviewer approval
are proven.

## Guardrails To Confirm

- Report preview/export must use stored aggregate ADinsights data only.
- No live Meta/Facebook/provider calls may occur during report preview/export.
- Tenant isolation must remain enforced for report, dashboard, widget preview, diagnostics, export,
  scheduled dry-run, and parity evidence paths.
- No user-level metrics, secrets, OAuth tokens, raw provider payloads, or sensitive artifact paths
  may appear in diagnostics, parity evidence, exports, logs, or support packets.
- Legacy dashboard/report layouts without `schema_version` must remain compatible.
- DashThis cancellation remains no-go until G0-G11 pass and G12 recommends cancellation.

## Current Gate Evidence

Latest preflight command:

```bash
make adinsights-preflight PROMPT="Assess SLB DashThis cancellation-readiness G0 G1 review and fixed-target intake"
```

Result captured 2026-06-16:

- Router action: `clarify`
- Scope status: `ESCALATE_ARCH_RISK`
- Contract status: `WARN_POSSIBLE_CONTRACT_CHANGE`
- Release status: `GATE_BLOCK`
- Contract executed: `True`
- Output directory: `/var/folders/4k/xdt2s05j1tl9zpyxhwtt8pk80000gn/T/adinsights-preflight-output-tjwl5mjo`

Persisted packet set:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake/README.md`
- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake/router-packet.json`
- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake/scope-packet.json`
- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake/contract-packet.json`
- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake/release-packet.json`

Checked persisted packet set:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake-with-checks/README.md`
- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake-with-checks/router-packet.json`
- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake-with-checks/scope-packet.json`
- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake-with-checks/contract-packet.json`
- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake-with-checks/release-packet.json`

Checked preflight delta:

- `data_contract_gate` passed.
- `observability_prereqs` passed.
- `production_readiness` failed because `AIRBYTE_TEMPLATE_META_METRICS_CONNECTION_ID` is required
  to bootstrap connections.

Blocking issue:

- Scope control gate blocked by architecture-level scope risk.
- Checked run also blocks test coverage because optional production readiness failed.

Warnings:

- Contract integrity requires follow-up before release.
- Security/PII gate requires verification due to sensitive signals.

Interpretation:

- This remains a cross-stream architecture/release-governance block, not evidence that the
  reporting runtime failed.
- Raj/Mira must decide whether G1-G11 fixed-range evidence capture can proceed and whether the
  contract/security warnings are covered by the current reviewer route or need additional work.

Prior preflight command:

```bash
make adinsights-preflight PROMPT="Assess SLB DashThis cancellation-readiness G0 Raj Mira scope and architecture review"
```

Prior result:

- Router action: `resolve`
- Scope status: `ESCALATE_ARCH_RISK`
- Contract status: `WARN_POSSIBLE_CONTRACT_CHANGE`
- Release status: `GATE_BLOCK`
- Contract executed: `True`
- Output directory: `/var/folders/4k/xdt2s05j1tl9zpyxhwtt8pk80000gn/T/adinsights-preflight-output-dszwbaay`

Blocking issue:

- Scope control gate blocked by architecture-level scope risk.

Warnings:

- Contract integrity requires follow-up before release.
- Security/PII gate requires verification due to sensitive signals.

Prior interpretation:

- This is a cross-stream architecture/release-governance block, not a unit-test failure.
- Raj/Mira must decide whether the implemented reporting-ops scope can proceed to fixed-range SLB
  evidence capture and whether any architecture changes are required before G1-G11.

## Prior Local Gate Evidence

The reporting-ops implementation previously ran these gates successfully:

- `make backend-lint`
- `make backend-test`
- `make frontend-guardrails`
- `make frontend-lint`
- `make frontend-test`
- `make frontend-build`
- `scripts/dev-healthcheck.sh`
- `backend/.venv/bin/python backend/manage.py backend_release_preflight`

Known local smoke caveat:

- `backend/.venv/bin/python backend/manage.py backend_release_smoke --strict-observability` was
  blocked by missing local `/metrics/app/` queue label samples for `sync`, `snapshot`, and `summary`.
  This should be treated as local observability evidence not yet ready, not as proof that the SLB
  reporting implementation failed.

## Raj Review Questions

Raj should answer:

1. Is the current scope acceptable as a cross-stream reporting cancellation-readiness track?
2. Can the team proceed to G1-G11 evidence capture without splitting the already implemented
   backend/frontend/docs reporting-ops slice into smaller review tracks first?
3. Are the required reviewer routes correct for Sofia, Andre, Lina, Joel, Omar, Hannah, Nina, and
   Priya/Martin when retention gaps appear?
4. Does the DashThis cancellation gate remain correctly separated from implementation completion?
5. What evidence is required before G12 can recommend keep/cancel DashThis?

## Mira Review Questions

Mira should answer:

1. Is the architecture direction acceptable: governed catalog, versioned `dashboard.v1`/`report.v1`,
   stored aggregate previews, durable report snapshots, diagnostics, and scheduled dry-run evidence?
2. Is `ReportExportJob.metadata.report_snapshot` acceptable as the v1 snapshot store, or does the
   next sprint need a dedicated model before hardening?
3. Are preview/export/diagnostics consistency rules strong enough to prevent stale or partial data
   being misrepresented?
4. Are schema-versioning and legacy layout compatibility handled sufficiently for continuing
   evidence work?
5. Are there architecture blockers before fixed-range parity, export, delivery, and hardening
   evidence can continue?

## Requested G0 Decision

G0 can move from `review_pending` to `passed` only when Raj/Mira record:

- Scope classification.
- Architecture classification.
- Whether G1-G11 may proceed.
- Required follow-up reviewers or blockers.
- Explicit statement that DashThis cancellation remains no-go until G12.

If Raj/Mira require runtime changes before G1-G11, mark G0 as `failed_or_blocked` and create the
specific implementation/handoff item instead of proceeding to parity evidence.

## Next Sub-Goal After G0

After G0 is cleared or explicitly classified, proceed to G1:

- Choose fixed SLB proof target.
- Record tenant/client, report ID, template key, fixed reporting date range, and recipient
  assumptions.
- Keep Instagram deferred unless readiness is proven.
