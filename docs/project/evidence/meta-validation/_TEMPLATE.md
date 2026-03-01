# Meta Validation Evidence - <timestamp>

- Run timestamp (America/Jamaica):
- Run timestamp (UTC):
- Operator:
- Environment: staging
- Meta App ID (redacted):
- Meta ad account ID (redacted):
- Tenant ID (redacted):

## OAuth and setup checks

- `POST /api/integrations/meta/oauth/start/`:
- `POST /api/integrations/meta/oauth/exchange/`:
- `POST /api/integrations/meta/pages/connect/`:
- `POST /api/integrations/meta/provision/`:
- `POST /api/integrations/meta/sync/`:

## Direct read API checks

- `GET /api/meta/accounts/` status:
- Account count:
- `GET /api/meta/insights/?account_id=<id>&level=ad&since=<today-30>&until=<yesterday>` status:
- Insights row count:

## Meta debugger and explorer checks

- Access Token Debugger result:
- Graph API Explorer query parity:
  - `/me/adaccounts`
  - `/act_<account_id>/campaigns`
  - `/act_<account_id>/adsets`
  - `/act_<account_id>/ads`
  - `/act_<account_id>/insights`

## Outcome

- Final status: pass | fail
- Notes:
- Follow-up actions:

> Do not include raw access tokens or unredacted identifiers.
