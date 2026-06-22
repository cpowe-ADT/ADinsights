# Content Operations Goal O Facebook Page Publisher Adapter

Date: 2026-06-10
Timezone: America/Jamaica
Scope: backend
Status: live Facebook Page adapter implemented behind disabled-by-default config

## Summary

Goal O adds a real Facebook Page Graph publisher adapter for Content Ops. The adapter remains
disabled unless `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING=true`; default processing still fails closed
with `provider_not_configured`.

No production tenant publishing is enabled by this goal.

## Implemented Boundary

- `content_ops.facebook_graph.FacebookGraphPageClient` posts approved Page feed messages to the repo
  configured Graph API version.
- `content_ops.facebook_graph.FacebookGraphPagePublisher` resolves the selected `MetaPage` by
  `tenant_id` and `meta_page_id`, decrypts the stored Page token inside the adapter, and calls the
  Graph client.
- `content_ops.publisher.process_facebook_page_publish_attempt` uses the live adapter only through
  an injected publisher or when `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING=true`.
- Successful live/fake publish reuses the existing `PublishedPost`, attempt, schedule, and draft
  state transitions.
- Retryable/terminal Graph errors are converted to safe Content Ops provider errors before
  persistence.

## Security And Tenant Rules

- Page token lookup is scoped by tenant plus selected Page ID.
- Cross-tenant `MetaPage` rows are not used even when `page_id` matches.
- Access tokens are sent in the Graph POST body, not the URL.
- Persisted failure details are sanitized by the existing provider failure path.
- Raw Graph responses, tokens, authorization headers, and Page token values are not stored in
  publish attempts.

## Remaining Launch Blockers

- `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING` must stay off for production tenants until App Review,
  staging proof, security review, observability, rollback, and release gates pass.
- Goal R Facebook staging publish proof is still required.
- Final release preflight remains expected to report `GATE_BLOCK` until staging/App Review/release
  approvals are complete.

## Validation Results

- `backend/.venv/bin/pytest -q backend/tests/test_content_ops_publisher.py` passed.
- `backend/.venv/bin/pytest -q backend/tests/test_content_ops_publisher.py backend/tests/test_content_ops_api.py backend/tests/test_schema_regressions.py backend/tests/test_tasks.py` passed.
- `make backend-lint && make backend-test` passed.
- `git diff --check -- backend/content_ops/facebook_graph.py backend/content_ops/publisher.py backend/core/settings.py backend/.env.sample backend/tests/test_content_ops_publisher.py docs/project/api-contract-changelog.md docs/project/content-operations-api-contract.md docs/runbooks/content-operations-publishing.md docs/project/feature-flags-reference.md docs/project/content-operations-current-state.md docs/project/content-operations-implementation-backlog.md docs/project/evidence/content-operations/2026-06-10-goal-o-facebook-page-adapter.md docs/ops/doc-index.md docs/ops/agent-activity-log.md` passed.
- Scope gatekeeper advisory packet: `ESCALATE_ARCH_RISK` for backend plus docs, with architecture-sensitive settings change and contract-risk docs. Required reviewers: Raj, Mira, Sofia, Hannah.
- Contract guard advisory packet: `WARN_POSSIBLE_CONTRACT_CHANGE`; non-breaking contract-doc change with no missing docs.
- ADinsights preflight packet persisted at `docs/project/evidence/content-operations/preflight-2026-06-10-goal-o-facebook-page-adapter/`.
- ADinsights preflight result: `GATE_BLOCK`, expected until architecture/contract/security review, staging proof, App Review approval, and final release approval are complete.
