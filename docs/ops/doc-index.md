# Documentation Index & Wayfinding

Purpose: cold-start map for ADinsights so every session knows where to look, how the docs link, and how to keep the index fresh.

## Session Cold-Start Prompt
You are resuming work on ADinsights with a cold memory. Rebuild context and keep docs cross-linked so future sessions can navigate quickly.

Quick-use note: paste the checklist below as your first message each session, or skim this section to warm up. If memory is low later, return here or to `docs/ops/agent-activity-log.md` for a fast refresh.

Core wayfinding targets (open/skim in this order):
- AGENTS.md — global guardrails (stack boundaries, RLS/tenant rules, schedules, testing matrix, secrets/PII policy).
- README.md — repo structure, roadmap phases, quick start, default endpoints.
- docs/workstreams.md — per-folder scope, owners/backups, KPIs, tests, DoD (sets which folder a PR may touch).
- docs/project/phase1-execution-backlog.md — live status board (stream IDs, personas, priority, commands).
- docs/task_breakdown.md — immediate next actions and gaps.
- docs/project/vertical_slice_plan.md — Airbyte → dbt → backend → frontend → runbooks sequence to keep builds green.
- docs/security/uac-spec.md — privilege model and UAC rollout references.
- docs/orchestration.md — task wiring/orchestration notes.
- docs/runbooks/ (folder) — operational docs; open relevant runbook for the area you touch.
- docs/ops/agent-activity-log.md — recent changes/commits/schedules.
- docs/design-system.md and docs/project/frontend-design-system-plan.md — frontend design/UX references.
- docs/runbooks/deployment.md, docs/BI/ (folder), deploy/ — deployment/BI configs and guidance.

Linkage reminders:
- AGENTS.md governs everything: stack, health endpoints, RLS, secrets, schedules, test matrix.
- docs/workstreams.md maps top-level folders → owners/tests/DoD; scope PRs to one folder unless Raj (integration) + Mira (architecture) are engaged.
- phase1-execution-backlog is the live board; align sprint picks with it and note dependencies.
- task_breakdown + vertical_slice_plan define priority and sequencing; follow them to avoid breaking the build.
- security/uac-spec + AGENTS enforce tenant isolation and secrets hygiene.
- agent-activity-log shows what changed last session to avoid duplication.
- README.md is the quick repo map and command cheat-sheet.
- runbooks/orchestration must be updated when behavior or observability changes.

Navigation checklist for cold starts:
1) AGENTS.md → extract guardrails/schedules/tests.
2) docs/workstreams.md → owners/folders/tests/DoD.
3) phase1-execution-backlog → open P1s + dependencies.
4) task_breakdown + vertical_slice_plan → confirm sequencing.
5) agent-activity-log → recent changes.
6) README.md → repo layout + commands.
7) Open area-specific docs (design-system, UAC spec, deployment runbook, orchestration).

Working rules to restate every session:
- Keep changes to a single top-level folder unless Raj/Mira sign off.
- Preserve tenant isolation (SET app.tenant_id + RLS) and secrets hygiene (no secrets in logs/commits; AES-GCM per-tenant DEKs).
- Use exponential backoff with jitter (base 2, max 5 attempts).
- Emit structured JSON logs with tenant_id, task_id, correlation_id.
- Run canonical tests per folder before calling done (per AGENTS/workstreams).

