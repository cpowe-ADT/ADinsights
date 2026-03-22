# PostgreSQL Grants & Row-Level Security (RLS)

This document describes the required PostgreSQL permissions and configuration to support the ADinsights multi-tenant isolation model.

## RLS Overview

ADinsights uses PostgreSQL Row-Level Security (RLS) to ensure that a tenant can only access its own data, even if a software bug or query mistake omits a `WHERE tenant_id = ...` clause.

The isolation is enforced by checking a session variable `app.tenant_id` against the `tenant_id` column in each scoped table.

## Required Grants

The PostgreSQL database user used by the Django application (e.g., `adinsights_app`) requires the following permissions:

### 1. DDL Permissions (Migrations & Setup)

During initial setup and migrations, the user (or a separate migration user) must be able to:
- Create tables, indexes, and constraints.
- Enable RLS on tables: `ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;`
- Create and drop policies: `CREATE POLICY ... ON <table_name> ...;`

### 2. DML Permissions (Runtime)

The application user requires standard DML on all tenant-aware tables:
- `SELECT`, `INSERT`, `UPDATE`, `DELETE` on all tables in the `public` schema.
- `USAGE` on all sequences.

### 3. Session Configuration

The application user must be able to set the `app.tenant_id` configuration parameter:
- `SET app.tenant_id = '...';`
- `RESET app.tenant_id;`

In PostgreSQL, any user can set a custom configuration parameter (like `app.tenant_id`) unless it is a reserved system parameter. No special `GRANT` is required for `SET`.

## RLS Policy Definition

The `enable_rls` management command ensures that the following policy is present on all tenant-scoped tables:

```sql
ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON <table_name>
USING (tenant_id = current_setting('app.tenant_id')::uuid);
```

### Security Considerations

- **Bypass RLS:** Database superusers and the table owner bypass RLS by default. Ensure the application user is NOT the table owner or a superuser in production.
- **Leaked Context:** The `TenantMiddleware` ensures that `app.tenant_id` is reset at the end of every request to prevent context leaking between requests in a connection pool.
- **Unauthenticated Requests:** For unauthenticated requests (e.g., login), `app.tenant_id` is set to `DEFAULT` or `NULL`. RLS will block all access to tenant-scoped tables in this state unless the table has a specific policy for public access (none do).

## Troubleshooting

If you see errors like `permission denied for table ...`, verify that the application user has the correct `GRANT`s.

If a query returns 0 rows when you expect data, verify that `app.tenant_id` is correctly set for the session:
```sql
SHOW app.tenant_id;
```
If it is empty or set to a different tenant ID, RLS is doing its job.
