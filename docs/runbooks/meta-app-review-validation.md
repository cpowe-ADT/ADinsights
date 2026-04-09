# Meta App Review and Validation Runbook

Timezone baseline: `America/Jamaica`.

## Related docs

- Canonical catalog: `docs/project/meta-permissions-catalog.yaml`
- Human policy/profile: `docs/project/meta-permission-profile.md`
- Submission checklist: `docs/runbooks/meta-app-review-submission-checklist.md`
- Reusable copy pack: `docs/runbooks/meta-app-review-copy-pack.md`

## Permission policy (runtime gate vs optional scopes)

Runtime gate enforced by backend (`backend/integrations/views.py`):

- `(ads_read OR ads_management)` AND
- `business_management` AND
- `pages_read_engagement` AND
- `pages_show_list`

Required-now App Review permissions for active flow:

- `ads_read`
- `ads_management`
- `business_management`
- `pages_read_engagement`
- `pages_show_list`

Optional near-term permissions (request only when feature is active):

- `instagram_basic`
- `instagram_manage_insights`
- `catalog_management`
- `pages_manage_ads`
- `pages_manage_metadata`
- `pages_messaging`

Notes:

- `META_OAUTH_SCOPES` defaults can include broader scopes than the runtime gate.
- Runtime gate is authoritative for onboarding/provisioning readiness.
- Use the submission checklist doc to enforce feature-gated optional requests.
- Do not request `read_insights` in Facebook Login. Page Insights setup now relies on
  `pages_show_list`, `pages_read_engagement`, and `pages_manage_metadata`.
- `instagram_basic` and `instagram_manage_insights` are optional only. They are not part of the
  current ADinsights baseline Facebook Login authorize request and should be documented only when an
  active Instagram feature path actually needs them.
- Meta's public changelog currently exposes `v25.0`, but ADinsights remains pinned to
  `META_GRAPH_API_VERSION=v24.0` until an explicit migration is tested end-to-end.

## Test app prerequisites

1. Create a fresh Meta Test App and add a test user.
2. Configure `META_APP_ID`, `META_APP_SECRET`, `META_LOGIN_CONFIG_ID`, `META_OAUTH_REDIRECT_URI`.
3. Ensure ADinsights backend/frontend are reachable.
4. Confirm Airbyte defaults are set for provisioning (`AIRBYTE_DEFAULT_WORKSPACE_ID`, `AIRBYTE_DEFAULT_DESTINATION_ID`).

Local/dev note:

- Launcher-backed local OAuth uses the selected frontend origin plus
  `/dashboards/data-sources` as `META_OAUTH_REDIRECT_URI`.
- `http://localhost:5173` on launcher profile 1 still matches the checked-in default Meta app
  configuration.
- If `META_OAUTH_REDIRECT_URI` is explicit, ADinsights now treats it as authoritative and will not
  silently switch to another runtime host/port.
- The checked-in local runtime pins `backend/.env` to
  `META_OAUTH_REDIRECT_URI=http://localhost:5173/dashboards/data-sources`, so manual non-launcher
  runs stay on `5173` unless you export a different runtime env value before starting Django.
- Alternate launcher frontend ports can work for Meta OAuth only when the Meta app redirect/domain
  settings are updated to the exact same origin and redirect path first.
- If Facebook shows `Can't load URL`, check the exact App Domain and valid redirect URI in the Meta
  app settings before retrying.

## Operator-run validation flow

1. Start OAuth:
   - `POST /api/integrations/meta/oauth/start/`
2. Exchange callback code/state:
   - `POST /api/integrations/meta/oauth/exchange/`
3. Complete asset selection:
   - `POST /api/integrations/meta/pages/connect/` with `selection_token`, `page_id`, `ad_account_id`
4. Provision + trigger sync:
   - `POST /api/integrations/meta/provision/`
   - `POST /api/integrations/meta/sync/`
