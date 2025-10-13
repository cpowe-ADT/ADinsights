# Tenant Onboarding & RBAC Runbook

The Django backend now exposes a collection of endpoints that orchestrate tenant creation, user
invitations, and role assignments. This runbook captures the happy-path sequence along with guardrails
for support engineers.

## 1. Create a Tenant
- **Endpoint**: `POST /api/tenants/`
- **Body**: `{"name": "Acme", "admin_email": "owner@acme.com", "admin_password": "..."}` (first and
  last names are optional).
- **Result**: Returns the tenant payload plus `admin_user_id`. The admin user is automatically granted
the `ADMIN` role.
- **Notes**: Endpoint is open to unauthenticated callers for self-service sign-ups. Provisioners should
immediately store generated secrets (e.g., credentials vault entries) against `admin_user_id`.

## 2. Invite Additional Users
- **Endpoint**: `POST /api/users/invite/`
- **Authentication**: Tenant admin or superuser.
- **Body**: `{"email": "analyst@acme.com", "role": "ANALYST"}` (role optional, defaults to no RBAC).
- **Result**: Returns an invitation record with a generated `token` and expiration timestamp. The
`accounts.hooks.send_invitation_email` hook is called so deployments can plug in real email delivery.

## 3. Accept an Invitation
- **Endpoint**: `POST /api/users/accept-invite/`
- **Body**: `{"token": "<invite token>", "password": "...", "first_name": "Analyst"}`.
- **Result**: Creates the user within the issuing tenant, sets the password, marks the invitation as
accepted, and assigns the requested role.
- **Guards**: The API rejects expired or previously accepted tokens and prevents duplicate emails
within the tenant.

## 4. Manage RBAC Assignments
- **List**: `GET /api/user-roles/` (any authenticated tenant member; scoped to their tenant).
- **Grant**: `POST /api/user-roles/` with `{ "user": "<uuid>", "role": "VIEWER" }` (admin-only).
- **Revoke**: `DELETE /api/user-roles/{id}/` (admin-only).

## 5. Troubleshooting Tips
- Verify that the caller holds the `ADMIN` role when receiving `403` responses on invite or role
  mutation endpoints.
- Invitation tokens default to a seven-day expiry (`accounts.models.default_invitation_expiry`). Ops
  teams can purge or extend invites via the Django admin if necessary.
- The placeholder email hook logs to application logs; integrate SES, SendGrid, or another provider by
  overriding `accounts.hooks.send_invitation_email` during deployment.
