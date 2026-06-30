## Scope Gatekeeper Advisory Packet

- Schema version: `1.1.0`
- Status: `ESCALATE_ARCH_RISK`
- Advisory-only: `True`
- Contract risk signal: `True`
- Evidence source: `explicit_paths`
- Touched folders: `backend, docs`
- Required reviewers: `Raj, Mira, Sofia, Hannah`
- Invoke contract guard: `True`
- Invoke release readiness: `True`

### Required Tests By Folder

- `backend`
  - `ruff check backend && pytest -q backend`
- `docs`
  - `docs-only change (no canonical code test)`

### Required Docs Updates

- `docs/ops/doc-index.md`
- `docs/ops/agent-activity-log.md`

### Recommended Next Action

- Route to Raj + Mira before implementation and capture architecture rationale/rollback notes.

### Rationale

- Evidence source: explicit_paths.
- Detected 12 path(s): backend/content_ops/instagram_graph.py, backend/content_ops/publisher.py, backend/core/settings.py, backend/.env.sample, backend/tests/test_content_ops_publisher.py, docs/runbooks/content-operations-publishing.md, docs/project/feature-flags-reference.md, docs/project/api-contract-changelog.md, docs/project/content-operations-current-state.md, docs/project/content-operations-implementation-backlog.md, docs/project/evidence/content-operations/2026-06-10-goal-p-instagram-adapter.md, docs/ops/agent-activity-log.md.
- Touched top-level folders: backend, docs.
- Architecture-sensitive paths detected: backend/core/settings.py
- Contract-risk signal detected: docs/project/api-contract-changelog.md

### Contract Risk Reasons

- Matched contract-risk pattern on 'docs/project/api-contract-changelog.md'.

### Evidence

- `scope_path` `backend/content_ops/instagram_graph.py` (strength=0.8, source=explicit_paths)
- `scope_path` `backend/content_ops/publisher.py` (strength=0.8, source=explicit_paths)
- `scope_path` `backend/core/settings.py` (strength=0.8, source=explicit_paths)
- `scope_path` `backend/.env.sample` (strength=0.8, source=explicit_paths)
- `scope_path` `backend/tests/test_content_ops_publisher.py` (strength=0.8, source=explicit_paths)
- `scope_path` `docs/runbooks/content-operations-publishing.md` (strength=0.8, source=explicit_paths)
- `scope_path` `docs/project/feature-flags-reference.md` (strength=0.8, source=explicit_paths)
- `scope_path` `docs/project/api-contract-changelog.md` (strength=0.8, source=explicit_paths)
- `scope_path` `docs/project/content-operations-current-state.md` (strength=0.8, source=explicit_paths)
- `scope_path` `docs/project/content-operations-implementation-backlog.md` (strength=0.8, source=explicit_paths)
- `scope_path` `docs/project/evidence/content-operations/2026-06-10-goal-p-instagram-adapter.md` (strength=0.8, source=explicit_paths)
- `scope_path` `docs/ops/agent-activity-log.md` (strength=0.8, source=explicit_paths)
- `architecture_sensitive_match` `backend/core/settings.py` (strength=1.0, source=rules)
- `contract_risk_match` `docs/project/api-contract-changelog.md` (strength=0.9, source=rules)