5. Verify direct read surfaces:
   - `GET /api/meta/accounts/` returns at least one account
   - `GET /api/meta/insights/?account_id=<act_id>&level=ad&since=<today-30>&until=<yesterday>`
   - `GET /api/datasets/status/` returns the expected live-reporting stage for the environment
   - `GET /api/integrations/social/status/` Meta row now includes additive `reporting_readiness`
     fields for `stage`, `direct_sync_status`, `warehouse_status`, and `dataset_live_reason`
6. Validate token using Meta Access Token Debugger.
7. Validate equivalent Graph API calls in Graph API Explorer.

## Required Troubleshooting Classification

Inspect these endpoints in order before changing code or reviewer guidance:

1. `GET /api/integrations/social/status/`
2. `GET /api/datasets/status/`
3. `GET /api/meta/accounts/`
4. `GET /api/meta/pages/`
5. `GET /api/metrics/combined/`

Classify the failure as exactly one of:

- `auth/setup failure`
- `permission failure`
- `asset discovery failure`
- `direct sync failure`
- `warehouse adapter disabled`
- `missing/stale/default snapshot`

Do not collapse these into one generic “Meta broken” label in evidence artifacts or remediation
notes.

## Restore flow validation

When Page Insights is still connected but the marketing credential is missing:

1. Confirm `GET /api/integrations/social/status/` returns Meta `reason.code=orphaned_marketing_access`.
2. Run `POST /api/integrations/meta/recovery/preview/` and confirm the stored Meta token still returns:
   - at least one Page
   - at least one ad account
   - `missing_required_permissions: []`
3. Save the selected assets through `POST /api/integrations/meta/pages/connect/`.
4. Treat `POST /api/integrations/meta/provision/` as best-effort during restore:
   - in local/dev, Airbyte may be unavailable and provision can fail cleanly
   - restore is still considered successful if direct sync succeeds
5. Run `POST /api/integrations/meta/sync/` and confirm reporting status becomes active.
6. Verify:
   - `GET /api/integrations/social/status/` no longer reports `orphaned_marketing_access`
   - `GET /api/meta/accounts/` is repopulated
   - `GET /api/datasets/status/` truthfully reports `ready`, `missing_snapshot`, `stale_snapshot`,
     `default_snapshot`, or `adapter_disabled`
   - dashboard recovery messaging stays truthful if Airbyte was not provisioned

## App Review submission prep

Before submitting to Meta:

1. Complete `docs/runbooks/meta-app-review-submission-checklist.md`.
2. Confirm the permission set in submission matches `docs/project/meta-permissions-catalog.yaml`.
3. Confirm runtime gate wording in submission artifacts matches backend enforcement.
4. Confirm each use-case statement explicitly says "on behalf of onboarded business customers."
5. Confirm each screencast script says "demonstrate the complete Facebook login process."
6. Use the copy blocks from `docs/runbooks/meta-app-review-copy-pack.md` unless a specific business case requires documented custom wording.

## Graph API Explorer checks (examples)

Use the same granted token:

- `GET /me/adaccounts?fields=id,account_id,name,currency,account_status,business_name`
- `GET /act_<account_id>/campaigns?fields=id,name,status,effective_status,objective,updated_time`
- `GET /act_<account_id>/adsets?fields=id,campaign_id,name,status,effective_status,daily_budget,updated_time`
- `GET /act_<account_id>/ads?fields=id,campaign_id,adset_id,name,status,effective_status,updated_time`
- `GET /act_<account_id>/insights?level=ad&time_increment=1&time_range={"since":"YYYY-MM-DD","until":"YYYY-MM-DD"}&fields=date_start,account_id,campaign_id,adset_id,ad_id,impressions,reach,spend,clicks,cpc,cpm,actions`

## Evidence capture format

Store one markdown artifact per run in `docs/project/evidence/meta-validation/<timestamp>.md`.
Start from `docs/project/evidence/meta-validation/_TEMPLATE.md` and save as a timestamped file.
Each artifact must include:

- Run timestamp (local and UTC)
- Operator name
- App ID (redacted), ad account ID (redacted)
- Endpoint requests + response status
- Token Debugger screenshots/notes
- Graph API Explorer query screenshots/notes
- Final outcome (`pass`/`fail`) and remediation notes

Never include raw access tokens in artifacts.