## Key Docs Map
| Path | Role | Update triggers | Related docs |
| --- | --- | --- | --- |
| AGENTS.md | Global guardrails (stack, schedules, tests, secrets/PII) | Any change to stack, schedules, or guardrails | docs/workstreams.md, docs/task_breakdown.md |
| README.md | Repo overview, structure, quick start, endpoints | New components, commands, or layout changes | AGENTS.md |
| docs/workstreams.md | Folder scopes, owners, KPIs, tests, DoD | New stream, owner change, test matrix tweak | AGENTS.md, phase1-execution-backlog |
| docs/project/phase1-execution-backlog.md | Live status board per stream | Status/priority/command changes | docs/task_breakdown.md |
| docs/project/feature-catalog.md | Consolidated feature list (built/in progress/planned) | Feature status changes | docs/task_breakdown.md, phase1-execution-backlog.md |
| docs/project/feature-ownership-map.md | Feature ownership + tests + runbooks | Owner or scope changes | docs/workstreams.md |
| docs/project/api-contract-changelog.md | API payload change log | API schema changes | docs/workstreams.md, frontend/README.md |
| docs/runbooks/release-checklist.md | Release readiness checklist | Release process changes | docs/runbooks/deployment.md |
| docs/ops/data-quality-checklist.md | Data quality validation checklist | Modeling or ingestion changes | dbt/README.md, docs/runbooks/operations.md |
| docs/ops/risk-register.md | Operational risk register | Risk status changes | docs/runbooks/operations.md |
| docs/ops/adr-log.md | Architecture decision log | Architecture changes | AGENTS.md, docs/workstreams.md |
| docs/project/user-journey-map.md | Core user workflows | Product workflow updates | docs/task_breakdown.md |
| docs/runbooks/support-playbook.md | Support triage steps | Support process updates | docs/runbooks/operations.md |
| docs/ops/escalation-matrix.md | Incident escalation routing | On-call/escalation changes | docs/ops/risk-register.md |
| docs/ops/alert-thresholds-escalation.md | Default alert thresholds + escalation workflow (Owner: Omar/Hannah) | Alert tuning or contact changes | docs/runbooks/alerting.md, docs/ops/escalation-matrix.md |
| docs/ops/alerts-runbook.md | Nightly sync alert response steps (Owner: Omar/Hannah) | Airbyte/dbt health or nightly sync changes | docs/runbooks/operations.md |
| docs/ops/metrics-scrape-validation.md | Prometheus scrape + `/metrics/app/` smoke steps (Owner: Omar/Hannah) | Metrics endpoint or scrape config changes | docs/runbooks/operations.md |
| docs/ops/observability-stability-tests.md | Observability stability tests + runbook QA checklist (Owner: Omar/Hannah) | Logging/metrics/alerting changes | docs/ops/alert-thresholds-escalation.md |
| docs/ops/stream6-definition-of-done.md | Stream 6 observability completion checklist (Owner: Omar/Hannah) | Stream 6 DoD updates | docs/workstreams.md |
| docs/ops/slo-sli-summary.md | SLO/SLI quick reference | SLO updates | docs/ops/slo-sli.md |
| docs/project/metrics-glossary.md | Metrics definitions | Metric changes | dbt/README.md, docs/project/api-contract-changelog.md |
| docs/ops/dashboard-links.md | Monitoring dashboard index | Dashboard changes | docs/ops/slo-sli-summary.md |
| docs/ops/postmortem-template.md | Incident postmortem template | Process changes | docs/ops/escalation-matrix.md |
| docs/project/data-lineage-map.md | High-level data flow | Pipeline changes | docs/project/vertical_slice_plan.md |
| docs/ops/ai-onboarding-checklist.md | AI session recontext checklist | Onboarding process changes | AGENTS.md |
| docs/ops/testing-cheat-sheet.md | Test commands quick ref | Test matrix changes | docs/workstreams.md, AGENTS.md |
| docs/project/feature-flags-reference.md | Feature flags/entitlements summary | UAC changes | docs/security/uac-spec.md |
| docs/project/definition-of-done.md | Completion criteria | DoD changes | docs/workstreams.md |
| docs/ops/escalation-rules.md | When to escalate to Raj/Mira | Escalation policy updates | docs/workstreams.md |
| docs/ops/ai-session-resume-template.md | Copy/paste session resume | Recontext process changes | AGENTS.md |
| docs/ops/decision-checklist.md | When to update docs | Process changes | AGENTS.md, doc-index |
| docs/ops/test-failure-triage.md | Test failure steps | QA process changes | docs/ops/testing-cheat-sheet.md |
| docs/ops/new-engineer-onboarding.md | New engineer onboarding guide | Onboarding changes | AGENTS.md |
| docs/ops/human-onboarding-guide.md | Human engineer onboarding guide | Onboarding changes | AGENTS.md |
| docs/ops/confused-engineer-walkthrough.md | Low-context walkthrough | Onboarding changes | AGENTS.md |
| docs/ops/documentation-snob-review.md | Documentation critique | Doc quality reviews | docs/ops/doc-index.md |
| docs/ops/golden-path-onboarding.md | Single best onboarding path | Onboarding changes | AGENTS.md |
| docs/ops/cold-start-walkthrough.md | Actual cold start attempt | Onboarding changes | docs/ops/golden-path-onboarding.md |
| docs/task_breakdown.md | Immediate next actions and gaps | New tasks/gaps discovered | vertical_slice_plan |
| docs/project/vertical_slice_plan.md | End-to-end slice sequencing | Workflow/order changes | docs/task_breakdown.md |
| docs/security/uac-spec.md | UAC/privilege model | Security/RBAC changes | AGENTS.md |
| docs/orchestration.md | Task wiring/orchestration notes | Scheduler/flow changes | docs/runbooks/* |
| docs/runbooks/* | Operational runbooks | Behavior, observability, or SOP changes | docs/orchestration.md |
| docs/ops/agent-activity-log.md | Recent changes/commits/schedules | After each session/change | AGENTS.md |
| docs/design-system.md | Design tokens/guidelines | Design system changes | frontend-design-system-plan |
| docs/project/frontend-design-system-plan.md | Frontend plan and UX notes | UX roadmap changes | docs/design-system.md |
| docs/runbooks/deployment.md | Deployment steps | Deploy process changes | deploy/, docs/BI/ |
| docs/BI/ | BI configs | BI/dashboard changes | deploy/, backend/dbt contracts |
| deploy/ | Deployment infra notes | Compose/infra changes | docs/runbooks/deployment.md |
| docs/PROGRAM-NOTES.md | Session warm-up summary | Orientation flow changes | AGENTS.md, docs/ops/doc-index.md |
| backend/README.md | Backend service setup/KMS/RLS/API endpoints | Backend setup or contract changes | AGENTS.md, docs/workstreams.md |
| frontend/README.md | Frontend shell setup/auth/mocks | Frontend auth/data flow changes | docs/design-system.md, frontend-design-system-plan |
| dbt/README.md | dbt project setup/macros/models | dbt build/test/connector changes | docs/task_breakdown.md, vertical_slice_plan |
| infrastructure/airbyte/README.md | Airbyte compose/env/scheduling/templates | Ingestion scheduling or connector bootstrap changes | docs/workstreams.md Stream 1, AGENTS schedules |
| infrastructure/dbt/README.md | dbt infra prerequisites/profiles | Warehouse/profile/orchestration changes | docs/orchestration.md |
| deploy/README.md | Deployment steps + KMS requirements | Deploy flow/KMS env changes | docs/runbooks/deployment.md |
| qa/README.md | Playwright E2E usage (mock/live) | QA setup/run changes | frontend/README.md |
| integrations/exporter/README.md | Exporter CLI for PDF/PNG reports | Export/report pipeline changes | docs/task_breakdown.md alerts/summaries |
| bi/superset/README.md | Superset exports (datasets/dashboards/subscriptions) | BI asset changes | docs/BI/, deploy/ |

## Documentation Hygiene
- When adding or updating a doc/README/runbook: add an index entry here (path, purpose, owner persona, related docs) and log a one-liner in docs/ops/agent-activity-log.md with timestamp + summary + commit hash (if any).
- Place new docs in the closest logical folder (docs/runbooks for ops, docs/project for plans, docs/design for UX). Add back-links to related docs (e.g., “See also: docs/workstreams.md Stream 3”).
- When deprecating/moving docs: add a redirect note at the top of the old file pointing to the new path and update this index.
- When behavior or observability changes: update the relevant runbook and docs/orchestration.md; then log it in agent-activity-log with timestamp + summary.

After rebuilding context, draft the sprint/task plan with stream/ID, scope (folder), acceptance criteria, tests/commands, observability/logging, docs to update. Stop if work crosses folders and flag Raj/Mira.
