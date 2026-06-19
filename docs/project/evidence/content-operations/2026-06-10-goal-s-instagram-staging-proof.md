# Goal S Evidence: Instagram Staging Publish Proof

Run timestamp local (`America/Jamaica`): 2026-06-10T14:49:07-0500
Run timestamp UTC: 2026-06-10T19:49:07Z
Operator: Codex
Environment: local workspace / staging-readiness check only
Feature flag(s): `CONTENT_OPS_META_INSTAGRAM_BETA=false`
Status: blocked; no Instagram media container or publish call was attempted

## Scope

- [ ] Planning/export only
- [ ] Facebook Page publishing
- [x] Instagram publishing
- [x] Public media URL proof
- [ ] Aggregate reporting
- [x] Failure simulation / readiness blocker capture

## Summary

Goal S requires redacted evidence for one approved Instagram feed publish, including public media URL
proof, container lifecycle, published media ID, logs/metrics, and rollback flag proof.

That proof could not be captured in this workspace because the local/staging configuration is not
authorized or deploy-ready for live Instagram publishing:

- `CONTENT_OPS_META_INSTAGRAM_BETA=False`
- `CONTENT_OPS_PUBLIC_MEDIA_BASE_URL` is not set
- `instagram_business_basic` is not present in runtime `META_OAUTH_SCOPES`
- `instagram_business_content_publish` is not present in runtime `META_OAUTH_SCOPES`
- legacy fallback `instagram_content_publish` is not present in runtime `META_OAUTH_SCOPES`
- `.dev-launch.active.env` reports `META_LOCAL_OAUTH_SUPPORTED=0`
- App Review approval, linked professional Instagram account evidence, deployable public media URL
  proof, and credentialed staging publish evidence are not present in the repository

No live Meta Graph call was made. No media container was created. No beta flag was enabled. No token,
Page ID, Instagram user ID, media ID, CDN URL, or credential value is recorded in this evidence
packet.

## Read-Only Validation Commands

```bash
backend/.venv/bin/python backend/manage.py shell -c "from django.conf import settings; print('CONTENT_OPS_META_INSTAGRAM_BETA=' + str(bool(settings.CONTENT_OPS_META_INSTAGRAM_BETA))); print('CONTENT_OPS_PUBLIC_MEDIA_BASE_URL_SET=' + str(bool(settings.CONTENT_OPS_PUBLIC_MEDIA_BASE_URL))); print('instagram_business_basic_in_oauth_scopes=' + str('instagram_business_basic' in settings.META_OAUTH_SCOPES)); print('instagram_business_content_publish_in_oauth_scopes=' + str('instagram_business_content_publish' in settings.META_OAUTH_SCOPES)); print('instagram_content_publish_in_oauth_scopes=' + str('instagram_content_publish' in settings.META_OAUTH_SCOPES)); print('META_GRAPH_API_VERSION=' + settings.META_GRAPH_API_VERSION)"
```

Observed safe output:

```text
CONTENT_OPS_META_INSTAGRAM_BETA=False
CONTENT_OPS_PUBLIC_MEDIA_BASE_URL_SET=False
instagram_business_basic_in_oauth_scopes=False
instagram_business_content_publish_in_oauth_scopes=False
instagram_content_publish_in_oauth_scopes=False
META_GRAPH_API_VERSION=v24.0
```

```bash
awk -F= '/^META_LOCAL_OAUTH_SUPPORTED=|^META_LOCAL_OAUTH_REASON=|^META_OAUTH_REDIRECT_URI=|^META_LOCAL_OAUTH_CANONICAL_FRONTEND_URL=/ {print}' .dev-launch.active.env
```

Observed safe output:

```text
META_LOCAL_OAUTH_CANONICAL_FRONTEND_URL=http://localhost:5173
META_OAUTH_REDIRECT_URI=http://localhost:5174/dashboards/data-sources
META_LOCAL_OAUTH_SUPPORTED=0
META_LOCAL_OAUTH_REASON=launcher_redirect_aligned_but_meta_app_must_allow_this_exact_frontend_origin_and_redirect_uri
```

