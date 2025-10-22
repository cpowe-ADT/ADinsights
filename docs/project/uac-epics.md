# UAC Rollout — Linear/Jira Epic Stubs

> Use these descriptions when creating work items in Linear or Jira. Each epic maps to the rollout phases in `docs/task_breakdown.md` §7 and the security baseline defined in `docs/security/uac-spec.md`.

## Epic U0 — Identity & Context Plumbing

- **Summary:** Introduce agency/tenant role bindings, entitlements, and tenant context enforcement across API + frontend.
- **Key Deliverables:**
  - Agency + entitlement schemas, migrations, seeds.
  - JWT/session claim updates, scope-aware DRF permissions.
  - Frontend tenant context store prototype.
- **Definition of Done:** SCIM group sync works in sandbox; every protected API requires `current_tenant_id`; regression tests for legacy roles green.

## Epic U1 — Agency Delegated Admin & Portfolio Mode

- **Summary:** Enable white-label agencies to create/manage client tenants and view aggregate KPIs across assigned portfolios.
- **Key Deliverables:**
  - Agency admin CRUD endpoints + UI forms.
  - Tenant/agency switcher (search + keyboard shortcuts).
  - Portfolio dashboard (aggregate only, PDF export stub).
- **Definition of Done:** Agency admin can spin up a managed tenant end-to-end in staging; portfolio PDF watermarked; audit entries emitted for all admin actions.

## Epic U2 — Client Approvals, Board Packs, Blackout Windows

- **Summary:** Ship dual-control workflows (draft→publish, budget proposals), monthly Board Pack PDFs for Execs, and embargo controls.
- **Key Deliverables:**
  - Approval engine with status transitions, comments, notifications.
  - Board Pack generator + scheduling UI, KPI marts in dbt.
  - Blackout window configuration + enforcement.
- **Definition of Done:** Exec can receive a watermarked PDF after TL approval; embargo prevents publish during blocked windows; audit trails complete.

## Epic U3 — Security Hardening & Step-up Workflows

- **Summary:** Introduce step-up MFA, impersonation with consent, export watermarking, and comprehensive audit retention.
- **Key Deliverables:**
  - Middleware/decorators enforcing 2FA for high-risk actions.
  - Impersonation API + UI banners; auto-expiry logic.
  - Export watermarking service, download registry, SIEM feed.
- **Definition of Done:** Pen-test validates tenant isolation + export controls; support impersonation logs contain actor, approver, duration; SIEM integration live.

## Epic U4 — Compliance Reviews & UX Polishing

- **Summary:** Finalise “why denied” diagnostics, quarterly access review exports, persona onboarding, and documentation polish.
- **Key Deliverables:**
  - Privilege decision trace API + UI messaging.
  - Access attestation exports, reviewer workflow.
  - Persona tours, role badges, updated onboarding guides.
- **Definition of Done:** Security/product sign off; customer success uses tours during onboarding; compliance team executes quarterly review using exported evidence.

## Cross-cutting Tasks

- Update runbooks, SOC/ISO evidence folders, and customer-facing docs each epic.
- Track entitlements feature flags per tenant/agency; include QA checklist for enabling CSV/Board Pack features.
- Maintain rollback plan: ensure progress can be feature-flagged off without losing data integrity.

When creating epics:

- Prefix with `UAC` (e.g., `UAC-U1 Delegated Admin & Portfolio Mode`).
- Attach relevant specs (`uac-spec.md`, `task_breakdown.md`).
- Link dependent backend/frontend/dbt tasks underneath; keep PRs scoped per top-level folder.
- Mark security review & ops runbook updates as explicit subtasks.
