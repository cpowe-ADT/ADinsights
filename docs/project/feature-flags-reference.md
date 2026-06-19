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

## Content Operations

- `CONTENT_OPS_META_MVP` gates the tenant-facing Content Operations workspace and non-live Meta
  publishing workflow surfaces. It does not enable live Meta Graph publishing, OAuth scope
  expansion, Instagram containers, or AI provider calls by itself.
- `CONTENT_OPS_META_INSTAGRAM_BETA` gates Instagram publishing beta work after the current Meta
  permission family, linked professional account setup, and public asset URL proof are validated.
  Default is off. When enabled, the implemented Instagram Graph adapter can create media containers,
  poll container status, and publish media for tenant-local selected identities. It must stay off for
  production tenants until App Review evidence, staging proof, token-handling proof, observability,
  rollback, and Raj/Maya/Nina signoff are complete.
- `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING` gates the implemented live Facebook Page provider adapter.
  Default is off. It must stay off for production tenants until App Review evidence, token-handling
  proof, observability, rollback, staging proof, and Raj/Maya/Nina signoff are complete.
- `CONTENT_OPS_LIVE_AI_GENERATION` gates future live caption/graphic provider calls after quota,
  redaction, eval, and billing controls are approved.

Content Ops flags are staged rollout controls only. They must not collapse Meta auth, Page
selection, Instagram linkage, Facebook publishing readiness, Instagram publishing readiness, and
reporting readiness into one generic connected state.

## Operational runtime controls (not entitlement flags)
- `CORS_ALLOWED_ORIGINS`, `CORS_ALLOW_ALL_ORIGINS`, `CORS_ALLOW_CREDENTIALS`
- `CONTENT_OPS_PUBLIC_MEDIA_BASE_URL` configures the deployed HTTPS public media route used by Meta
  fetches for approved Content Ops media. It is not a live publishing flag and does not enable Graph
  posting by itself.
- `DRF_THROTTLE_AUTH_BURST`, `DRF_THROTTLE_AUTH_SUSTAINED`, `DRF_THROTTLE_PUBLIC`
- `SES_EXPECTED_FROM_DOMAIN`, `SES_CONFIGURATION_SET`

Update this file when entitlements are implemented or renamed.
