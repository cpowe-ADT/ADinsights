# External Actions Register (AWS)

Purpose: canonical checklist for operator-owned actions that cannot be completed from local repo automation. Use this to move ADinsights from laptop-only execution to AWS staging/production readiness.

Who should use this:
- Release lead (Mei)
- Platform/infra owners (Victor, Nina)
- Integrations owners (Maya, Leo)
- Observability owners (Omar, Hannah)
- Review/approval owners (Raj, Mira)

Timezone: `America/Jamaica`.

## Preconditions

1. AWS account access to target staging/production accounts.
2. DNS management access for `adtelligent.net` records.
3. Access to monitoring stack (Datadog/CloudWatch + Slack/email/pager integrations).
4. Access to Airbyte target workspace and production credential vault.
5. GitHub repository access for PR review/sign-off evidence.

## External Actions Table

| ID | Action | System | Owner | Exact steps | Evidence required | Done when |
| --- | --- | --- | --- | --- | --- | --- |
| `S7-D` | SES sender readiness | AWS SES + DNS | Mei + Nina | 1) Verify SES identity for `adtelligent.net`. 2) Enable DKIM and validate all CNAMEs. 3) Confirm SPF/DMARC alignment in DNS. 4) Request and verify SES sandbox exit. 5) Set final `EMAIL_FROM_ADDRESS` + `SES_EXPECTED_FROM_DOMAIN`. 6) Run invite/password-reset smoke checks. | Completed `ses-verification-<date>-est.md` using template + screenshots/headers of successful deliveries. | Domain verified, DKIM valid, SPF/DMARC aligned, account out of sandbox, invite/password-reset delivered from approved sender. |
| `P1-X1` | KMS production provisioning + env wiring | AWS KMS + Secrets Manager/SSM | Nina + Victor | 1) Create CMK and alias (`alias/adinsights-prod`). 2) Ensure key policy allows backend/worker/beat roles. 3) Set `KMS_PROVIDER=aws`, `KMS_KEY_ID=<alias-or-arn>`, `AWS_REGION` in secret manager. 4) Deploy settings update to target env. 5) Run DEK rotation dry run and one scoped rotation verification. | Completed `kms-provisioning-<date>-est.md` with key/alias metadata (redacted), policy confirmation, and dry-run output. | App boots with AWS KMS config and DEK rotation validates with no secret leakage in logs. |
| `P1-X2` | Airbyte production credential readiness | Airbyte UI/API + secret store | Maya + Leo | 1) Load real Meta/Google credentials from secure store into target env. 2) Confirm tenant/workspace mappings. 3) Run `validate_tenant_config.py`. 4) Run `verify_production_readiness.py`. 5) Run `airbyte_health_check.py`. 6) Trigger one controlled sync and inspect telemetry. | Completed `airbyte-prod-readiness-<date>-est.md` with command outputs and connection IDs (redacted). | Scripts pass and one production-like sync reports healthy telemetry. |
| `P1-X4` | Observability alert simulation | Datadog/CloudWatch/PagerDuty + Slack/email | Omar + Hannah | Execute all scenarios from `docs/runbooks/observability-alert-simulations.md` in staging, including consecutive failures, empty sync, stale Airbyte health, stale dbt health; verify routing and acknowledgment. | Completed `observability-simulation-<date>-est.md` with alert IDs, timestamps, route targets, and ack links/screenshots. | All required alerts fire within expected detection windows and route to on-call channels. |
| `P1-X9` | Staging go/no-go rehearsal | AWS staging + Airbyte + dbt + backend/frontend | Mei + Raj | 1) Run full release checklist in staging. 2) Validate health endpoints and smoke flows. 3) Validate rollback path (task revision rollback + migration fallback guidance). 4) Record decisions and open risks. | Completed `staging-rehearsal-<date>-est.md` plus linked command outputs and screenshots. | End-to-end rehearsal passes or only approved, documented risks remain. |
| `P1-X5-signoff` | Cross-stream release sign-offs | GitHub PRs + release gate docs | Raj + Mira | 1) Review cross-folder PR set. 2) Add explicit Raj integration comment and Mira architecture comment. 3) Link comments in gate evidence doc. 4) Mark closeout decision (`READY` or `READY_PENDING_EXTERNALS`). | PR links + reviewer comments captured in release gate evidence file. | Raj and Mira sign-off references are present and linked from release gate. |

## AWS Bootstrap Sequence (Laptop -> Staging -> Production)

1. **Local parity**
   - Keep repo checks green:
     - `ruff check backend && pytest -q backend`
     - `python3 infrastructure/airbyte/scripts/check_data_contracts.py`
     - `python3 infrastructure/airbyte/scripts/verify_observability_prereqs.py`
     - `cd infrastructure/airbyte && docker compose config`
2. **Staging infrastructure baseline**
   - Provision/update VPC, RDS, Redis, ECS services, Airbyte dependencies, secret stores.
   - Deploy current `main` to staging.
3. **Staging external actions**
   - Run `P1-X1`, `P1-X2`, `P1-X4`, `P1-X9` with staging-scoped credentials and alert routes.
4. **Production cutover prerequisites**
   - Complete `S7-D` SES and production KMS/credential validations.
   - Confirm runbooks, evidence, and sign-offs are current.
5. **Production rollout**
   - Deploy tagged release.
   - Run production smoke and observe alert baselines.
   - Record closure decision in release evidence.

## Troubleshooting

1. **SES still sandboxed**
   - Check support case status and verify region-specific SES account state.
2. **KMS decrypt errors on startup**
   - Validate task role permissions (`kms:Decrypt`, `kms:GenerateDataKey`) and key policy trust.
3. **Airbyte readiness script failures**
   - Verify workspace IDs, source auth scopes, and refresh-token validity.
4. **Alerts not firing**
   - Confirm metric/log ingestion pipeline health first, then verify monitor query scope and thresholds.
5. **Sign-off missing near release**
   - Block merge, request Raj/Mira review on cross-folder PRs, and attach links in release gate evidence.

External production actions must be tracked in `docs/runbooks/external-actions-aws.md`.
