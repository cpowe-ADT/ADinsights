# Meta Authenticated Validation Required (External)

Date: 2026-02-06 (America/Jamaica)

## Why this exists

Meta developer documentation pages required for deep field/scope verification are not accessible to
anonymous crawler tooling in this environment (HTTP 429 / auth-gated responses). Final validation must
be completed by an authenticated operator in the Meta developer portal and Ads Manager context.

## Required operator evidence

1. Screenshot/export showing approved app permissions for Marketing API access (`ads_read` and any
   additional required scopes).
2. Screenshot/export showing account access for target ad account IDs.
3. Confirmation of insights reporting field availability used by ADinsights:
   - `date_start`, `account_id`, `campaign_id`, `adset_id`, `ad_id`, `region`,
     `spend`, `impressions`, `clicks`, `actions` / `action_values`.
4. Confirmation of lookback/attribution constraints used in operations runbooks.

## Sign-off

- Integrations owner (Maya): Pending
- Celery owner (Leo): Pending
- Cross-stream reviewer (Raj): Pending
