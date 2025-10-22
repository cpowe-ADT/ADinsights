# GitHub Milestones & Labels — ADinsights

Use this guide to keep GitHub issues and pull requests aligned with the six workstreams. Apply the labels and milestones below to new issues/PRs and update them at the end of each sprint.

## Milestones

| Milestone                 | Target Date | Scope                                                                                          |
| ------------------------- | ----------- | ---------------------------------------------------------------------------------------------- |
| `MVP-backend-api`         | 2025-02-14  | Combined metrics endpoint, Airbyte/dbt telemetry APIs, auth hardening.                         |
| `MVP-frontend-dashboards` | 2025-02-28  | Live dashboard data wiring, filter bar, Data Health UI, credential & alert management screens. |
| `MVP-dbt-warehouse`       | 2025-02-28  | SCD2 dimensions, pacing/geo marts, freshness + tests, metric dictionary export.                |
| `MVP-airbyte-ingestion`   | 2025-03-07  | Production-grade Meta/Google connectors, sync scheduling, telemetry hooks, alerting.           |
| `MVP-ops-observability`   | 2025-03-14  | Deployment automation, monitoring stack, incident runbooks, security checklist.                |
| `MVP-launch`              | 2025-03-28  | Final UAT, tenant onboarding, go-live checklist signed off; production deployment.             |

## Labels

Label taxonomy keeps PRs and issues scoped to a single top-level folder as required by `AGENTS.md`.

| Label                | Color     | Usage                                                              |
| -------------------- | --------- | ------------------------------------------------------------------ |
| `area/backend`       | `#1f6feb` | Django/DRF/Celery changes under `backend/`.                        |
| `area/frontend`      | `#bf3989` | React/TanStack/Leaflet work under `frontend/`.                     |
| `area/dbt`           | `#0969da` | dbt models, macros, seeds, tests under `dbt/`.                     |
| `area/airbyte`       | `#1a7f37` | Airbyte connectors, sync orchestration, `infrastructure/airbyte/`. |
| `area/ops`           | `#8a4600` | Deployment, CI/CD, alerting, observability, scripts.               |
| `area/docs`          | `#8250df` | Documentation, design assets, runbooks, prompts.                   |
| `type/feature`       | `#0e8a16` | Net-new functionality.                                             |
| `type/fix`           | `#d73a4a` | Bug fixes, regressions.                                            |
| `type/chore`         | `#6e7781` | Refactors, dependency updates, infrastructure chores.              |
| `priority/high`      | `#cf222e` | Must-land this sprint; blockers for other workstreams.             |
| `priority/medium`    | `#f0883e` | Important but not blocking.                                        |
| `priority/low`       | `#e3b341` | Nice-to-have or backlog grooming.                                  |
| `status/discovery`   | `#54aeff` | Research or spike; output is plan/prototype.                       |
| `status/in-progress` | `#fbca04` | Active development.                                                |
| `status/review`      | `#c69026` | Awaiting code review.                                              |
| `status/blocked`     | `#b60205` | Waiting on external dependency.                                    |

## Maintenance Checklist

- Create milestones in GitHub → Issues → Milestones using the names/dates above.
- Bulk-apply area labels to existing issues/PRs to reflect current ownership.
- During sprint planning:
  - Assign issues to appropriate milestone and area label.
  - Update milestone dates if dependencies shift.
- During standups:
  - Move issues between `status/*` labels to reflect actual state.
- At sprint review:
  - Close milestones when all issues complete or reassign remaining tasks to the next milestone.
  - Update this document if new workstreams emerge.

Maintaining consistent milestones and labels ensures parallel workstreams remain decoupled and merge cleanly into `main`.
