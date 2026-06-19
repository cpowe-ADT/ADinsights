# Content Operations Goal L Contract and Security Review

Date: 2026-06-10
Timezone: America/Jamaica
Scope: docs/tests only unless required fixes are discovered
Status: review evidence prepared; live publishing remains disabled

## Review Summary

Goal L reviewed the Content Ops contract/security boundary before live Meta adapter work. The
current implementation remains a safe foundation: tenant-scoped DRF routes exist, scheduler and
publisher processors are fakeable/disabled by default, `publish-now` returns `501 not_implemented`,
credential references and storage internals are not returned through public serializers, and organic
reporting stores aggregate metric snapshots only.

One contract-doc drift item was corrected during this pass: the API contract previously said live
frontend export history was still planned. Persisted JSON export artifact history is now implemented,
while richer PDF/CSV/ZIP packet formats remain future work.

## Reviewer Notes

- Raj: Goal L spans `docs/` and `backend/` test evidence, so cross-stream review is required before
  merge. Keep future adapter work split by backend-only goals unless a contract doc change is needed.
- Mira: No architecture refactor is needed for Goal L. The current provider-boundary shape remains
  compatible with disabled-by-default live adapters.
- Sofia: API contract evidence is strongest around serializer ownership, write-only fields,
  publish-attempt enums, retry endpoint behavior, and disabled `publish-now`. Keep schema regression
  tests in the required live-adapter gate.
- Nina: Existing tests prove storage keys, AI lineage, credential references, and provider failure
  details are client-safe. This pass adds explicit Instagram provider error redaction coverage.
- Leo: Celery scans remain queue-oriented and tenant-scoped. Live adapter goals must keep provider
  side effects behind config/flags and preserve five-attempt retry limits with jitter.
- Hannah: Evidence is sufficient for Goal L only. It does not satisfy App Review, public media URL,
  live staging publish, or final release-readiness proof.

## Evidence Matrix

| Requirement                              | Evidence                                                                                                                                                                                                       | Goal L result                                                             |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Tenant isolation                         | `backend/tests/test_content_ops_api.py` workspace scope, role gates, retry/list filters, task tenant scans; `backend/tests/test_content_ops_publisher.py` wrong-tenant preflight and task tenant targeting     | Covered for current fakeable surfaces                                     |
| API contracts                            | `backend/tests/test_schema_regressions.py` pins Content Ops paths, action serializers, publish-attempt states, channel enums, readiness enums, `credential_ref` write-only, and asset `storage_key` write-only | Covered for current contract                                              |
| Token boundaries                         | `test_publishing_identity_create_hides_credentials_and_readiness`; provider boundaries still do not decrypt or call Meta by default                                                                            | Covered for current disabled provider state                               |
| No secret logging / safe provider errors | Facebook retryable/terminal provider error tests and Instagram provider error redaction test prove token-like fragments persist as generic safe details                                                        | Covered by tests; log inspection still required in staging goals          |
| Credential handling                      | `credential_ref` is write-only and server-owned readiness fields cannot be client-forced                                                                                                                       | Covered for API writes; live token retrieval remains future work          |
| Storage and public URL leakage           | Asset upload/download tests hide `storage_key` and reject unsafe paths; export tests omit `storage_key` and `ai_lineage`                                                                                       | Covered for private/authenticated paths; public CDN proof remains missing |
| Aggregate-only reporting                 | Report overview/posts and metric refresh tests expose aggregate metrics, not viewer/commenter/reaction user IDs                                                                                                | Covered for current reporting endpoints                                   |
| Live publishing disabled                 | API contract and tests confirm `publish-now` is not implemented and default publishers fail closed                                                                                                             | Covered                                                                   |

## Remaining Blockers Before Live Adapters

- Meta App Review packet is not locked for live publishing permissions.
- Public HTTPS media URL/CDN proof is missing; current asset download endpoint is authenticated and
  not suitable for Meta fetches.
- Live Facebook Page and Instagram provider adapters are not implemented.
- Live token retrieval/decryption path has not been wired or staging-proven for Content Ops.
- Staging publish evidence for Facebook and Instagram does not exist.
- Final ADinsights release preflight remains expected to report `GATE_BLOCK` until App Review,
  staging proof, security sign-off, and release gates are complete.

## Required Review Gates

- Raj: cross-stream/release architecture review for docs plus backend test scope.
- Sofia: API contract and schema regression review.
- Nina: secrets, PII, tenant isolation, and credential-boundary review.
- Leo: Celery scheduler/retry review before Goals O/P.
- Hannah: runbook/evidence proof review before Goals R/S/T.

## Validation Commands

Run for Goal L:

```bash
backend/.venv/bin/pytest -q backend/tests/test_content_ops_publisher.py backend/tests/test_content_ops_api.py backend/tests/test_schema_regressions.py
make backend-lint && make backend-test
make adinsights-preflight PROMPT="Content Ops Goal L contract and security review docs/tests only; verify tenant isolation API contracts token boundaries no secret logging safe provider errors credential handling aggregate-only reporting; no live publishing activation"
```

Expected preflight state: `GATE_BLOCK` until later live-publishing goals provide App Review,
public media URL, staging evidence, and final release approvals.

## Validation Results

- `backend/.venv/bin/pytest -q backend/tests/test_content_ops_publisher.py backend/tests/test_content_ops_api.py backend/tests/test_schema_regressions.py` passed.
- `make backend-lint && make backend-test` passed.
- `git diff --check -- backend/tests/test_content_ops_publisher.py docs/project/content-operations-api-contract.md docs/project/evidence/content-operations/2026-06-10-goal-l-contract-security-review.md docs/ops/doc-index.md docs/ops/agent-activity-log.md` passed.
- Scope gatekeeper advisory packet: `ESCALATE_CROSS_SCOPE` for `docs` plus `backend`, requiring Raj, Hannah, and Sofia review.
- Contract guard advisory packet: `PASS_NO_CONTRACT_CHANGE`; no breaking contract change detected for Goal L docs/tests scope.
- ADinsights preflight packet persisted at `docs/project/evidence/content-operations/preflight-2026-06-10-goal-l-contract-security/`.
- ADinsights preflight result: `GATE_BLOCK`, with expected architecture scope and contract/security follow-up warnings until later live-publishing gates are satisfied.