```bash
rg -n "instagram_business_basic|instagram_business_content_publish|instagram_content_publish|instagram_basic|CONTENT_OPS_META_INSTAGRAM_BETA|CONTENT_OPS_PUBLIC_MEDIA_BASE_URL" backend/.env backend/.env.dev .env.dev.compose frontend/.env.local frontend/.env backend/.env.sample docs/project/meta-permission-profile.md docs/runbooks/content-operations-app-review.md docs/runbooks/content-operations-publishing.md
```

Observed safe result:

- Instagram publishing permissions appear only in documentation as gated planning items.
- `CONTENT_OPS_META_INSTAGRAM_BETA=0` and empty `CONTENT_OPS_PUBLIC_MEDIA_BASE_URL` appear in
  `backend/.env.sample`.
- Runtime env files do not contain Instagram publishing scopes or a public media base URL.

## Required Successful Evidence Still Missing

| Evidence item | Required proof | Current result |
| --- | --- | --- |
| Readiness | Redacted `GET /api/content-ops/readiness/` showing Instagram publishing ready | Missing |
| Public media URL proof | Redacted `public-media-proof` output with HTTPS URL, approved active version, image/video MIME, non-zero length, and `storage_key_exposed=false` | Missing |
| Clean unauthenticated media fetch | HTTP `200`, expected `Content-Type`, expected `Content-Length`, no tenant/private storage data | Missing |
| Approval snapshot | Approved draft version with internal and client approval for the exact Instagram media/caption | Missing |
| Schedule / attempt | Redacted schedule ID and publish attempt ID for a due Instagram target | Missing |
| Container creation | Redacted container ID suffix and attempt state transition to `container_pending` or `container_ready` | Missing |
| Container polling | Redacted status polling evidence through ready, retryable, expired, or terminal state | Missing |
| Media publish | Redacted Instagram published media ID suffix only | Missing |
| External media proof | Screenshot/link reference showing published staging Instagram feed media | Missing |
| Logs | Structured logs with `tenant_id`, `task_id`, `correlation_id`, `schedule_id`, `attempt_id`, `draft_id`, `channel`, `state`, and no secrets | Missing |
| Metrics | Queue delay, container processing duration, publish duration, retry count, terminal failure count, and safe failure code if applicable | Missing |
| Rollback | Proof that `CONTENT_OPS_META_INSTAGRAM_BETA` can be returned to `false` and processing fails closed | Missing |
| Redaction review | Confirmation that no raw token, app secret, authorization header, Page token, IG token, credential ref, signed URL secret, private URL, storage key, or user-level engagement data appears in evidence | Missing |

## Required Staging Run Preconditions

Before rerunning Goal S as a pass/fail staging publish:

1. Use a Meta test/staging app with the selected Instagram publishing permission family available
   for the controlled test user and professional Instagram account.
2. Confirm whether the product path uses the primary current family
   `instagram_business_basic` plus `instagram_business_content_publish`, or the documented legacy
   fallback `instagram_basic` plus `instagram_content_publish`.
3. Confirm the selected staging tenant has a linked professional Instagram account and tenant-local
   selected `MetaPage` with a decryptable token usable inside the provider boundary.
4. Configure `CONTENT_OPS_PUBLIC_MEDIA_BASE_URL` to a deployed HTTPS route that maps to
   `/api/content-ops/public-media/<asset_id>/`.
5. Capture `public-media-proof` for the exact approved image/video asset before container creation.
6. Confirm runtime OAuth scopes include only the selected gated Instagram publishing permissions in
   the staging environment.
7. Confirm `CONTENT_OPS_META_INSTAGRAM_BETA=true` only for the staging validation window.
8. Confirm the draft version has internal approval, client approval, immutable approval snapshot,
   caption, and approved media for the exact Instagram feed post.
9. Confirm all screenshots, logs, API outputs, public URL evidence, and provider results are
   redacted before storing them under `docs/project/evidence/content-operations/`.
