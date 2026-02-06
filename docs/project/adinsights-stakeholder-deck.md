# ADinsights Stakeholder Deck

## Slide 1: Title
**ADinsights: Trusted Paid Media Intelligence for Agency and Client Stakeholders**

- Multi-tenant analytics platform for agencies managing Meta and Google Ads.
- Built for fast decisions with tenant-safe, aggregated metrics.
- Focus region: Jamaica (timezone + parish-level reporting support).

---

## Slide 2: Executive Summary
**What ADinsights delivers**

- One view of campaign performance across ad platforms.
- Faster reporting through automated ingestion, modeling, and dashboard refresh.
- Better stakeholder alignment with shared KPIs, drill-downs, and freshness indicators.
- Lower operational risk through observability, runbooks, and tenant isolation guardrails.

---

## Slide 3: The Stakeholder Problem We Are Solving
**Today's pain points**

- Performance data lives in separate platform UIs and exports.
- Teams spend time reconciling definitions instead of acting on performance.
- Leadership gets delayed or inconsistent snapshots.
- Operations teams react late when syncs fail or data is stale.
- Compliance/security concerns slow onboarding of new data sources.

---

## Slide 4: What ADinsights Is
**Product overview**

- Ingestion: Airbyte syncs platform data.
- Modeling: dbt standardizes metrics and dimensions.
- API layer: Django + DRF serves tenant-scoped aggregated insights.
- Experience: React dashboards with KPI cards, trends, tables, and parish choropleth maps.
- Ops layer: Celery scheduling, health checks, telemetry, and alerting runbooks.

---

## Slide 5: Why It Matters to the Business
**Business outcomes**

- Shorter reporting cycle from data arrival to stakeholder-ready insight.
- More confident budget and pacing decisions with a shared metrics layer.
- Reduced risk of decision-making on stale or partial data.
- Better client trust from consistent reporting outputs.
- Operational resilience with explicit reliability targets and incident workflows.

---

## Slide 6: Who Needs to See This Deck
**Primary audience map**

- Agency leadership (CEO/COO/Heads of Client Services).
- Account directors and client success leads.
- Performance marketing managers and analysts.
- Finance and revenue operations.
- Platform operations, support, and SRE.
- Security/compliance stakeholders.
- Product, data, and engineering leads.
- Client-side marketing stakeholders (brand manager/marketing lead).

---

## Slide 7: Stakeholder Value by Role
| Stakeholder | Core question | ADinsights value |
| --- | --- | --- |
| Agency leadership | Are we growing accounts profitably? | Consolidated KPI and pacing visibility across tenants and channels. |
| Account/Client Success | What do I show clients each week? | Fresh snapshot-backed dashboard views and shareable reporting workflows. |
| Analysts/Media Buyers | Where should I optimize next? | Drill-downs by campaign/creative/geo with normalized metrics. |
| Finance/RevOps | Are spend and outcomes reconciled? | Standardized spend/conversion views for planning and forecasting. |
| Ops/Support | Is data healthy and current? | Health endpoints, telemetry, alerts, and runbook-guided triage. |
| Security/Compliance | Is sensitive data protected? | Tenant isolation, encrypted credentials, and aggregated-only metric exposure. |
| Product/Engineering | Can we ship safely and scale? | Defined ownership map, test matrix, and clear API/data contracts. |

---

## Slide 8: End-to-End Data Flow (Trust Chain)
**How insight gets produced**

1. Airbyte ingests raw ad-platform data.
2. dbt builds staging/marts with SCD2 support for changing dimensions.
3. Backend serves `/api/metrics/combined/` snapshots for dashboards.
4. Frontend renders decision-ready visuals with freshness indicators.

**Design guardrails**
- Tenant isolation enforced across layers.
- Aggregated metrics only (no user-level PII).

---

## Slide 9: Current Product Status
**Built now**

- Multi-tenant auth + tenant switching + role flows.
- KPI dashboards (campaigns, creatives, budget pacing), table + map views.
- Airbyte connection lifecycle APIs + telemetry endpoints.
- dbt staging/marts and snapshot persistence.
- Core observability and deployment/release runbooks.

**In progress / next**
- Dashboard library live API integration.
- Sync health and health-checks overview UI.
- Connector expansion and admin/reporting enhancements.

---

## Slide 10: Reliability and Operating Commitments
**Operational KPI targets**

- Nightly sync success before 06:00 America/Jamaica: `>=99%`.
- dbt staging freshness at 06:30: `>=98%` within 90 minutes.
- Dashboard freshness during business hours: `>=99%` under 6 hours old.
- Median alert closure latency: `<=45 minutes`.

**What this means for stakeholders**
- More predictable morning reporting and fewer surprise escalations.

---

## Slide 11: Security, Privacy, and Governance
**Controls built into the platform**

- AES-GCM encryption for stored platform credentials with per-tenant DEKs.
- KMS-backed key management and scheduled DEK rewrap process.
- Structured observability logs with tenant/task/correlation context.
- PII policy: aggregated advertising metrics only.

**Stakeholder impact**
- Security and compliance stakeholders can approve rollout with clear controls.

---

## Slide 12: Stakeholder-Specific Demo Walkthrough
**Suggested flow in a review meeting**

1. Agency leader view: top KPI and pacing summary.
2. Account lead view: tenant switch + shared weekly reporting perspective.
3. Analyst view: filter, trend, campaign/creative deep dive, parish map signal.
4. Ops view: freshness banner + telemetry/health posture.
5. Security view: tenant and encryption guardrails.

---

## Slide 13: Value Realization Framework
**Track these outcomes post-launch**

- Reporting cycle time (data arrival to client-ready summary).
- Hours spent on manual data reconciliation.
- Number of stale-data incidents reaching client-facing teams.
- Dashboard adoption by role (leadership, account, analyst).
- Trend in support tickets tied to missing/stale metrics.

---

## Slide 14: Adoption and Rollout Plan
**90-day adoption structure**

- Days 0-30: onboard priority tenants, baseline current reporting effort.
- Days 31-60: run weekly stakeholder review cadence from ADinsights dashboards.
- Days 61-90: expand to full account portfolio and lock in operating rhythm.

**Enablement needs**
- Role-based training for account leads, analysts, and ops responders.
- Clear escalation path using support playbook + runbooks.

---

## Slide 15: Risks and Mitigations
| Risk | Mitigation |
| --- | --- |
| Data quality regressions | dbt tests + data quality checklist. |
| Snapshot staleness | Freshness alerting + runbook response. |
| Connector coverage gaps | Prioritized connector roadmap and phased rollout. |
| Secrets leakage | KMS-backed encryption + log scrubbing controls. |

---

## Slide 16: Decision and Next-Step Asks
**Asks from stakeholders in this meeting**

- Confirm the initial pilot tenant set and success metrics baseline.
- Approve role-based operating cadence (leadership, account, analyst, ops).
- Confirm ownership for reliability escalation and client communications.
- Prioritize next-scope items (connector expansion, admin/reporting workflows).

**Immediate next step**
- Run a 45-minute cross-functional demo using the Slide 12 walkthrough and finalize pilot go-live criteria.
