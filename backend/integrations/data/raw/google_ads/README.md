# Google Ads Raw Reference Inputs (v23)

Drop full Google Ads reference text exports here before running import commands.

## Expected files

- `services_common_resources_v23.txt`
  - Source content: services/common/enums/errors/misc/resources reference dump.
- `query_resources_v23.txt`
  - Source content: "List of all resources" + GAQL field attribute overview.
- `segments_metrics_fields_v23.txt`
  - Source content: `segments.*` and `metrics.*` field metadata dump.

## Import commands

```bash
cd backend
python3 manage.py import_google_ads_reference \
  --input integrations/data/raw/google_ads/services_common_resources_v23.txt \
  --api-version v23

python3 manage.py import_google_ads_query_reference \
  --input integrations/data/raw/google_ads/query_resources_v23.txt \
  --api-version v23

python3 manage.py import_google_ads_fields_reference \
  --input integrations/data/raw/google_ads/segments_metrics_fields_v23.txt \
  --api-version v23
```

## Normalized outputs

- `backend/integrations/data/google_ads_v23_reference.json`
- `backend/integrations/data/google_ads_v23_query_reference.json`
- `backend/integrations/data/google_ads_v23_fields_reference.json`
