# Google Ads Scaffold Plan (v23)

This plan maps your new Google Ads reference payloads into the existing backend scaffold.

## 1) Reference ingestion and storage

- canonical raw input folder:
  - `backend/integrations/data/raw/google_ads/` (see `README.md` in that folder)
- `services/common/enums/errors/misc/resources` reference:
  - parser: `backend/integrations/google_ads/catalog.py`
  - command: `python3 manage.py import_google_ads_reference`
  - storage: `backend/integrations/data/google_ads_v23_reference.json`
- queryable resources + GAQL metadata overview:
  - parser: `backend/integrations/google_ads/query_reference.py`
  - command: `python3 manage.py import_google_ads_query_reference`
  - storage: `backend/integrations/data/google_ads_v23_query_reference.json`
- field-level segments/metrics metadata:
  - parser: `backend/integrations/google_ads/field_reference.py`
  - command: `python3 manage.py import_google_ads_fields_reference`
  - storage: `backend/integrations/data/google_ads_v23_fields_reference.json`

## 2) API scaffolding placement

- OAuth/setup/provision/sync/status/disconnect:
  - logic: `backend/integrations/google_ads_views.py`
  - request/response validation: `backend/integrations/google_ads_serializers.py`
  - routes: `backend/core/urls.py`
- reference summary endpoint:
  - route: `GET /api/integrations/google_ads/reference/summary/`
  - merges counts from all three reference stores.

## 3) Near-term wiring targets

- GAQL query builder hardening:
  - use `field_reference` filter/select/sort metadata to validate selectable fields before query execution.
  - enforce `selectable_with` compatibility checks for metric + segment combos.
- dashboard preset bundles:
  - map approved metric/segment sets to dashboard views in `gaql_templates.py` and capability bundles.
- sync orchestration:
  - add Google-specific scheduled sync task in `backend/integrations/tasks.py` (parity with Meta cadence rules).
  - publish sync-state snapshots for Google as done for Meta.

## 4) Contract and test coverage

- API contract surfaces:
  - update OpenAPI path assertions in `backend/tests/test_schema_regressions.py` for new routes.
- parser coverage:
  - `backend/tests/test_google_ads_catalog.py`
  - `backend/tests/test_google_ads_query_reference.py`
  - `backend/tests/test_google_ads_field_reference.py`
- endpoint coverage:
  - `backend/tests/test_google_ads_api.py`

## 5) Rollout sequence

1. Keep ingest commands as source of truth and import full raw docs payloads.
2. Lock approved segment/metric allowlists for first dashboard release.
3. Enable tenant-specific OAuth + provisioning in staging.
4. Verify status/sync endpoints and Airbyte connection lifecycle.
5. Expand metric/segment selection gradually by capability bundle.
