# Meta Integration V3 Sign-Off Checklist (Raj + Mira)

Timestamp (America/Jamaica): 2026-02-19T20:45:00-0500  
Scope: Stabilize-first implementation and release-gate readiness review.

## 1) Engineering gate status

- Backend checks: pass  
  `ruff check backend && pytest -q backend`
- Frontend checks: pass  
  `cd frontend && npm ci && npm test -- --run && npm run build`
- dbt checks: pass (wrapper flow)
  - `make dbt-deps`
  - `./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' run --select staging`
  - `./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' snapshot`
  - `./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' run --select marts`
- Airbyte config render: pass  
  `cd infrastructure/airbyte && docker compose config`
- Data-contract checker: pass  
  `python3 infrastructure/airbyte/scripts/check_data_contracts.py`
- QA Playwright Meta spec: pass  
  `cd qa && npm ci && npx playwright test tests/meta-integration.spec.ts --project=chromium-desktop`

## 2) Preflight packets

Artifacts:
- `docs/project/evidence/meta-validation/preflight-2026-02-19/router-packet.json`
- `docs/project/evidence/meta-validation/preflight-2026-02-19/scope-packet.json`
- `docs/project/evidence/meta-validation/preflight-2026-02-19/contract-packet.json`
- `docs/project/evidence/meta-validation/preflight-2026-02-19/release-packet.json`

Current packet outcomes:
- Scope: `ESCALATE_ARCH_RISK`
- Contract: `WARN_POSSIBLE_CONTRACT_CHANGE`
- Release readiness: `GATE_BLOCK` (blocked by cross-stream architecture scope risk, not failing tests)

## 3) PR split execution pack

- Execution guide: `docs/project/meta-integration-v3-pr-execution.md`
- Path manifests:
  - `docs/project/pr-track-manifests/backend.txt`
  - `docs/project/pr-track-manifests/dbt.txt`
  - `docs/project/pr-track-manifests/frontend.txt`
  - `docs/project/pr-track-manifests/infrastructure-airbyte.txt`
  - `docs/project/pr-track-manifests/qa.txt`
  - `docs/project/pr-track-manifests/docs.txt`

## 4) Operator-only staging validation

Pending completion:
- `docs/project/evidence/meta-validation/2026-02-19T20-35-00-0500.md`

Required operator evidence:
1. Fresh Meta Test App OAuth connect (`/api/integrations/meta/oauth/start` and `/exchange`)
2. Asset connect + provision + sync
3. `/api/meta/accounts/` returns at least one account
4. `/api/meta/insights/?account_id=<id>&level=ad&since=<today-30>&until=<yesterday>` returns rows
5. Access Token Debugger confirmation
6. Graph API Explorer parity checks

## 5) Approvals

- Raj (Cross-Stream Integration Lead): pending
- Mira (Architecture/Refactor): pending
- Sofia (Backend): pending
- Maya (Integrations): pending
- Priya (dbt): pending
- Lina (Frontend/QA UX): pending