10. Immediately prove rollback by setting `CONTENT_OPS_META_INSTAGRAM_BETA=false` again and
    verifying the processor fails closed with `provider_not_configured`.

## Staging Evidence Template For The Real Run

| Step | Action | Expected | Actual | Pass/Fail |
| ---- | ------ | -------- | ------ | --------- |
| 1 | Capture beta flag state before enabling staging publish | `CONTENT_OPS_META_INSTAGRAM_BETA=false` | Not run | Fail |
| 2 | Enable Instagram beta in staging only | Flag true in staging runtime, not committed | Not run | Fail |
| 3 | Capture readiness endpoint | Instagram publishing axis ready | Not run | Fail |
| 4 | Capture public media proof | HTTPS, approved, fetchable, non-secret URL proof | Not run | Fail |
| 5 | Fetch public media unauthenticated | HTTP `200`, safe headers, no private paths | Not run | Fail |
| 6 | Capture exact approved draft/version | Internal and client approvals match active version and media | Not run | Fail |
| 7 | Dispatch due schedule | One Instagram `PublishAttempt` created/queued | Not run | Fail |
| 8 | Process attempt: create container | Attempt enters container lifecycle with redacted container ID | Not run | Fail |
| 9 | Poll container | Attempt reaches `container_ready` or safe failure state | Not run | Fail |
| 10 | Publish media | Attempt transitions to `published` with redacted media ID suffix | Not run | Fail |
| 11 | Capture external Instagram media | Staging Instagram feed media visible | Not run | Fail |
| 12 | Capture logs/metrics | Structured logs and queue/container/publish metrics without secrets | Not run | Fail |
| 13 | Roll back flag | Flag false and processor fails closed | Not run | Fail |

## Outcome

- [ ] Pass
- [x] Fail / blocked

## Validation

Passed:

```bash
git diff --check -- docs/project/evidence/content-operations/2026-06-10-goal-s-instagram-staging-proof.md docs/runbooks/content-operations-publishing.md docs/project/content-operations-current-state.md docs/project/content-operations-implementation-backlog.md docs/ops/doc-index.md docs/ops/agent-activity-log.md
```

ADinsights preflight:

```bash
make adinsights-preflight PROMPT="Goal S Content Operations Instagram staging feed publish proof; docs/evidence only; captured blocked staging-readiness evidence because Instagram beta publishing remains disabled, public media base URL is unset, and Instagram publishing scopes are absent from runtime OAuth scopes; no container or media publish Graph call and no live publishing activation"
```

Persisted packet rerun:

```bash
backend/.venv/bin/python docs/ops/skills/adinsights-release-readiness/scripts/run_preflight_skillchain.py --prompt "Goal S Content Operations Instagram staging feed publish proof; docs/evidence only; captured blocked staging-readiness evidence because Instagram beta publishing remains disabled, public media base URL is unset, and Instagram publishing scopes are absent from runtime OAuth scopes; no container or media publish Graph call and no live publishing activation" --changed-files-from-git --format markdown --output-dir docs/project/evidence/content-operations/preflight-2026-06-10-goal-s-instagram-staging-proof
```

Result:

- Router action: `resolve`
- Scope status: `ESCALATE_ARCH_RISK`
- Contract status: `WARN_POSSIBLE_CONTRACT_CHANGE`
- Release status: `GATE_BLOCK`
- Blocking issue: scope control gate blocked by architecture-level scope risk
- Warnings: contract integrity follow-up and security/PII verification are required before release

Packet directory:

- `docs/project/evidence/content-operations/preflight-2026-06-10-goal-s-instagram-staging-proof/`

Remediation:

- Capture the real staging evidence only after Meta App Review/test-app setup, staging tenant/Page/IG
  credentials, deployed HTTPS public media URL proof, gated runtime scopes, and temporary beta flag
  activation are available.
- Keep live Instagram publishing disabled outside the controlled staging validation window.

Follow-up ticket:

- Goal S rerun: credentialed Instagram staging feed publish proof.
