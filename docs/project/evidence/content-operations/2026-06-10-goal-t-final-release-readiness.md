# Goal T Evidence: Final Release Readiness Pass

Run timestamp local (`America/Jamaica`): 2026-06-10T14:52:38-0500
Run timestamp UTC: 2026-06-10T19:52:38Z
Operator: Codex
Environment: local workspace / release-readiness evidence review
Decision: **NO-GO**
Release status: `GATE_BLOCK`
Live publishing status: disabled

## Summary

Goal T ran the final release-readiness pass for Content Operations live Facebook and Instagram
publishing after Goal R and Goal S staging-proof checks. The current evidence does not prove safe
live posting. Release remains blocked and live publishing must stay disabled.

No live Meta Graph call was made. No Facebook or Instagram publishing flag was enabled. No OAuth
publishing scope was added.

## Final Gate Result

ADinsights preflight:

```bash
make adinsights-preflight PROMPT="Goal T Content Operations final release readiness pass for live Facebook and Instagram publishing; evaluate current evidence after Goal R and Goal S blocked staging proof packets; do not enable live publishing; record final go/no-go, approver requirements, rollback plan, required artifacts, and unresolved GATE_BLOCK blockers"
```

Persisted packet rerun:

```bash
backend/.venv/bin/python docs/ops/skills/adinsights-release-readiness/scripts/run_preflight_skillchain.py --prompt "Goal T Content Operations final release readiness pass for live Facebook and Instagram publishing; evaluate current evidence after Goal R and Goal S blocked staging proof packets; do not enable live publishing; record final go/no-go, approver requirements, rollback plan, required artifacts, and unresolved GATE_BLOCK blockers" --changed-files-from-git --format markdown --output-dir docs/project/evidence/content-operations/preflight-2026-06-10-goal-t-final-release-readiness
```

Result:

- Router action: `clarify`
- Scope status: `ESCALATE_ARCH_RISK`
- Contract status: `WARN_POSSIBLE_CONTRACT_CHANGE`
- Release status: `GATE_BLOCK`
- Blocking issue: scope control gate blocked by architecture-level scope risk
- Warnings:
  - contract integrity requires follow-up before release
  - security/PII handling requires verification due to sensitive signals

Packet directory:

- `docs/project/evidence/content-operations/preflight-2026-06-10-goal-t-final-release-readiness/`

## Gate Matrix

| Gate | Status | Evidence / reason |
| --- | --- | --- |
| Scope control | Block | Final preflight returned `ESCALATE_ARCH_RISK`; route to Raj + Mira before any release activation. |
| Contract integrity | Warn | Final preflight returned `WARN_POSSIBLE_CONTRACT_CHANGE`; contract follow-up remains required. |
| Security / PII / secrets | Warn | Publishing touches OAuth tokens, public media URLs, provider errors, and evidence redaction; Nina signoff is not recorded. |
| Facebook staging proof | Block | Goal R is blocked; no approved Facebook Page staging publish proof exists. |
| Instagram staging proof | Block | Goal S is blocked; no approved Instagram feed staging publish proof exists. |
| Meta App Review | Block | Permission availability/approval evidence is not captured for `pages_manage_posts` or the selected Instagram publishing family. |
| Public media deployment | Block for Instagram | Backend proof path exists, but deployed HTTPS/CDN proof for staging is missing. |
| Test coverage | Pending before release | Prior J-Q focused/full tests are recorded, but release packet still requires explicit backend/frontend verification before a go decision. |
| Runbook / ops readiness | Pass with blockers | Runbooks exist and now include blocked R/S proof checklists, but release activation remains prohibited. |
| Rollout / rollback plan | Pass as disabled plan | Rollback defaults are clear: keep flags false and publishing scopes absent. Staging rollback proof still missing. |
| Final decision | No-go | Do not enable live Facebook or Instagram publishing. |

## Required Approvers Before Any Future Go

Final preflight required:

- Raj
- Mira
- Sofia
- Hannah
- Lina

Content Ops live publishing also requires the following reviewer signoffs before production or beta
activation:

