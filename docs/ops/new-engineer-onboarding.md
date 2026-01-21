# New Engineer Onboarding (v0.1)

Purpose: standard onboarding for humans and AI engineers.

## First Day
- Read `AGENTS.md` and `docs/ops/doc-index.md`.
- Review `docs/workstreams.md` to understand owners and scope.
- Skim `docs/project/feature-catalog.md` and `docs/project/feature-ownership-map.md`.

## Environment Setup
- Run `scripts/dev-launch.sh` (or use docker-compose.dev.yml).
- Verify health endpoints `/api/health/`, `/api/health/airbyte/`, `/api/health/dbt/`, `/api/timezone/`.
- Run frontend `npm test -- --run` and `npm run build`.

## First PR
- Pick a task from `docs/project/phase1-execution-backlog.md`.
- Stay within one top-level folder.
- Run the canonical tests for that folder.
- Update docs/runbooks if behavior changes.

## Getting Help
- Use the escalation rules in `docs/ops/escalation-rules.md`.
