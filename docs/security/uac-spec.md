# ADinsights User Access Control (UAC) & Privilege Model

**Version:** 1.3 (2025-01-05)

> This document captures the current and future-state access model for the ADinsights multi-tenant analytics platform. It supersedes earlier RBAC notes and should be used by product, engineering, security, and support when designing features, onboarding partners, or conducting audits.

## 1. Scope & Guardrails

- **Platform archetype:** three-layer SaaS hierarchy — Adtelligent (software management), Agency (white-label partner), and Client/Tenant (advertiser). 1:N relationships between layers; a user may hold roles across multiple tenants.
- **Isolation:** hard separation by `tenant_id`; workspace scoping inside tenants; cross-tenant access prohibited except platform break-glass with 2FA and justification.
- **Model:** RBAC foundation with ABAC constraints (tenant/workspace ownership, sensitivity tags, entitlement flags). Reference standards: NIST SP 800-162 (ABAC), NIST 800-53 AC-5/AC-6 (least privilege & separation of duties), NIST 800-63 (step-up authentication).
- **Secrets & exports:** connectors/token material always encrypted, never displayed raw. CSV exports disabled by default; approvals + watermarking required when enabled.
- **Entitlements:** feature toggles at Agency and Tenant level govern access to Board Packs, CSV exports, Portfolio Mode, etc. All changes audited.
- **SCIM/JML:** SCIM 2.0 inbound (RFC 7643/7644) for group-driven role binding; revocation SLA ≤72h with quarterly reviews.

## 2. Identity Object Model

| Layer | Entity | Description |
| ----- | ------ | ----------- |
| Software Management | **Agency** | Represents a partner agency granted delegated admin over managed tenants. Holds branding, entitlements, managed tenant list. |
| Software Management | **Adtelligent User** | Platform staff with portfolio responsibilities. Claims include `managed_agencies[]`, `managed_tenants[]`. |
| Agency | **Managed Tenant** | Client organisation created under an agency; inherits agency entitlements unless overridden. |
| Tenant | **Workspace** | Brand/region slice within a tenant. Workflows (dashboards, budgets, jobs) scoped here. |
| Identity | **User / Service Account** | Principal authenticated via SSO/JWT; session stores `current_tenant_id`, `recent_tenants`, `role_bindings[]`. |
| Resource | Dashboards, Reports, Budgets, Alerts, Pipelines, Connectors, API Keys, Board Packs, Audit Log, Billing, Comments. |
| Action verbs | `view`, `create`, `edit`, `publish`, `delete`, `export`, `propose`, `approve`, `execute`, `configure`, `share`, `comment`, `impersonate`. |

All API requests carry a tenant context header derived from `current_tenant_id`. Portfolio endpoints aggregate only over tenants listed in the caller’s bindings and deny drill-through to raw tables.

## 3. Role Catalog

### 3.1 Software Management (Adtelligent)

| Role | Summary |
| ---- | ------- |
| **Super Admin** | Full platform control (create/disable agencies & tenants, global policies, entitlements). Break-glass only with 2FA + justification. |
| **Admin (Portfolio Ops Lead)** | Assigned agencies/tenants. Manages users/roles, rotations (masked), approvals, job control, Board Pack scheduling. No access to other agencies. |
| **Support (Time-boxed)** | Consent-based impersonation (read-only unless escalated). Banners + watermark + audit trail. Auto-expires. |
| **White-label Configuration Admin** | Custom domain, branding, email templates. No data access. |
| **Entitlements Manager** | Adjusts feature toggles/plan tiers (CSV, Portfolio Mode, Board Pack). Changes audited. |

### 3.2 Agency (White-label Partner)

| Role | Summary |
| ---- | ------- |
| **Agency Owner** | Appoints Agency Admins; reviews entitlements; no raw data by default. |
| **Agency Admin (Delegated)** | Creates managed tenants, invites users, seeds workspaces, rotates connectors (masked), approves publish. Portfolio aggregate across managed tenants (PDF only). |
| **Agency Team Lead** | Day-to-day lead across assigned managed tenants/workspaces. Approves publish, co-approves budgets, runs jobs. |
| **Agency Senior Analyst** | NEW. Builds/edits dashboards across assigned tenants; proposes budget/pacing; workspace job control; PNG/PDF export (CSV via entitlement). Cannot publish. |
| **Agency Analyst (Jr)** | Drafts + annotations; PNG export only; no budgets/publish. |
| *(Optional)* Finance, Auditor, Data Engineer — scoped to billing, audit export, or ETL respectively. |

