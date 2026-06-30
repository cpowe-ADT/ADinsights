# Usable Pilot Delivery Specification

Status: Repository implementation complete; staging activation and required review pending
Approved scope date: 2026-05-26
Timezone: America/Jamaica

This document is the authoritative delivery checklist for making the current ADinsights
product usable for a live pilot. Where older backlog text conflicts with this specification,
this specification controls until the pilot milestones are closed or deliberately revised.

## Pilot Goal

A tenant can connect live Meta and Google Ads data, review aggregated dashboards, download real
CSV/PDF/PNG report artifacts, configure alert delivery without storing webhook secrets in
plaintext, and receive the scheduled daily summary email. Operators can then complete staging
evidence and issue a go/no-go decision.

## Scope And Review Route

- Required pilot sources: Meta and Google Ads.
- Deferred from pilot acceptance: GA4 live onboarding, Search Console tenant onboarding,
  additional ad networks, and additional notification channel types.
- Data policy: exports, alerts, and summaries use aggregated advertising metrics only.
- Security policy: Slack/webhook URLs, authentication headers, and tokens are encrypted using
  tenant DEKs wrapped by the configured KMS provider; they are never returned or logged.
- This delivery touches `docs/`, `backend/`, `frontend/`, and `integrations/exporter/`; it
  requires Raj cross-stream review and Mira architecture review, with Sofia, Nina, Lina, and Omar
  reviewing their owned surfaces.

## Verified Current State

| Capability                                                                   | State at audit                                                     | Delivery requirement                                                                  |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------- |
| Tenant auth, dashboards, metrics snapshots, alert/rule UI, operations routes | Working in code                                                    | Preserve tenant isolation and existing response compatibility.                        |
| Meta and Google Ads ingestion/runtime paths                                  | Working in code; live credential evidence pending                  | Require staging sync and dashboard evidence during activation.                        |
| Generic report exports                                                       | Broken at audit; repository fix verified                           | Jobs now create non-empty aggregate CSV/PDF/PNG artifacts or fail honestly.           |
| Meta Page export rendering                                                   | Working renderer/CLI available; macOS launch portability corrected | Shared renderer produces PDF/PNG artifacts locally and retains Linux deployment path. |
| Alert notification delivery                                                  | Partially working at audit; repository fix verified                | Slack/webhook secrets are encrypted and API/UI surfaces are redacted.                 |
| Scheduled daily summaries                                                    | Stubbed delivery at audit; repository fix verified                 | Summaries send through active tenant email notification channels.                     |
| Local release evidence                                                       | Strict smoke requires runtime metric samples; docs reconciled      | Deterministic preflight is the local gate and strict smoke remains live evidence.     |
| GA4/Search Console                                                           | Partially implemented, not self-service live-ready                 | Defer from usable-pilot gate and label accordingly.                                   |

## Pilot Journey

1. An operator prepares tenant access, KMS configuration, SES settings, and Meta/Google Ads
   credentials without committing credentials.
2. The tenant connects Meta and Google Ads; successful syncs populate aggregate dashboard data.
3. The tenant reviews dashboards and requests CSV, PDF, and PNG report exports.
4. The tenant configures email and optionally Slack/webhook alert channels; secret destinations
   are accepted write-only and shown thereafter only as configured/masked.
5. A fired rule reaches its assigned channels; the 06:10 daily summary reaches active email
   channels.
6. Operators run staging readiness checks, capture evidence, and make the pilot go/no-go decision.

## Delivery Milestones

### M0 - Specification And Status Reconciliation

- [x] Publish this specification and add it to cold-start wayfinding.
- [x] Correct stale task/catalog statements that presented already-built UI as missing.
- [x] Log the cross-stream implementation start and required review route.

### M1 - Real Report Artifacts

- [x] Generic `ReportExportJob` requests create non-empty artifact files for `csv`, `pdf`, and
      `png`.
- [x] CSV contains only tenant-scoped aggregate report rows; PDF/PNG reuse the exporter template.
- [x] Failed query/render/storage work produces `failed` jobs with sanitized diagnostics.
- [x] Download behavior remains compatible and completed jobs never point to absent files.
- [x] CSV cell output neutralizes spreadsheet formula prefixes and artifact downloads reject
      escaped/sibling paths for both generic and pilot-relevant Google Ads exports.

