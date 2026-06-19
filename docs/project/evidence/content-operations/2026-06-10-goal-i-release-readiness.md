# Content Operations Goal I Release Readiness Evidence

Run timestamp local (`America/Jamaica`): 2026-06-10T13:01:20-0500
Run timestamp UTC: 2026-06-10T18:01:20Z
Operator: Codex
Environment: local repository validation
Feature flag(s): Content Ops publishing remains disabled for live provider activation

## Scope

- [x] Planning/export only
- [ ] Facebook Page publishing live activation
- [ ] Instagram publishing live activation
- [x] Aggregate reporting
- [x] Failure/readiness simulation

## Summary

Goal I is complete as a release-readiness and Meta App Review evidence pass. The result is not a
launch approval. The current packet status is `GATE_BLOCK`, and live Facebook/Instagram publishing
must remain disabled until the blocking issues and warnings below are resolved.

## Commands Run

```bash
make adinsights-preflight PROMPT="Content Ops release readiness and Meta App Review evidence pass; docs/runbooks validation only; no live publishing activation"

backend/.venv/bin/python docs/ops/skills/adinsights-release-readiness/scripts/run_preflight_skillchain.py \
  --prompt "Content Ops release readiness and Meta App Review evidence pass; docs/runbooks validation only; no live publishing activation" \
  --changed-files-from-git \
  --format markdown \
  --output-dir docs/project/evidence/content-operations/preflight-2026-06-10-goal-i
```

Both commands exited `0`.

## Packet Outputs

Persisted packet directory:

- `docs/project/evidence/content-operations/preflight-2026-06-10-goal-i/router-packet.json`
- `docs/project/evidence/content-operations/preflight-2026-06-10-goal-i/scope-packet.json`
- `docs/project/evidence/content-operations/preflight-2026-06-10-goal-i/contract-packet.json`
- `docs/project/evidence/content-operations/preflight-2026-06-10-goal-i/release-packet.json`

Key results from `release-packet.json`:

| Gate | Status | Evidence |
| ---- | ------ | -------- |
| Release status | `GATE_BLOCK` | `release_status` |
| Scope control | `BLOCK` | `ESCALATE_ARCH_RISK` |
| Contract integrity | `WARN` | `WARN_POSSIBLE_CONTRACT_CHANGE` |
| Security/PII/secrets | `WARN` | Sensitive path signals, including env sample and publishing-related surfaces |
| Runbook operations readiness | `PASS` | Required runbooks present |
| Documentation completeness | `PASS` | Doc index and activity log present |
| Rollout/rollback plan | `PASS` | Deployment runbook present |
| Observability | `PASS` | No explicit packet blocker |
| Test coverage | `INFO` | Required tests identified; packet did not execute optional checks |

## Release Blocking Issues

- Scope control gate is blocked by architecture-level scope risk.
- Current changed-file evidence spans `backend/`, `frontend/`, and `docs/`, including
  architecture-sensitive files such as `AGENTS.md`, `backend/core/settings.py`, and
  `backend/core/urls.py`.
- Raj and Mira review is required before release or merge of the cross-stream Content Ops package.

## Release Warnings

- Contract integrity requires follow-up before release.
- Security/PII gate requires verification due to sensitive publishing, credential, and env-sample
  signals.

## Required Approvers

From the release packet:

- Raj
- Mira
- Sofia
- Hannah
- Lina

## Required Artifacts

From the release packet:

- `docs/runbooks/release-checklist.md`
- `docs/runbooks/deployment.md`
- `docs/runbooks/operations.md`
- `docs/project/api-contract-changelog.md`
- `docs/project/integration-data-contract-matrix.md`

Content Ops-specific artifacts still required before live publishing:

- Meta App Review permission family confirmation for Facebook Page and Instagram publishing.
- Reviewer copy and screencast showing exact approved content, scheduling/publishing, and aggregate
  reporting without secrets.
- Staging Facebook Page publish proof with redacted Page/app/test-user identifiers.
- Staging Instagram professional account publish proof with redacted IG user ID.
- Deployable public/fetchable asset URL proof for Meta media fetches.
- Token handling proof for live provider adapters.
- Observability evidence for queue delay, publish duration, retries, failure codes, and aggregate
  metric refresh.
- Rollback evidence showing live publishing can be disabled without affecting planning/export.

## Redacted Identifier Status

- Tenant: not captured in this local pass
- Meta app ID: not captured
- Facebook Page ID: not captured
- Instagram user ID: not captured
- Draft ID: not captured
- Schedule ID: not captured
- Publish attempt ID: not captured
- Correlation ID: not captured

No raw tokens or secrets were captured in this evidence pass.

## Outcome

- [ ] Pass
- [x] Fail / release blocked

Remediation:

1. Route the package to Raj and Mira for architecture-scope review.
2. Resolve contract warning or capture explicit contract risk acceptance with Sofia, Lina, and Raj.
3. Complete security/PII/secrets review with Nina or the security owner before any live provider
   adapter is enabled.
4. Capture Meta App Review and staging evidence listed above.
5. Rerun the preflight and required backend/frontend test matrices after review changes.

Follow-up ticket: Content Ops release/App Review blocker resolution.