- Maya: Meta product path, App Review permission family, staging Page/IG evidence
- Nina: secrets, token handling, public media URL exposure, PII/aggregate-only evidence
- Leo: Celery scheduling, retry, Instagram container lifecycle, fail-closed rollback behavior

No required approver is recorded as signed off for live publishing in this Goal T pass.

## Required Artifacts Before Any Future Go

Final preflight required these general release artifacts:

- `docs/runbooks/release-checklist.md`
- `docs/runbooks/deployment.md`
- `docs/runbooks/operations.md`
- `docs/project/api-contract-changelog.md`
- `docs/project/integration-data-contract-matrix.md`

Content Ops live publishing additionally requires:

- successful Goal R Facebook staging publish proof with redacted readiness, approval snapshot,
  publish attempt, published post, logs/metrics, and rollback flag proof
- successful Goal S Instagram staging feed publish proof with public media URL proof, container
  lifecycle, published media ID, logs/metrics, and rollback flag proof
- Meta App Review evidence packet with permission copy, screencast, test users/assets, redaction
  checklist, and submission result
- deployed HTTPS public media/CDN proof for the exact Instagram staging asset
- security review proving no raw tokens, credential refs, signed URL secrets, private storage keys,
  or user-level engagement identities are logged or stored in evidence
- contract review proving Content Ops readiness, publishing queue, reports, and retry/error payloads
  have no unreviewed breaking drift
- final backend and frontend validation matrix for the release candidate

## Current Blockers

1. Facebook staging publish proof is blocked:
   - `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING=False`
   - `pages_manage_posts` is absent from runtime OAuth scopes
   - no credentialed staging Page publish proof exists
   - evidence: `docs/project/evidence/content-operations/2026-06-10-goal-r-facebook-staging-proof.md`

2. Instagram staging publish proof is blocked:
   - `CONTENT_OPS_META_INSTAGRAM_BETA=False`
   - `CONTENT_OPS_PUBLIC_MEDIA_BASE_URL` is unset
   - Instagram publishing scopes are absent from runtime OAuth scopes
   - no credentialed staging Instagram feed publish proof exists
   - evidence: `docs/project/evidence/content-operations/2026-06-10-goal-s-instagram-staging-proof.md`

3. Meta App Review evidence is incomplete:
   - `pages_manage_posts` approval/availability is not proven
   - selected Instagram permission family is not proven in the app console
   - screencast/submission packet is not complete

4. Final release preflight remains blocked:
   - `scope_control=BLOCK`
   - `contract_integrity=WARN`
   - `security_pii_secrets=WARN`

## Rollback / Hold Plan

Until a future go decision is recorded:

1. Keep `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING=false`.
2. Keep `CONTENT_OPS_META_INSTAGRAM_BETA=false`.
3. Keep Content Ops publishing permissions out of default/runtime OAuth scopes:
   - do not add `pages_manage_posts`
   - do not add `instagram_business_basic`
   - do not add `instagram_business_content_publish`
   - do not add legacy `instagram_content_publish`
4. Keep `CONTENT_OPS_PUBLIC_MEDIA_BASE_URL` unset unless running a controlled staging public-media
   proof.
5. Keep live Graph publishing disabled outside a controlled staging validation window.
6. If a staging validation window is opened later, immediately prove rollback by returning the
   relevant flag to `false` and verifying the processor fails closed with `provider_not_configured`.
7. Do not expose raw tokens, credential refs, signed URL secrets, Page/IG token values, private
   storage keys, or user-level engagement identities in logs, screenshots, evidence, or persisted
   failure details.

## Validation

Passed:

```bash
git diff --check
```

Final preflight and persisted packet rerun both completed and returned `GATE_BLOCK`, which is the
correct release-readiness result for the current evidence.

## Outcome

- [ ] Go
- [x] No-go

Required next action:

- Do not enable live publishing.
- Treat the persistent live-publishing goal as blocked until external staging/App Review conditions
  are available and Goals R/S can be rerun successfully.
