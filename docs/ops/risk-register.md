# Risk Register (v0.1)

Purpose: track operational, security, and delivery risks with owners and mitigations.

| Risk                                     | Impact | Likelihood | Owner      | Mitigation                                      | Status |
| ---------------------------------------- | ------ | ---------- | ---------- | ----------------------------------------------- | ------ |
| Incomplete live-data filtering           | High   | Medium     | Sofia/Lina | Wire filters end-to-end; add API contract tests | Open   |
| Airbyte connector gaps (LinkedIn/TikTok) | Medium | Medium     | Maya       | Implement connectors; validate schemas          | Open   |
| Snapshot staleness undetected            | High   | Medium     | Omar       | Freshness alert + runbook updates               | Open   |
| Data quality regressions                 | High   | Medium     | Priya      | dbt tests + data quality checklist              | Open   |
| Secrets leakage                          | High   | Low        | Nina       | Enforce KMS, log scrubbing, audits              | Open   |
| Release rollback gaps                    | High   | Low        | Carlos     | Expand runbook + checklist                      | Open   |

Update this table when risks change or mitigation completes.
