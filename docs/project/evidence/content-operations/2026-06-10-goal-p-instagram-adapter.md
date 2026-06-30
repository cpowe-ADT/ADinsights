# Goal P Evidence: Live Instagram Publisher Adapter

Date: 2026-06-10
Scope: `backend/` plus required docs/evidence updates
Status: implemented, disabled by default, not production-enabled

## Summary

Goal P adds the real Instagram Graph publishing adapter behind
`CONTENT_OPS_META_INSTAGRAM_BETA=0` by default. The adapter is wired to the existing Content Ops
Instagram container state machine:

1. create media container with `POST /{ig-user-id}/media`
2. poll container status with `GET /{container-id}?fields=status_code,status`
3. publish with `POST /{ig-user-id}/media_publish`

The default runtime remains fail-closed with `provider_not_configured` until the beta flag is
explicitly enabled in a gated environment.

## Implementation Evidence

- Added `backend/content_ops/instagram_graph.py`.
- Added `CONTENT_OPS_META_INSTAGRAM_BETA` to `backend/core/settings.py` and `backend/.env.sample`.
- Updated `backend/content_ops/publisher.py` so the default Instagram publisher resolves to the
  disabled publisher unless the beta flag is enabled.
- Added `meta_page_id` to the Instagram container payload so create, poll, and publish paths can
  resolve the tenant-local selected `MetaPage` across separate worker ticks.
- Preserved existing fakeable publisher injection for deterministic tests and dry-runs.

## Security / Isolation Evidence

- Token lookup is tenant-scoped by `tenant_id` and selected `meta_page_id`.
- The adapter prefers the active `MetaConnection` user token and falls back to the selected Page
  token only inside the provider boundary.
- Graph requests use bearer authorization headers; tests prove tokens are not placed in URLs or
  request bodies.
- Provider errors persist only safe retryable/terminal failure details through the existing
  sanitizer.
- Cross-tenant selected Page token lookup is rejected and does not call the Graph client.

## Test Evidence

Focused command run:

```bash
backend/.venv/bin/pytest -q backend/tests/test_content_ops_publisher.py
```

Result:

```text
55 passed
```

Additional validation:

```bash
backend/.venv/bin/pytest -q backend/tests/test_content_ops_publisher.py backend/tests/test_content_ops_api.py backend/tests/test_schema_regressions.py backend/tests/test_tasks.py
make backend-lint
make backend-test
git diff --check
```

Results:

```text
focused Content Ops/API/schema/task suite: passed
backend lint: passed
backend tests: passed
diff whitespace check: passed
```

Advisory gates:

```bash
backend/.venv/bin/python docs/ops/skills/adinsights-scope-gatekeeper/scripts/evaluate_scope.py ...
backend/.venv/bin/python docs/ops/skills/adinsights-contract-guard/scripts/evaluate_contract.py ...
backend/.venv/bin/python docs/ops/skills/adinsights-release-readiness/scripts/run_preflight_skillchain.py ...
```

Results:

```text
scope: ESCALATE_ARCH_RISK
contract: WARN_POSSIBLE_CONTRACT_CHANGE
release: GATE_BLOCK
```

Persisted packets:

- `docs/project/evidence/content-operations/preflight-2026-06-10-goal-p-instagram-adapter/`

Coverage added:

- Instagram Graph success path creates a container, polls status, publishes media, and persists the
  returned media ID.
- Instagram Graph client uses bearer token headers and avoids token material in URLs/bodies.
- Cross-tenant token lookup fails closed without a Graph call.
- Retryable provider errors remain secret-safe in persisted failure details.

## Launch Status

Not ready for production live publishing.

Remaining blockers:

- Meta App Review approval for the selected Instagram permission family.
- Credentialed staging Instagram publish proof.
- Redacted logs/metrics evidence from staging.
- Raj, Maya, Nina, Leo, Hannah, and release readiness signoff.
- Final Goal T preflight must resolve current `GATE_BLOCK` status before launch.
