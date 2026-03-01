# ADinsights Persona Report Templates

All default reports must include these sections in order:

1. `Status`
2. `Gaps`
3. `Actions`
4. `Dependencies`
5. `Escalations`

## Template A: Phase 0 Backlog Simulation

Use this for workstream readiness checks and backlog gap reviews.

```markdown
## Status

- Workstream:
- Persona:
- Overall readiness:

## Gaps

- KPI or DoD mismatch:
- Missing test coverage:
- Missing observability or runbook updates:
- Contract or dependency ambiguity:

## Actions

1. [Owner] [Action] - ETA [date]
2. [Owner] [Action] - ETA [date]
3. [Owner] [Action] - ETA [date]

## Dependencies

- Upstream dependency:
- Downstream dependency:
- Blocking external action (if any):

## Escalations

- Raj required? [Yes/No] Reason:
- Mira required? [Yes/No] Reason:
- Additional stream owner consults:
```

## Template B: Implementation Planning Review

Use this for owner-style planning before coding.

```markdown
## Status

- Requested change:
- Routed persona:
- Scope folder(s):

## Gaps

- Missing technical context:
- Missing acceptance criteria:
- Testing gaps:
- Docs/runbook update gaps:

## Actions

1. Define implementation sequence by folder and dependency.
2. Define exact test commands and pass criteria.
3. Define docs/runbook updates and ownership.

## Dependencies

- Required upstream task(s):
- Contract assumptions:
- Rollout/coordination notes:

## Escalations

- Raj trigger check:
- Mira trigger check:
- Any unresolved ownership conflicts:
```

## Template C: Cross-Stream Escalation Brief

Use this when the request spans top-level folders or implies architecture refactor.

```markdown
## Status

- Trigger condition:
- Affected folders:
- Affected personas/owners:

## Gaps

- Integration risks:
- Contract drift risks:
- Test matrix coverage risks:

## Actions

1. Assign Raj as cross-stream integrator.
2. Assign Mira for architecture/refactor review.
3. Split implementation into stream-safe milestones.

## Dependencies

- Sequence constraints:
- Required reviewer checkpoints:
- External prerequisites:

## Escalations

- Raj: [Required]
- Mira: [Required/Conditional]
- Stream owner approvals:
```
