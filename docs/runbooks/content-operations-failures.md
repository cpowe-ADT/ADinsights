# Content Operations Failure Triage

Status: planned operations runbook
Timezone baseline: `America/Jamaica`

## Purpose

Classify and respond to Content Operations failures without leaking secrets or collapsing readiness
states.

## Triage Order

1. Check `GET /api/content-ops/readiness/`.
2. Check publish attempt state and `failure_code`.
3. Check scheduler logs by `correlation_id`.
4. Check Meta auth/Page/Instagram status separately.
5. Check asset URL fetch validation.
6. Check App Review/permission evidence.

## Failure Classes

| Class | Signals | Action |
| ----- | ------- | ------ |
| `caption_schema_invalid` | caption provider/fake output is missing required fields or has invalid values | Fix provider/schema mapping; do not create drafts from invalid candidates |
| `caption_policy_blocked` | all caption candidates contain blocked terms or secret-like output | Update brief constraints or regenerate with safer prompt; do not approve generated output |
| `required_terms_missing` | all caption candidates omit required terms/disclaimers | Regenerate or edit copy so required terms are present before review |
| `caption_active_limit_exceeded` | too many queued/running caption jobs exist for the tenant | Wait for active jobs to finish/cancel or raise the reviewed tenant limit |
| `caption_daily_limit_exceeded` | tenant reached rolling 24-hour caption job limit | Wait for quota window reset or raise the reviewed tenant limit |
| `caption_candidate_limit_exceeded` | requested candidates exceed rolling 24-hour candidate quota | Reduce candidate count or wait for quota window reset |
| `generation_job_cancelled` | caption job was cancelled before processing | No action unless user requests a new generation job |
| `generation_job_wrong_type` | caption processor received a non-caption job | Route job to the correct processor and inspect task wiring |
| `brief_missing` | generation job lost or lacks its source brief | Stop processing; inspect tenant-scoped data integrity |
| `auth_setup_failure` | Meta auth disconnected or token invalid | Reconnect Meta OAuth |
| `page_selection_failure` | no selected Page or Page role missing | Re-select Page and verify admin/business access |
| `attempt_missing` | publish attempt ID is not found | Confirm scheduler created the attempt and tenant context is correct |
| `attempt_wrong_tenant` | attempt does not belong to the processed tenant | Stop processing; verify tenant context and caller |
| `unsupported_channel` | Facebook preflight received non-Facebook channel or identity | Route to the correct platform preflight |
| `attempt_state_not_publishable` | attempt or draft state is not eligible for publishing | Confirm scheduler/approval state before retry |
| `schedule_missing` | attempt schedule is unavailable for tenant | Recreate schedule after verifying draft state |
| `draft_missing` | attempt draft is unavailable for tenant | Stop processing and inspect tenant-scoped data integrity |
| `version_missing` | attempt version is unavailable for tenant | Stop processing and inspect tenant-scoped data integrity |
| `schedule_version_stale` | active version, schedule version, or approval snapshot version drifted | Re-submit client approval and reschedule current version |
| `approval_snapshot_missing` | schedule lacks approval records | Re-submit approval workflow and reschedule |
| `client_approval_missing` | schedule lacks approved client approval in snapshot | Obtain client approval before publishing |
| `publishing_identity_missing` | attempt has no selected publish identity | Select a Facebook Page publishing identity |
| `publishing_identity_wrong_tenant` | attached identity belongs to another tenant | Stop processing; inspect tenant-scoped data integrity |
| `publishing_identity_not_selected` | identity is not selected for publishing | Select or reselect the intended Page identity |
| `publishing_identity_not_ready` | identity readiness is blocked, needs reauth, or needs review | Resolve identity readiness before retry |
| `facebook_page_publishing_not_ready` | readiness axis for Facebook Page publishing is blocked | Resolve permission/auth/Page blockers shown by readiness endpoint |
| `content_missing` | approved version has no caption text for MVP Page publish | Add approved caption content and reschedule |
| `provider_not_configured` | processor was invoked without a live publisher adapter | Do not retry automatically; wire staging-approved provider adapter first |
| `provider_retryable_error` | injected/provider boundary returned retryable failure | Allow backoff; inspect safe failure detail and provider status |
| `provider_terminal_error` | injected/provider boundary returned terminal failure | Fix root cause before retry |
| `facebook_publish_permission_missing` | missing `pages_manage_posts` | Complete App Review and OAuth rerequest |
| `instagram_linkage_failure` | no linked professional IG account | Link IG professional account to selected Page |
| `instagram_publish_permission_missing` | missing active IG content publish permission | Complete App Review and OAuth rerequest |
| `asset_fetch_failed` | Meta cannot fetch media URL | Validate public HTTPS URL, content type, length, expiry |
| `invalid_media` | Meta rejects dimensions/type/duration | Replace or regenerate media |
| `container_expired` | IG container expired before publish | Recreate container inside near-publish window |
| `rate_limited` | retryable upstream rate-limit response | Allow backoff; reduce manual retries |
| `duplicate_prevented` | idempotency key already used | Confirm published post before retry |
| `reporting_lag` | published but metrics unavailable | Wait for next metric refresh; do not republish |

## Caption Generation Boundary

Implemented caption generation behavior:

- queued jobs are created by `POST /api/content-ops/briefs/{brief_id}/captions/generate/`
- processor task name is `content_ops.tasks.process_content_caption_generation_job`
- default provider fails closed with `provider_not_configured`
- successful injected/fake provider output creates `generated` drafts and active versions only
- generation never creates approval requests, schedules, publish attempts, published posts, or
  metrics

Do not treat caption failures as publishing failures. Generated output still needs normal human
approval before scheduling.

## Safe Error Handling

Never expose:

- raw access tokens
- app secrets
- signed asset URLs
- raw provider payloads with credentials
- raw AI prompts containing client-sensitive data

Expose:

- safe `failure_code`
- actionable message
- retryable boolean
- next retry time
- correlation ID

## Escalation

- Maya: Meta permission, Page, Instagram, or Graph API errors.
- Leo: scheduler locks, retries, duplicate attempts, container expiry.
- Nina: tokens, signed URLs, prompt/secret leakage.
- Sofia: serializers, API payloads, tenant isolation.
- Lina: UI state confusion or missing operator action.
- Omar/Hannah: logs, alerts, runbook gaps.
- Raj/Mira: cross-stream or architecture-sensitive failures.

## Incident Evidence

Create an evidence artifact when:

- any scheduled publish misses SLA
- a duplicate publish is suspected
- a secret leak is suspected
- App Review blocks rollout
- Instagram container failures repeat for a tenant

Use `docs/project/evidence/content-operations/_TEMPLATE.md`.