### 3.3 Client/Tenant

| Role | Summary |
| ---- | ------- |
| **Client Team Lead (Tenant Admin)** | Manages users, approvals, budgets, connectors, invoices, audit access. |
| **Client Senior Lead** | Creates/edits dashboards, runs workspace jobs, proposes budget/pacing. Requires TL approval to publish/budget. |
| **Client Junior** | Drafts/comments; PNG only; no publish budgets or connectors. |
| **Executive View** | Tenant-wide aggregate dashboards; PDF/PNG export only; masked identifiers; no jobs/budgets. |
| **Non-Executive View** | Workspace-scoped masked dashboards; comment + PNG; no budgets/connectors. |
| *(Optional)* Finance-only, Compliance/Auditor, Data Engineer. |

Role bindings follow `(user_id, role_id, tenant_id, workspace_id | null, agency_id | null)` composite keys; multiple rows allow cross-tenant service. IdP groups map to bindings via SCIM.

## 4. Permission Overview

| Capability | Super Admin | Adtelligent Admin | Agency Admin | Agency Sr Analyst | Client TL | Client Sr | Exec | Non-Exec |
|-----------|-------------|-------------------|--------------|-------------------|-----------|-----------|------|---------|
| Create tenant | ✅ | ⚠️ (assigned) | ✅ (managed only) | 🔒 | 🔒 | 🔒 | 🔒 | 🔒 |
| Tenant settings | ✅ | ⚠️ | ⚠️ (branding only) | 🔒 | ✅ | 🔒 | 🔒 | 🔒 |
| Workspace create/delete | ✅ | ✅ | ✅ (managed) | 🔒 | ✅ | 🔒 | 🔒 | 🔒 |
| Dashboard view | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (agg) | ✅ (masked) |
| Dashboard create/edit | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 🔒 | 🔒 |
| Publish dashboard/report | ✅ | ✅ | ⚠️ (agency TL) | 🔒 | ✅ | ⚠️ (needs TL) | 🔒 | 🔒 |
| Budgets & pacing edit | ✅ | ⚠️ (needs client TL) | ⚠️ (needs client TL) | ⚠️ (propose) | ✅ | ⚠️ (propose) | 🔒 | 🔒 |
| Connector rotation | ✅ | ✅ (masked) | ✅ (masked) | 🔒 | ✅ (masked) | 🔒 | 🔒 | 🔒 |
| Job run/pause | ✅ | ✅ | ✅ (managed) | ✅ (workspace) | ✅ | ✅ (workspace) | 🔒 | 🔒 |
| CSV export | ✅ | ⚠️ (entitled tenants) | ⚠️ (entitled tenants) | ⚠️ (agg only) | ⚠️ (policy) | ⚠️ (agg) | 🔒 | 🔒 |
| PNG/PDF export | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (PDF/PNG) | ✅ (PNG) |
| Portfolio dashboard | ✅ | ✅ (assigned) | ✅ (managed) | 🔒 | 🔒 | 🔒 | 🔒 | 🔒 |
| Billing & invoices | ✅ (platform + tenant) | 🔒 | 🔒 | 🔒 | ✅ (tenant) | 🔒 | 🔒 | 🔒 |
| Audit log export | ✅ | ✅ | ⚠️ (managed) | 🔒 | ✅ | ⚠️ (view only) | 🔒 | 🔒 |
| Impersonation | ✅ (break-glass) | ⚠️ (consent) | 🔒 | 🔒 | 🔒 | 🔒 | 🔒 | 🔒 |

Legend: ✅ allowed · ⚠️ requires approval/entitlement · 🔒 denied. High-risk actions (CSV enablement, secret rotation, destructive operations) demand step-up auth and justification; results recorded in audit log.

## 5. Workflow & Governance

1. **Draft → Review → Publish**: Jr/Sr roles create drafts → TL approval required to publish. Embargo windows can block publish; reasons logged.
2. **Budget & pacing**: Agency TL or Client Sr propose → Client TL approves. Dual control enforced in UI/API.
3. **Connector rotation**: TL initiates; token masked; rotation event audited.
4. **Board Packs**: Scheduled PDFs for Exec roles. SLA: monthly (M+3), quarterly (Q+5). Content approved by Client TL.
5. **Portfolio mode**: Aggregated KPIs across assigned tenants; PDF only; no drill-through.
6. **CSV enablement**: Feature toggle + step-up + justification; auto-expiry optional.
7. **Impersonation**: Consent + banner + watermark; time-boxed; audit entry captures actor, reason, duration.

