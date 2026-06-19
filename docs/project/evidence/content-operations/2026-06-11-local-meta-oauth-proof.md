# Local Meta OAuth Proof Attempt

Date: 2026-06-11
Timezone baseline: `America/Jamaica`
Goal: Prove ADinsights local Meta OAuth connection for Content Ops using Meta app `2921903668150890`.

## Result

Status: BLOCKED before OAuth callback completion.

The local runtime, backend OAuth configuration, and OAuth start URL are proven correct. The browser
OAuth completion remains blocked by Safari's local HTTPS certificate warning for
`https://localhost:5173`, which requires a human browser-trust action before the Data Sources UI can
load and redirect through Meta.

No publishing feature was added or enabled.

## Evidence Captured

- Docker Desktop was started successfully.
- `scripts/dev-launch.sh --profile 1 --strict-profile --non-interactive --no-update --no-pull --no-open --no-demo-check`
  started the local stack after first-run image build.
- Launcher active runtime:
  - `DEV_FRONTEND_URL=https://localhost:5173`
  - `META_OAUTH_REDIRECT_URI=https://localhost:5173/dashboards/data-sources`
  - `META_LOCAL_OAUTH_SUPPORTED=1`
- Docker services were running:
  - `backend`
  - `frontend`
  - `postgres`
  - `redis`
  - `celery_worker`
  - `celery_worker_snapshot`
  - `celery_worker_summary`
  - `celery_beat`
- `curl -ksS https://localhost:5173` returned the Vite app HTML.
- Backend container settings proof via Django shell:
  - `META_APP_ID=2921903668150890`
  - `META_APP_SECRET_SET=True`
  - `META_OAUTH_REDIRECT_URI=https://localhost:5173/dashboards/data-sources`
  - `FRONTEND_BASE_URL=https://localhost:5173`
- Meta app credentials were verified against Meta's app access token endpoint without printing the
  secret or token; app ID and secret pair returned valid.
- `/api/integrations/meta/setup/` returned:
  - `ready_for_oauth=true`
  - `redirect_uri=https://localhost:5173/dashboards/data-sources`
  - `graph_api_version=v24.0`
  - `login_mode=facebook_login_for_business`
  - `oauth_scopes=[ads_management, ads_read, business_management, catalog_management, pages_manage_ads]`
  - `login_configuration_id_configured=false`
- `/api/integrations/meta/oauth/start/` returned an authorization URL with:
  - host `www.facebook.com`
  - Graph dialog version `v24.0`
  - `client_id=2921903668150890`
  - `redirect_uri=https://localhost:5173/dashboards/data-sources`
  - signed `state` present
  - `oauth_flow=marketing`
- `/api/integrations/meta/pages/` returned existing local Page records:
  - `AdTelligent`
  - `Superior Parts Auto Hub`
  - `Superior Parts Ltd`
- `/api/content-ops/readiness/` returned current Content Ops blockers:
  - `meta_auth.state=needs_reauth`
  - `meta_auth.reason=meta_token_invalid`
  - `instagram_linkage.state=blocked`
  - `instagram_linkage.reason=instagram_not_linked`
  - `facebook_page_publishing.reason=publishing_identity_missing`
  - `facebook_page_publishing.missing_permissions=[pages_manage_posts]`
  - `instagram_publishing.reason=publishing_identity_missing`
  - `instagram_publishing.missing_permissions=[instagram_basic, instagram_content_publish]`
  - `reporting_readiness.state=ready`

## Blocker

Safari is currently stopped on:

`This Connection Is Not Private`

for local `https://localhost:5173`. The OAuth proof cannot complete until a human accepts/trusts the
local development certificate in the browser. The agent did not bypass the browser safety
interstitial.

## Not Proven Yet

- Data Sources UI login through Safari.
- Meta OAuth consent from the Data Sources UI.
- Callback return to `https://localhost:5173/dashboards/data-sources`.
- Newly refreshed stored Meta user/page token.
- Post-callback Content Ops readiness changing from `needs_reauth`.
- Connected Instagram business account discovery.
- App Review/publishing permission availability.

## Required Next Action

1. In Safari, accept the local development certificate warning for `https://localhost:5173`.
2. Open `https://localhost:5173/login?next=/dashboards/data-sources?sources=social`.
3. Log in as `devadmin@local.test`.
4. Start the Meta OAuth flow from Data Sources.
5. Complete Meta consent in the already-authenticated Safari session.
6. Verify callback, API connection state, pages, Instagram account linkage, granted scopes, and
   Content Ops readiness again.
