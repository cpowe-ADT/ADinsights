# Phase 0 – Backlog Validation Playbook

Phase 0 ensures every workstream described in `docs/workstreams.md` has the
correct backlog, ownership, and sequencing before engineers begin parallel
implementation. Use this checklist during the first 1–2 days of the sprint.

## Objectives
- Map audit findings (tenant isolation, secrets, observability, testing) to
  actionable tickets per stream.
- Confirm each workstream owner signs off on their KPIs/Definition of Done.
- Surface cross-folder or cross-stream work early so Raj (Integration Lead) and
  Mira (Architecture/Refactor) can co-own plans before coding begins.

## Participants
- Stream owners + backups listed in `docs/workstreams.md`.
- Raj for anything spanning multiple top-level folders.
- Mira for refactors or shared libraries.
- Scrum facilitator to capture decisions and update the backlog tool.

## Agenda (repeat per workstream)
1. **KPI & DoD review** – verify success criteria, observability needs, and
   testing commands remain accurate.
2. **Ticket audit** – ensure open issues cover:
   - Tenant isolation gaps (backend, Celery, dbt contracts).
   - Secrets/KMS and configuration hygiene.
   - Monitoring/alerting additions (metrics, logs, dashboards).
   - Test automation (unit, integration, dbt, frontend, E2E).
3. **Dependency check** – document upstream/downstream sequencing (e.g.,
   Airbyte → dbt → backend → frontend) and note blocking items.
4. **Cross-stream review** – flag any ticket touching more than one top-level
   folder; assign Raj + Mira as co-reviewers and plan PR coordination.
5. **Action log** – capture owner, ETA, and link to backlog item/plan section.

## Output Artifacts
- Updated backlog/issue tracker with:
  - Tagged owner + stream.
  - Linked KPI/DoD reference.
  - Noted dependencies and reviewers.
- Meeting notes stored under `docs/logs/` (choose the relevant stream log) so
  future agents know which commitments were made.

## Parallelization Guidance
- Streams without dependency blockers (e.g., Secrets/KMS vs. Frontend UX) can
  start immediately after their Phase 0 review.
- Work that depends on upstream schema/API changes must wait until the upstream
  owner confirms their tickets are groomed and scheduled.
- Any deviation from single-folder scope requires Raj’s approval plus Mira’s
  sign-off if refactor-wide impacts exist.

## Communication Cadence
- **Daily async update** in the shared channel noting checklist progress per
  stream.
- **Weekly integration sync** led by Raj to make sure cross-stream items stay on
  schedule.
- **Escalations**: post blockers in the channel and tag the relevant owner +
  Raj/Mira immediately.

## Completion Criteria
- Every workstream has:
  - Validated KPIs/DoD still accurate.
  - Tickets covering critical remediation areas.
  - Owners assigned with clear dependencies.
- Cross-stream tickets list both stream leads as reviewers.
- Backlog reflects scheduling so Phase 1 implementation can begin confidently.

## AI/Persona Simulation Prompt
When live participants are unavailable, simulate each workstream review by
instantiating the owner/backups listed in `docs/workstreams.md`. Copy the prompt
below and fill in the bracketed values:

```
You are [Owner Persona], responsible for the [Workstream Name] track
scoped to [folders]. Review the Phase 0 backlog for this stream using
docs/workstreams.md and docs/project/phase0-backlog-validation.md. For the
checklist:
- Confirm KPIs/DoD are still correct; note gaps.
- List tickets (or TODO placeholders) covering tenant isolation, secrets,
  monitoring, and test automation.
- Call out dependencies/blockers and whether Raj/Mira need to co-own them.
- Provide next actions with owners + target dates.
Return the findings as a short report (Status, Gaps, Actions, Dependencies).
```

Log each simulated review in `docs/logs/project-worklog.md` (date + persona) so
future engineers know which assumptions were used.
