# External Prerequisites Checklist

Use this before Phase 1. Record owners and evidence paths, not secret values. Do not paste OAuth
tokens, client secrets, webhook URLs, API keys, KMS key material, SMTP passwords, or Airbyte tokens.

## Immediate External Actions For SLB Cancellation Readiness

| #   | Owner                                    | Required action                                                                                                                                                  | Evidence path/status                                                                 |
| --- | ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| 1   | Raj + Mira                               | Classify the G0 architecture/scope `GATE_BLOCK` and decide whether G1-G11 fixed-target evidence capture can proceed.                                             | `2026-06-16-g0-g1-review-target-intake.md`                                           |
| 2   | Operator + Hannah                        | Fill the G1 fixed SLB runtime target: environment, URLs, safe tenant/client, report ID, date range, source scopes, delivery assumptions, DashThis active status. | `2026-06-16-g1-runtime-target-intake-checklist.md`                                   |
| 3   | DashThis/source comparison owner + Andre | Provide safe fixed-range DashThis/source comparison values and tolerances for all required non-Instagram metrics.                                                | `2026-06-16-g6-parity-worksheet-proof.md`; `source-platform-comparison-worksheet.md` |
| 4   | Carlos/Mei or runtime owner + Raj/Mira   | Resolve the non-secret Airbyte Meta metrics template connection prerequisite or approve an alternative bootstrap path.                                           | This checklist; checked G0/G1 preflight packet                                       |

## Target Runtime

- Environment:
- Backend URL:
- Frontend URL:
- Airbyte workspace:
- Target tenant/client:
- First proof date range:
- Operator:
- Evidence timestamp:

## Access And Ownership

| Prerequisite                             | Owner | Required action                                                                                                                        | Evidence path                                                                                                      | Status  |
| ---------------------------------------- | ----- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ------- |
| Meta app admin access                    | TBD   | Confirm app, redirect URIs, review state, and active scopes.                                                                           | TBD                                                                                                                | blocked |
| Meta target ad account access            | TBD   | Confirm tenant ad account IDs and reporting permission.                                                                                | TBD                                                                                                                | blocked |
| Google Ads OAuth access                  | TBD   | Confirm OAuth client and refresh-token path without exposing secrets.                                                                  | TBD                                                                                                                | blocked |
| Google Ads developer token               | TBD   | Confirm approved token and target customer access.                                                                                     | TBD                                                                                                                | blocked |
| Airbyte workspace access                 | TBD   | Confirm workspace, source definition IDs, destination, and connection IDs.                                                             | TBD                                                                                                                | blocked |
| Airbyte Meta metrics template connection | TBD   | Provide a non-secret `AIRBYTE_TEMPLATE_META_METRICS_CONNECTION_ID` for the target runtime or record an approved bootstrap alternative. | `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake-with-checks/README.md` | blocked |
| Warehouse/dbt runtime                    | TBD   | Confirm target profile and dbt execution path.                                                                                         | TBD                                                                                                                | blocked |
| KMS provider                             | TBD   | Confirm production-equivalent KMS configuration for encrypted channel secrets.                                                         | TBD                                                                                                                | blocked |
| SES sender/domain                        | TBD   | Confirm identity, DKIM, SPF/DMARC, sandbox exit, and final from address.                                                               | TBD                                                                                                                | blocked |
| DNS                                      | TBD   | Confirm production/staging hostnames and email DNS records.                                                                            | TBD                                                                                                                | blocked |
| Slack/webhook destination                | TBD   | Confirm only if DashThis replacement needs it. Do not store raw destination URLs here.                                                 | TBD                                                                                                                | blocked |
| Scheduled report recipients              | TBD   | Confirm recipient emails and consent.                                                                                                  | TBD                                                                                                                | blocked |

## Environment Flags To Verify

| Flag                                          | Required replacement value                                                                                                             | Evidence path                                                                                                      | Status  |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ------- |
| `VITE_MOCK_MODE`                              | `false`                                                                                                                                | TBD                                                                                                                | blocked |
| `ENABLE_WAREHOUSE_ADAPTER`                    | `1`                                                                                                                                    | TBD                                                                                                                | blocked |
| `ENABLE_FAKE_ADAPTER`                         | `0`                                                                                                                                    | TBD                                                                                                                | blocked |
| `ENABLE_DEMO_ADAPTER`                         | Allowed only for fallback/demo, not replacement proof.                                                                                 | TBD                                                                                                                | blocked |
| `AIRBYTE_TEMPLATE_META_METRICS_CONNECTION_ID` | Target-runtime Airbyte Meta metrics template connection ID, or approved non-template bootstrap path. Do not store Airbyte tokens here. | `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake-with-checks/README.md` | blocked |

## Phase 1 Go/No-Go

Phase 1 can start only when the target runtime, proof tenant/client, and credential owners are named.
Phase 1 cannot exit until each prerequisite is verified or explicitly blocked with an owner,
required action, and evidence path.

## Current Production-Readiness Blocker

The checked G0/G1 release-readiness packet records `data_contract_gate` and `observability_prereqs`
as passing, but `production_readiness` fails because
`AIRBYTE_TEMPLATE_META_METRICS_CONNECTION_ID` is required to bootstrap connections.

Fresh local rerun on 2026-06-16 produced the same production-readiness failure. The data-contract
gate and observability prerequisite gate pass, while
`python3 infrastructure/airbyte/scripts/verify_production_readiness.py` still returns
`AIRBYTE_TEMPLATE_META_METRICS_CONNECTION_ID is required to bootstrap connections`.

This value is an external runtime configuration prerequisite, not a secret to paste into this
document. Before G11 hardening or G12 cancellation recommendation, record either:

- the safe evidence path showing the target runtime has the required Airbyte template connection
  configured, or
- a Raj/Mira-approved alternative bootstrap path that makes the production-readiness check pass.
