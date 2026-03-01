# Google Ads SDK Migration Runbook

Timezone baseline: `America/Jamaica`.

## Purpose

Operational runbook for Google Ads direct SDK ingestion with Airbyte fallback.

## Secret Rotation Procedure

1. Rotate OAuth client secret in Google Cloud Console.
2. Revoke existing refresh tokens issued with the previous client secret.
3. Generate fresh refresh tokens for each environment.
4. Update secret manager entries (dev/staging/prod) for:
   - `GOOGLE_ADS_CLIENT_ID`
   - `GOOGLE_ADS_CLIENT_SECRET`
   - `GOOGLE_ADS_DEVELOPER_TOKEN`
5. Restart backend/celery processes to load new secrets.
6. Confirm `/api/integrations/google_ads/status/` no longer reports credential reauth errors.

## SDK Parity Gate

SDK can become primary only when all criteria are true for each tenant:

1. 7 consecutive daily parity runs pass.
2. Spend delta <= 1.0%.
3. Clicks delta <= 2.0%.
4. Conversions delta <= 2.0%.
5. No critical SDK sync incidents during the same window.

## Auto-Rollback Triggers

Rollback to Airbyte is automatic when either condition is met:

1. 2 consecutive daily parity failures.
2. 3 consecutive hourly SDK sync failures.

When triggered, `GoogleAdsSyncState` flips to:

1. `effective_engine=airbyte`
2. `fallback_active=true`
3. `rollback_reason` populated

## Recovery Steps After Rollback

1. Inspect `GoogleAdsSyncState.last_sync_error` and latest `GoogleAdsParityRun.reasons`.
2. Fix root cause (auth, API quota, schema drift, or query incompatibility).
3. Run one manual SDK sync (`POST /api/integrations/google_ads/sync/`) in staging.
4. Run parity once and confirm pass.
5. Set desired engine back to `sdk` via provisioning flow.
6. Monitor for 24 hours before production re-enable.