## 6. Data & Privacy Controls

- Tenant/workspace filters enforced at query layer (`ScopeFilterBackend`) and down to dbt models/warehouse RLS. Column-level masking for PII (exposed to TL roles only).
- Executive/Non-Executive roles see aggregated, masked data only; exports limited to watermarked PDF/PNG. Prohibit raw IDs in board materials.
- Watermark all images/PDF exports with tenant, timestamp, requesting user.
- Maintain export registry: who, what, where, why.

## 7. Audit & Telemetry Requirements

- Authentication events: login, 2FA, token issuance/revocation.
- User lifecycle: invite, role changes, SCIM updates, disable, idp group change.
- Resource lifecycle: create/edit/publish/delete across dashboards, workspaces, tenants.
- Approvals: publish, budget/pacing, CSV enablement, blackout overrides.
- Secrets: rotation, failure, scope changes.
- Exports & board packs: generation, distribution, recipients.
- Impersonation: actor, approved by, start/end times, actions performed.
- Job runs: trigger, result, cost impact.

Audit logs must be tenant-aware, immutable for ≥12 months, and exportable for compliance attestation.

## 8. JWT / Session Claims (example)

```json
{
  "sub": "user_123",
  "tenants": ["tenant_alpha", "tenant_beta"],
  "current_tenant_id": "tenant_alpha",
  "managed_agencies": ["agency_west"],
  "role_bindings": [
    {"tenant": "tenant_alpha", "agency": "agency_west", "role": "agency_team_lead", "workspaces": ["ws_a", "ws_b"]},
    {"tenant": "tenant_beta", "agency": "agency_west", "role": "agency_senior_analyst", "workspaces": ["ws_c"]}
  ],
  "entitlements": {"portfolio_mode": true, "csv_export": "aggregated_only", "board_pack": true}
}
```

API middleware ensures `current_tenant_id` matches an allowed binding. Portfolio endpoints aggregate only tenants present in the bindings; other tenants trigger 403.

## 9. Board Pack Specification (Exec PDF)

- **Audience:** Exec View users (C-suite, board). Distribution = PDF + key PNGs only; watermarked; optional email schedule.
- **Cadence & SLA:** Monthly (M+3 business days) and quarterly (Q+5). Data freshness ≤24h (network) & ≤6h (warehouse).
- **Layout:** header (brand, period, freshness, owner), KPI tiles (Spend, Revenue, ROAS, CPA/CAC, CTR, CVR, Reach), variance vs plan & prior period (with RAG thresholds configurable per tenant), trend sparklines, anomalies/risks, top drivers (wins/watch-outs), next actions, footnote (sources/caveats).
- **Policy:** Aggregated data only; <800 words; no raw tables/PII. TL approval before delivery.
- **Watermark:** tenant, timestamp, version hash, requesting user.

## 10. Rollout Checklist (summary)

1. **Phase 0 – Foundations**: schema updates for role bindings, entitlements, agency table; SCIM group mapping; permission middleware scaffolding.
2. **Phase 1 – Agency Delegated Admin**: CRUD for agencies, managed tenants, branding; tenant switcher UI; portfolio dashboards (aggregate only); audit plumbing.
3. **Phase 2 – Client Controls**: approvals engine, budget workflows, Board Pack generation, exec/non-exec restrictions, blackout windows.
4. **Phase 3 – Security Hardening**: step-up auth, export watermarking, impersonation flow, audit exports, JML automation.
5. **Phase 4 – Compliance & UX polish**: policy diff UI, “why denied” trace, access review workflows, persona-driven UX tours, documentation updates.

Detailed rollout steps are maintained in `docs/project/workplan.md`.

## 11. References

1. NIST SP 800-162 — Guide to Attribute Based Access Control (ABAC) (2014).
2. NIST SP 800-53 Rev.5 — Security and Privacy Controls (AC-5, AC-6).
3. NIST SP 800-63B — Digital Identity Guidelines (authentication assurance).
4. RFC 7643/7644 — SCIM 2.0 (System for Cross-domain Identity Management).
5. Delegated admin patterns (Microsoft GDAP, Google Workspace delegated admin) — white-label & bounded admin.
6. SaaS tenant isolation patterns; feature flag & entitlement service best practices.
7. Viewer download restrictions for BI/analytics tools (PNG/PDF-only exec views).

---

For questions or change proposals, start a doc PR and tag @security, @product, and @platform. Significant modifications require security review and an access model regression plan.

