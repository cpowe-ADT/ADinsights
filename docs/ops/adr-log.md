# Architecture Decision Log (ADR) (v0.1)

Purpose: record major architectural decisions with rationale and impact.

## ADR-0001 — Stack Baseline
- **Decision**: Django/DRF/Celery backend, React/Vite frontend, Airbyte OSS, dbt.
- **Rationale**: Aligns with team expertise and current codebase; supports multi-tenant analytics.
- **Implications**: Future changes must preserve this stack per `AGENTS.md`.
- **Status**: Accepted.

## ADR-0002 — Tenant Isolation
- **Decision**: Enforce `SET app.tenant_id` per request and DB-level RLS.
- **Rationale**: Hard guardrail for data segregation.
- **Implications**: All API access must be tenant-scoped.
- **Status**: Accepted.
