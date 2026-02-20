# Escalation Matrix (v0.1)

Purpose: define who to notify and when during incidents.

## Severity Levels

- **SEV-1**: platform down, data exposure risk, security event.
- **SEV-2**: major workflow broken, no data for multiple tenants.
- **SEV-3**: partial outage, delayed syncs, degraded dashboards.

## Routing

| Severity | First Responders              | Escalate To                             | Timeframe         |
| -------- | ----------------------------- | --------------------------------------- | ----------------- |
| SEV-1    | On-call engineer + Omar (SRE) | Raj (Integration) + Mira (Architecture) | Immediate         |
| SEV-2    | Stream owner + Omar (SRE)     | Raj (Integration)                       | 30 minutes        |
| SEV-3    | Stream owner                  | Team lead                               | Same business day |

## Notes

- Log all incidents in the ops channel and link to `docs/ops/risk-register.md`.
- Update runbooks after resolution.
