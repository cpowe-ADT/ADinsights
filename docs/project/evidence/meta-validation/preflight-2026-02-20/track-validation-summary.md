# Track Validation Summary (2026-02-20)

## Review ownership (required)

- Cross-stream integration owner: **Raj** (required)
- Architecture/refactor owner: **Mira** (required)

## Split tracks and commits

- `codex/track-docs-governance` @ `1763fe6`
- `codex/track-backend-meta-pages` @ `72505a7b`
- `codex/track-frontend-meta-pages` @ `c91f2ed9`
- `codex/track-dbt-contracts` @ `3dc5e1b2`
- `codex/track-airbyte-contracts` @ `f85cabd2`
- `codex/track-qa-e2e` @ `92764e2a`
- `codex/track-github-root-governance` @ `7e2c3495`

## Contract checks

- `python3 infrastructure/airbyte/scripts/check_data_contracts.py` -> PASS
- `test_data_contract_checks.py` -> test target file is missing in-repo and must be restored or path-corrected.

## Canonical validation evidence

- Backend track:
  - `ruff check backend` -> PASS
  - `pytest -q backend` -> FAIL (cross-folder coupling: backend test expects docs artifact file)
- Frontend track:
  - `npm ci` -> FAIL (workspace lock mismatch without root lockfile track)
  - `npm test -- --run` -> FAIL (missing root workspace deps in isolated worktree)
  - `npm run build` -> FAIL (same dependency/type-resolution issue)
- dbt track:
  - `make dbt-deps` -> PASS
  - `dbt run --select staging` -> FAIL (DuckDB file lock)
  - `dbt snapshot` -> PASS earlier in unsplit root run, but in split worktree blocked by lock path contention
  - `dbt run --select marts` -> FAIL (upstream staging deps absent in failed run)
- Airbyte track:
  - `docker compose config` -> FAIL in isolated worktree due missing local `.env`; PASS in root workspace context.

## Preflight status by track

All split tracks re-ran the preflight skillchain and moved to `GATE_WARN` (no `GATE_BLOCK`), with warnings for scope clarification and contract follow-up on dbt/airbyte tracks.

## Raj + Mira signoff notes

- Raj signoff:
  - Status: `PENDING`
  - Notes:
- Mira signoff:
  - Status: `PENDING`
  - Notes:
