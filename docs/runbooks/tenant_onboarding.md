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
  backend sends an email via SES (when `EMAIL_PROVIDER=ses`) containing a link to
  `FRONTEND_BASE_URL/invite?token=...`.

## 3. Accept an Invitation

- **Endpoint**: `POST /api/users/accept-invite/`
- **Body**: `{"token": "<invite token>", "password": "...", "first_name": "Analyst"}`.
- **Result**: Creates the user within the issuing tenant, sets the password, marks the invitation as
  accepted, and assigns the requested role.
- **Guards**: The API rejects expired or previously accepted tokens and prevents duplicate emails
  within the tenant.
- **UI Path**: The frontend accepts invite tokens at `GET /invite?token=...` and POSTs the same
  payload to the endpoint above.

## 4. Password Resets

- **Request**: `POST /api/auth/password-reset/` with `{"email": "user@acme.com"}`. Returns `202`.
- **Confirm**: `POST /api/auth/password-reset/confirm/` with `{"token": "<reset token>", "password": "..."}`.
- **Email**: The reset email is delivered via SES (when `EMAIL_PROVIDER=ses`) and links to
  `FRONTEND_BASE_URL/password-reset?token=...`.
- **UI Path**: `GET /password-reset` (request form) and `GET /password-reset?token=...` (confirm).

## 5. Manage RBAC Assignments

- **List**: `GET /api/user-roles/` (any authenticated tenant member; scoped to their tenant).
- **Grant**: `POST /api/roles/assign/` with `{ "user": "<uuid>", "role": "VIEWER" }` (admin-only).
- **Revoke**: `DELETE /api/user-roles/{id}/` (admin-only).

## 6. Troubleshooting Tips

- Verify that the caller holds the `ADMIN` role when receiving `403` responses on invite or role
  mutation endpoints.
- Invitation tokens default to a seven-day expiry (`accounts.models.default_invitation_expiry`). Ops
  teams can purge or extend invites via the Django admin if necessary.
- SES email delivery requires `EMAIL_PROVIDER=ses`, `EMAIL_FROM_ADDRESS` (use the `adtelligent.net`
  domain), `FRONTEND_BASE_URL`, and valid AWS credentials (`AWS_REGION`, `AWS_ACCESS_KEY_ID`,
  `AWS_SECRET_ACCESS_KEY`).
- For production SES readiness, complete this checklist before onboarding external tenants:
  1. Domain identity for `adtelligent.net` is verified in SES.
  2. Easy DKIM is enabled and all SES DKIM records are verified.
  3. SPF and DMARC records are published and aligned with SES sending.
  4. SES account is approved for production sending (not sandbox-only).
  5. `EMAIL_FROM_ADDRESS` is confirmed with stakeholders and matches `SES_EXPECTED_FROM_DOMAIN`.
  6. Invite and password-reset smoke tests confirm successful delivery to approved mailboxes.
- For local development, set `EMAIL_PROVIDER=log` to suppress email sending while still exercising
  the invite/reset flows.
