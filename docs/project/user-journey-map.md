# User Journey Map (v0.1)

Purpose: capture core workflows and expected system behavior.

## Journey 1 — Agency Admin Onboarding

1. Log in → choose tenant.
2. Add platform credentials (Meta/Google).
3. Confirm Airbyte syncs and data freshness.
4. View dashboards and export reports.

## Journey 2 — Analyst Daily Check

1. Open campaign dashboard.
2. Apply filters (date/channel/campaign).
3. Inspect KPI changes and trend.
4. Review map + table details.

## Journey 3 — Executive Summary

1. Open dashboard snapshot.
2. Review KPIs and pacing.
3. Export PDF or share link.

## Failure States

- Airbyte sync failed → show alert + runbook link.
- Snapshot stale → warning banner + retry action.
- No data → empty state + guidance.
