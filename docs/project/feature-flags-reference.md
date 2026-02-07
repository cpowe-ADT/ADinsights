# Feature Flags & Entitlements Reference (v0.1)

Purpose: summarize feature flags/entitlements for AI and humans.

## Source of truth
- `docs/security/uac-spec.md`

## Core concepts
- **Entitlements**: per-agency/tenant toggles for premium features.
- **Feature flags**: temporary gates for staged rollouts.

## Examples (planned)
- CSV exports
- Portfolio mode
- Board packs
- Approval workflows

## Operational runtime controls (not entitlement flags)
- `CORS_ALLOWED_ORIGINS`, `CORS_ALLOW_ALL_ORIGINS`, `CORS_ALLOW_CREDENTIALS`
- `DRF_THROTTLE_AUTH_BURST`, `DRF_THROTTLE_AUTH_SUSTAINED`, `DRF_THROTTLE_PUBLIC`
- `SES_EXPECTED_FROM_DOMAIN`, `SES_CONFIGURATION_SET`
- dbt pilot toggles: `enable_ga4`, `enable_search_console`, `enable_linkedin`, `enable_tiktok`

Update this file when entitlements are implemented or renamed.