### M2 - Encrypted Notification Destinations

- [x] `NotificationChannel` stores encrypted Slack/webhook secrets using tenant DEKs/KMS.
- [x] Existing plaintext destination values are migrated into encrypted storage and removed from
      ordinary JSON configuration.
- [x] API inputs accept write-only secret values; API/UI responses expose only safe metadata and a
      configured/masked indication.
- [x] Dispatch decrypts only at delivery time and does not put secret material in logs/errors.
- [x] Model-level saves and response serialization prevent plaintext webhook secrets from being
      persisted or exposed if a caller bypasses normal serializer input.

### M3 - Scheduled Summary Delivery

- [x] The existing `ai-daily-summary` 06:10 schedule sends aggregated summaries to active tenant
      email notification channels.
- [x] Delivery records `delivered`, `skipped_no_recipients`, or `failed` audit outcomes.
- [x] The existing account email service remains the SES/log-provider delivery boundary.
- [x] Reprocessing the same successfully delivered summary snapshot is retry-safe and does not
      send a duplicate email or persist a duplicate summary record.

### M4 - Release And Operations Alignment

- [x] Release documentation uses `backend_release_preflight` for deterministic local/staging
      preflight and reserves strict smoke for live task/metrics evidence.
- [x] Alerting, orchestration, operations, and contract documentation match shipped behavior.
- [x] Canonical backend/frontend checks, data-contract checks, deterministic preflight, and local
      exporter render verification pass.
- [ ] The cross-stream release gate is cleared after required Raj/Mira and contract/security
      review; the skillchain currently reports `GATE_BLOCK` for this architecture-sensitive scope.

### M5 - Staging Activation Evidence

- [ ] Real Meta and Google Ads syncs populate an aggregate dashboard for a pilot tenant.
- [ ] Production-equivalent KMS configuration proves encrypted alert destination dispatch.
- [ ] SES configuration proves one alert email and one scheduled daily summary delivery.
- [ ] One Slack or webhook destination proves encrypted-at-rest dispatch.
- [x] Local throttle `429` evidence is repeatable through
      `backend_release_smoke --check-rate-limits`.
- [ ] Staging throttle `429`, empty-sync alerting, and final go/no-go evidence are attached to the
      release record.

## Interface Decisions

- `POST /api/reports/{report_id}/exports/` remains compatible; a completed export now guarantees a
  stored downloadable artifact for all supported formats.
- Report job failure details remain sanitized: no exported rows, tokens, URLs, or provider
  secrets appear in error fields or logs.
- Notification channel responses retain safe identity/state fields and add
  `credentials_configured` plus `masked_destination`; Slack/webhook secret configuration becomes
  write-only input.
- Daily summary delivery requires no new public endpoint; it consumes active email notification
  channel recipients already controlled by the tenant.

## Failure And Observability Requirements

- Export jobs log tenant ID, job ID, format, status, duration, and correlation/task context only.
- Notification delivery isolates channel failures; errors identify the channel and type but not
  destinations, headers, or tokens.
- Daily summary delivery audit records contain recipient count and outcome, not recipient
  addresses or summary content.
- All asynchronous tenant work remains wrapped in the established tenant context/RLS flow.

## Validation Commands

- Backend behavior: `make backend-lint && make backend-test`
- Frontend API/UI behavior: `make frontend-guardrails && make frontend-lint && make frontend-test && make frontend-build`
- Contracts/observability: `python3 infrastructure/airbyte/scripts/check_data_contracts.py && python3 infrastructure/airbyte/scripts/verify_observability_prereqs.py`
- Deterministic backend readiness: `backend/.venv/bin/python backend/manage.py backend_release_preflight`
- Cross-stream handoff: `make adinsights-preflight PROMPT="usable pilot delivery"`
- Live staging evidence only: `python3 backend/manage.py backend_release_smoke --strict-observability`

## Repository Verification Evidence

Verified on 2026-05-26 in the local development workspace:

- `make backend-lint && make backend-test` passed.
- `make frontend-guardrails && make frontend-lint && make frontend-test && make frontend-build`
  passed.
