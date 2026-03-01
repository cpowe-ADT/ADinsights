# Google Ads Integration Scaffold

This module is the backend structure for the Google Ads API build-out.

## Why this exists

- Keep Google Ads onboarding/reporting logic isolated from existing Meta-first integration code.
- Persist a normalized Google Ads v23 reference catalog for service/resource discovery.
- Provide capability bundles and GAQL starter templates for dashboard ingestion.

## Files

- `catalog.py`
  - Parses raw Google Ads API reference text into a normalized JSON catalog.
  - Loads/saves `backend/integrations/data/google_ads_v23_reference.json`.
- `capabilities.py`
  - Defines phased service bundles for OAuth/account discovery, reporting, conversion, and optimization.
- `gaql_templates.py`
  - Stores reusable GAQL templates for campaign, creative, and geographic daily metrics.
- `query_reference.py`
  - Parses/stores GAQL queryable-resource reference content (overview + resource types + field attribute semantics).
- `field_reference.py`
  - Parses/stores field-level Google Ads metadata for `segments.*` and `metrics.*` (description, type, filter/select/sort/repeated, selectable-with).

## Importing a full v23 reference dump

1. Save raw reference text to a file, for example:
   - `backend/integrations/data/raw/google_ads/services_common_resources_v23.txt`
2. Run:

```bash
cd backend
python3 manage.py import_google_ads_reference \
  --input integrations/data/raw/google_ads/services_common_resources_v23.txt \
  --api-version v23
```

This command writes normalized output to:

- `backend/integrations/data/google_ads_v23_reference.json`

## Importing GAQL queryable-resource reference text

```bash
cd backend
python3 manage.py import_google_ads_query_reference \
  --input integrations/data/raw/google_ads/query_resources_v23.txt \
  --api-version v23
```

This command writes normalized output to:

- `backend/integrations/data/google_ads_v23_query_reference.json`

## Importing segments/metrics field reference text

```bash
cd backend
python3 manage.py import_google_ads_fields_reference \
  --input integrations/data/raw/google_ads/segments_metrics_fields_v23.txt \
  --api-version v23
```

This command writes normalized output to:

- `backend/integrations/data/google_ads_v23_fields_reference.json`
- Raw input storage contract:
  - `backend/integrations/data/raw/google_ads/README.md`

## Scaffolded backend endpoints

- `GET /api/integrations/google_ads/setup/`
- `POST /api/integrations/google_ads/oauth/start/`
- `POST /api/integrations/google_ads/oauth/exchange/`
- `GET /api/integrations/google_ads/status/`
- `GET /api/integrations/google_ads/reference/summary/`
- `POST /api/integrations/google_ads/provision/`
- `POST /api/integrations/google_ads/sync/`
- `POST /api/integrations/google_ads/disconnect/`

## Suggested next implementation steps

1. Add Google OAuth start/callback endpoints using existing `PlatformCredential` + tenant guards.
2. Add provider-specific status/provision/sync endpoints parallel to Meta flow.
3. Wire GAQL templates to an ingestion job that upserts into raw tables.
4. Map staged Google Ads marts into `/api/metrics/combined/` dashboard sections.
