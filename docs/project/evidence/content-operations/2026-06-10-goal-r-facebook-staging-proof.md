# Goal R Evidence: Facebook Staging Publish Proof

Run timestamp local (`America/Jamaica`): 2026-06-10T14:45:04-0500
Run timestamp UTC: 2026-06-10T19:45:04Z
Operator: Codex
Environment: local workspace / staging-readiness check only
Feature flag(s): `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING=false`
Status: blocked; no Facebook Page publish was attempted

## Scope

- [ ] Planning/export only
- [x] Facebook Page publishing
- [ ] Instagram publishing
- [ ] Aggregate reporting
- [x] Failure simulation / readiness blocker capture

## Summary

Goal R requires redacted evidence for one approved Facebook Page publish, including readiness,
approval snapshot, publish attempt, published post, logs/metrics, and rollback flag proof.

That proof could not be captured in this workspace because the local/staging configuration is not
authorized for live Facebook Page publishing:

- `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING=False`
- `pages_manage_posts` is not present in runtime `META_OAUTH_SCOPES`
- `.dev-launch.active.env` reports `META_LOCAL_OAUTH_SUPPORTED=0`
- App Review approval and credentialed staging Page evidence are not present in the repository

No live Meta Graph call was made. No feature flag was enabled. No token, Page ID, post ID, or
credential value is recorded in this evidence packet.

## Read-Only Validation Commands

```bash
backend/.venv/bin/python backend/manage.py shell -c "from django.conf import settings; print('CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING=' + str(bool(settings.CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING))); print('pages_manage_posts_in_oauth_scopes=' + str('pages_manage_posts' in settings.META_OAUTH_SCOPES)); print('META_GRAPH_API_VERSION=' + settings.META_GRAPH_API_VERSION)"
```

Observed safe output:

```text
CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING=False
pages_manage_posts_in_oauth_scopes=False
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
rg -n "pages_manage_posts" backend/.env backend/.env.dev .env.dev.compose frontend/.env.local frontend/.env backend/.env.sample docs/project/meta-permission-profile.md docs/runbooks/content-operations-app-review.md
```

Observed safe result:

- `pages_manage_posts` appears only in documentation as `content_ops_gated`.
- It does not appear in runtime env files or `backend/.env.sample` OAuth scope examples.

## Required Successful Evidence Still Missing

| Evidence item        | Required proof                                                                                                                                               | Current result |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------- |
| Readiness            | Redacted `GET /api/content-ops/readiness/` showing Facebook publishing ready                                                                                 | Missing        |
| Approval snapshot    | Approved draft version with internal and client approval for the exact Facebook post                                                                         | Missing        |
| Schedule / attempt   | Redacted schedule ID and publish attempt ID for a due Facebook Page target                                                                                   | Missing        |
| Live provider result | Redacted provider result with Meta post ID suffix only                                                                                                       | Missing        |
| External post proof  | Screenshot/link reference showing published staging Facebook Page post                                                                                       | Missing        |
| Logs                 | Structured logs with `tenant_id`, `task_id`, `correlation_id`, `schedule_id`, `attempt_id`, `draft_id`, `channel`, `state`, and no secrets                   | Missing        |
| Metrics              | Queue delay, publish duration, retry count, terminal failure count, and safe failure code if applicable                                                      | Missing        |
| Rollback             | Proof that `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING` can be returned to `false` and processing fails closed                                                     | Missing        |
| Redaction review     | Confirmation that no raw token, app secret, authorization header, Page token, credential ref, private URL, or user-level engagement data appears in evidence | Missing        |

## Required Staging Run Preconditions

Before rerunning Goal R as a pass/fail staging publish:

1. Use a Meta test/staging app with `pages_manage_posts` approved or available for the controlled
   test user/Page path.
2. Confirm the selected staging tenant has a tenant-local selected `MetaPage` with a decryptable Page
   token and the correct Page task access.