- Data-contract/observability prerequisite checks and `backend_release_preflight` passed; migration
  drift check reports no missing migrations.
- `integrations/exporter` tests passed and a live local run produced non-empty PDF and PNG files.
- `make adinsights-preflight PROMPT="usable pilot delivery"` executed and correctly retained a
  release block pending Raj/Mira architecture and contract/security review for this cross-folder
  security/API change.

## Post-Implementation Audit Evidence

Audited and hardened on 2026-05-27 in the local development workspace:

- Found and corrected server-side CSV formula injection exposure in generic and Google Ads export
  artifacts; tests now assert formula-leading campaign data is neutralized before download.
- Found and corrected prefix-string path containment checks in generic and Google Ads download
  handlers; tests now reject escaped sibling paths and empty generic artifacts.
- Found and corrected model-bypass plaintext secret persistence and residual configuration
  exposure; tests cover direct model writes, legacy-row response redaction, migration extraction,
  encrypted dispatch, and DEK rotation.
- Found and corrected repeated scheduled-summary delivery behavior; tests now prove the same
  successfully delivered snapshot sends once and persists one daily summary.
- Found two live-container export defects after bringing up the supported launcher profile:
  report workers did not package/share renderer artifacts with the API container, and the
  serverless Chromium binary failed on the local ARM64 container runtime. The backend image now
  packages Node plus the renderer, uses architecture-compatible native Chromium, and mounts a
  shared export-artifact volume for the API and summary worker.
- Found that live strict observability could not observe Celery samples produced outside the API
  process and that real publishers did not stamp queue timing headers. Container profiles now
  share a Prometheus multiprocess registry across backend/workers and publishers stamp
  `published_at`, with live `sync`/`snapshot`/`summary` queue starts and measured queue wait
  visible through `/metrics/app/`.
- Found duplicate snapshot and daily-summary completion counters caused by task-body metrics
  overlapping lifecycle instrumentation. Live re-verification after the fix published one task
  to each queue and each success counter increased exactly once.
- Reduced local image build context after the audit showed the Python virtual environments were
  being uploaded into Docker builds; the repository-level `.dockerignore` and root-context image
  build reduce rebuild context while permitting the renderer package to be included.
- Applied outstanding local development database migrations through
  `integrations.0026_notificationchannel_secret_config`, verified Django system checks, and
  launched a supported local profile with `scripts/dev-launch.sh`; `scripts/dev-healthcheck.sh`
  and the launcher demo-adapter check passed.
- Through the live frontend/API/worker path, requested fresh generic CSV, PDF, and PNG export
  jobs; each reached `completed`, each artifact was non-empty in shared storage, and each
  authenticated download endpoint returned HTTP `200`.
- Re-ran backend and frontend canonical suites, live PDF/PNG renderer artifact generation,
  contract/observability checks, migration drift detection, deterministic backend preflight, and
  diff validation after the hardening changes; all passed. The cross-stream preflight correctly
  retains its Raj/Mira contract/security review block.
- Exercised raw live-runtime strict smoke after real local queue work. The repaired queue-label
  and queue-wait signals are now present; its only remaining missing samples are retries,
  combined metrics, Airbyte, and dbt activity, which must be emitted in staging as described in
  the activation gates.

Extended on 2026-05-28:

- Found that `DRF_THROTTLE_PUBLIC` was configured and documented but had no fast, repeatable
  pilot evidence path. The public OpenAPI schema and lightweight version endpoint now use the
  public throttle, and `backend_release_smoke --check-rate-limits` verifies both auth and public
  throttles return `429` using the configured rates.
- Local evidence command passed with `POST /api/token/` reaching `429` on attempt `11` at
  `DRF_THROTTLE_AUTH_BURST=10/min`, and `GET /api/health/version/` reaching `429` on attempt
  `121` at `DRF_THROTTLE_PUBLIC=120/min`.

## External Activation Gates

Implementation can complete without external credentials. Pilot activation remains blocked until
operators supply production-equivalent KMS configuration, SES domain/sender readiness, real
Meta/Google Ads Airbyte credentials, live notification evidence, staging throttle evidence,
empty-sync evidence, and final staging go/no-go approval.
