## Contract Guard Decision Packet

- Schema version: `1.0.0`
- Contract status: `WARN_POSSIBLE_CONTRACT_CHANGE`
- Breaking change: `False`
- Surfaces touched: `contract_docs`
- Required reviewers: `Raj`
- CI strict enabled: `False`
- CI strict level: `breaking_only`
- CI would fail: `False`

### Required Docs Updates

- None

### Required Tests

- None

### Next Actions

- Confirm downstream consumers for touched contract surfaces.
- Validate data contract checks before merge.

### Rationale

- Evidence source: explicit_paths.
- Detected 13 path(s): backend/content_ops/instagram_graph.py, backend/content_ops/publisher.py, backend/core/settings.py, backend/.env.sample, backend/tests/test_content_ops_publisher.py, docs/runbooks/content-operations-publishing.md, docs/project/feature-flags-reference.md, docs/project/api-contract-changelog.md, docs/project/content-operations-current-state.md, docs/project/content-operations-implementation-backlog.md, docs/project/evidence/content-operations/2026-06-10-goal-p-instagram-adapter.md, docs/ops/agent-activity-log.md, docs/ops/doc-index.md.
- Surface 'contract_docs' matched paths: docs/project/api-contract-changelog.md.