3. Confirm runtime OAuth scopes include `pages_manage_posts` only in the gated staging environment.
4. Confirm `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING=true` only for the staging validation window.
5. Confirm the draft version has internal approval, client approval, and immutable approval snapshot
   for the exact Facebook caption/media to publish.
6. Confirm all screenshots, logs, API outputs, and provider results are redacted before storing them
   under `docs/project/evidence/content-operations/`.
7. Immediately prove rollback by setting `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING=false` again and
   verifying the processor fails closed with `provider_not_configured`.

## Staging Evidence Template For The Real Run

| Step | Action                                                     | Expected                                                      | Actual  | Pass/Fail |
| ---- | ---------------------------------------------------------- | ------------------------------------------------------------- | ------- | --------- |
| 1    | Capture feature flag state before enabling staging publish | `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING=false`                  | Not run | Fail      |
| 2    | Enable Facebook publishing in staging only                 | Flag true in staging runtime, not committed                   | Not run | Fail      |
| 3    | Capture readiness endpoint                                 | Facebook Page publishing axis ready                           | Not run | Fail      |
| 4    | Capture exact approved draft/version                       | Internal and client approvals match active version            | Not run | Fail      |
| 5    | Dispatch due schedule                                      | One Facebook Page `PublishAttempt` created/queued             | Not run | Fail      |
| 6    | Process attempt                                            | Attempt transitions through preflight/publishing to published | Not run | Fail      |
| 7    | Capture provider result                                    | Redacted Meta post ID suffix only                             | Not run | Fail      |
| 8    | Capture external Page post                                 | Staging Facebook Page post visible                            | Not run | Fail      |
| 9    | Capture logs/metrics                                       | Structured logs and queue/publish metrics without secrets     | Not run | Fail      |
| 10   | Roll back flag                                             | Flag false and processor fails closed                         | Not run | Fail      |

## Outcome

- [ ] Pass
- [x] Fail / blocked

## Validation

Passed:

```bash
git diff --check -- docs/project/evidence/content-operations/2026-06-10-goal-r-facebook-staging-proof.md docs/runbooks/content-operations-publishing.md docs/project/content-operations-current-state.md docs/project/content-operations-implementation-backlog.md docs/ops/doc-index.md docs/ops/agent-activity-log.md
```

ADinsights preflight:

```bash
make adinsights-preflight PROMPT="Goal R Content Operations Facebook staging publish proof; docs/evidence only; captured blocked staging-readiness evidence because live Facebook publishing remains disabled and pages_manage_posts is absent from runtime OAuth scopes; no Graph call and no live publishing activation"
```

Persisted packet rerun:

```bash
backend/.venv/bin/python docs/ops/skills/adinsights-release-readiness/scripts/run_preflight_skillchain.py --prompt "Goal R Content Operations Facebook staging publish proof; docs/evidence only; captured blocked staging-readiness evidence because live Facebook publishing remains disabled and pages_manage_posts is absent from runtime OAuth scopes; no Graph call and no live publishing activation" --changed-files-from-git --format markdown --output-dir docs/project/evidence/content-operations/preflight-2026-06-10-goal-r-facebook-staging-proof
```

Result:

- Router action: `resolve`
- Scope status: `ESCALATE_ARCH_RISK`
- Contract status: `WARN_POSSIBLE_CONTRACT_CHANGE`
- Release status: `GATE_BLOCK`
- Blocking issue: scope control gate blocked by architecture-level scope risk
- Warnings: contract integrity follow-up and security/PII verification are required before release

Packet directory:

- `docs/project/evidence/content-operations/preflight-2026-06-10-goal-r-facebook-staging-proof/`

Remediation:

- Capture the real staging evidence only after Meta App Review/test-app setup, staging tenant/Page
  credentials, gated runtime scopes, and temporary staging flag activation are available.
- Keep live Facebook Page publishing disabled outside the controlled staging validation window.

Follow-up ticket:

- Goal R rerun: credentialed Facebook staging publish proof.
