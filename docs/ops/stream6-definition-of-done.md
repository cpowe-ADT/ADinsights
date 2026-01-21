# Stream 6 Definition of Done (Observability & Alerts)

Owner: Omar (primary), Hannah (backup). This checklist defines when Stream 6 work is considered complete. Use it for sprint closeout and release readiness.

## Scope boundaries

- Only observability/alerting code and docs are in scope.
- If changes touch more than one top-level folder, coordinate with Raj (integration) and Mira (architecture).

## Required outcomes

### 1) Alert thresholds & escalation runbook (Week 1)

- Default thresholds documented and reviewed by stream owner.
- Escalation paths reference `docs/ops/escalation-matrix.md`.
- Alert runbooks link to relevant dashboards and health endpoints.

### 2) Prometheus scrape validation + `/metrics/app/` smoke docs (Week 2)

- `/metrics/app/` smoke checklist exists and is validated in at least one environment.
- Prometheus target validation steps documented.
- Known scrape failure modes and fixes documented.

### 3) Log schema doc + cardinality review (Week 3)

- Log schema reference includes required fields and common optional fields.
- Cardinality review checklist included.
- Logging standards updated without introducing PII exposure risk.

### 4) Stability tests + runbook QA (Week 4)

- Observability stability tests documented and run at least once per release cycle.
- Runbook QA checklist includes thresholds, commands, and owner checks.
- Evidence captured (logs, screenshots, or links) and stored in the incident or release notes.

## Verification evidence

- Links or screenshots for Prometheus target `UP` and `/metrics/app/` payload checks.
- Sample structured logs showing `tenant_id`, `task_id`, and `correlation_id`.
- Confirmation that alert thresholds were reviewed by Omar/Hannah.

## Sign-off checklist

- [ ] Stream owner review complete.
- [ ] Docs updated and cross-linked in `docs/ops/doc-index.md`.
- [ ] Agent activity log updated with the change summary.
- [ ] Release checklist notified if alert thresholds changed.

## See also

- `docs/ops/alert-thresholds-escalation.md`
- `docs/ops/metrics-scrape-validation.md`
- `docs/ops/observability-stability-tests.md`
- `docs/ops/logging-standards.md`
- `docs/runbooks/alerting.md`
