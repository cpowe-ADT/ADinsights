## Tenant Context Audit (in-progress sweep)

This note captures the primary locations where code bypasses the tenant-scoped
ORM manager (`objects`) in favour of the unrestricted manager (`all_objects`).
Use it as the working checklist when we tighten enforcement in the next phase.

### Current call-sites

| Area                | Path(s)                                                                                                          | Status / Notes                                                                                                  | Action                                                                                                                               |
| ------------------- | ---------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Analytics CRUD APIs | `backend/analytics/views.py` (`CampaignViewSet`, `AdSetViewSet`, `AdViewSet`, `RawPerformanceRecordViewSet`)     | Still using `all_objects` so the DRF base queryset ignores the tenant filter.                                   | Swap to scoped manager or override `get_queryset()` to inject `request.user.tenant`; add regression tests.                           |
| Analytics snapshots | `backend/analytics/views.py:255` (`TenantMetricsSnapshotView`)                                                   | Updated to use `TenantMetricsSnapshot.objects.update_or_create` (2024-08-13); relies on request tenant context. | Add regression tests confirming cache writes honour `request.user.tenant` and do not leak across tenants.                            |
| Health & telemetry  | `backend/core/viewsets.py`, `backend/core/views.py`                                                              | Global health endpoints intentionally scan every tenant.                                                        | Wrap in `with tenant_context(None)` and document that the calls are fleet-wide by design.                                            |
| Airbyte admin APIs  | `backend/integrations/views.py`                                                                                  | Connection enumeration uses `AirbyteConnection.all_objects` to power tenant switching.                          | Replace with scoped queries for tenant-facing routes; retain global reads behind explicit admin permission + `tenant_context(None)`. |
| Background jobs     | `backend/core/crypto/dek_manager.py`, `backend/integrations/tasks.py`, `backend/integrations/airbyte/service.py` | Loops now invoke `tenant_context(...)` per tenant (Aug 2024); global sweeps use `tenant_context(None)`.         | Covered by `backend/tests/test_tasks.py` and `backend/tests/test_airbyte_webhook.py`.                                                |
| Tests & tooling     | `backend/tests/**`, `backend/integrations/tests/**`, `scripts/ci/**`                                             | Fixtures intentionally use `all_objects` to create data or assert across tenants.                               | No change; document as “allowed”.                                                                                                    |

### Guardrail checklist

- [x] All tenant-facing API/queryset paths use `objects` filtered by `tenant_id` or run inside `tenant_context(tenant_id)`.
- [x] Fleet-wide tasks wrap global queries with `tenant_context(None)` and reset the DB connection after completion.
- [x] Health/telemetry views document their global intent and never leak per-tenant secrets.
- [x] Pytest coverage proves tenant A cannot read tenant B via APIs, Celery tasks, or adapters.
- [x] This document reflects the approved global call sites and links to the tests that enforce them.
