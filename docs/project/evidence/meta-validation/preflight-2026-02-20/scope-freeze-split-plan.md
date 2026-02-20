# Scope Freeze + Split Ownership (2026-02-20)

This effort is a **cross-stream integration change** spanning:
- `backend/`
- `frontend/`
- `dbt/`
- `infrastructure/airbyte/`
- `qa/`
- `docs/`
- `.github/` and root governance files

Per repository guardrails, review ownership is assigned up front:
- **Raj**: Cross-Stream Integration Lead (required co-review for multi-folder integration sequencing)
- **Mira**: Architecture/Refactor reviewer (required for codebase-wide refactor/scope-control risk)

## Split Branch Tracks (short-lived)

- `codex/track-docs-governance`: `docs/*` contracts/runbooks/governance
- `codex/track-backend-meta-pages`: `backend/*` API/integrations/models/tasks/tests
- `codex/track-frontend-meta-pages`: `frontend/*` routes/components/state/tests
- `codex/track-dbt-contracts`: `dbt/*` schemas/seeds/selectors
- `codex/track-airbyte-contracts`: `infrastructure/airbyte/*` connector specs/readme/scripts
- `codex/track-qa-e2e`: `qa/*` e2e updates
- `codex/track-github-root-governance`: `.github/*` and root governance/config files

## Current Gate Evidence

- Contract script: `python3 infrastructure/airbyte/scripts/check_data_contracts.py` -> PASS
- Preflight skillchain: `run_preflight_skillchain.py` -> `GATE_BLOCK`
  - scope status: `ESCALATE_ARCH_RISK`
  - release blocker: architecture-level scope risk remains until split branches are executed and reviewed

## Required next gate actions

1. Materialize folder-scoped PRs from the split tracks above.
2. Attach per-track test evidence to each PR.
3. Capture Raj + Mira signoff notes in each track.
4. Re-run preflight skillchain with updated changed-file scope per track.
