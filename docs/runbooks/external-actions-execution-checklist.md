# External Actions Execution Checklist (Run-This-Now)

Purpose: operator command pack for the external AWS/provider steps that cannot be completed from repo-only automation.

Source of truth: `docs/runbooks/external-actions-aws.md`.

Timezone for all evidence: `America/Jamaica`.

## 0) One-time setup

```bash
cd /Users/thristannewman/ADinsights

export AWS_PROFILE=adinsights-prod
export AWS_REGION=us-east-1
export API_BASE_URL=https://<staging-or-prod-api-host>
export AIRBYTE_BASE_URL=https://<staging-or-prod-airbyte-host>
export AIRBYTE_API_AUTH_HEADER="Bearer <airbyte-api-token>"
export AIRBYTE_WORKSPACE_ID=<workspace-uuid>

DATE_EST="$(TZ=America/Jamaica date +%Y-%m-%d-est)"
EVIDENCE_DIR="docs/project/evidence/phase1-closeout/external"
```

## 1) `S7-D` SES sender readiness

### 1.1 Verify identity + DKIM + sandbox state

```bash
aws sesv2 get-account --region "$AWS_REGION"
aws sesv2 get-email-identity --email-identity adtelligent.net --region "$AWS_REGION"
aws sesv2 get-email-identity --email-identity adtelligent.net --region "$AWS_REGION" \
  --query 'DkimAttributes.Tokens' --output text
```

Expected:
- `ProductionAccessEnabled` is `true`.
- `VerifiedForSendingStatus` is `true`.
- DKIM status is `SUCCESS`.

### 1.2 Verify SPF + DMARC

```bash
dig +short TXT adtelligent.net
dig +short TXT _dmarc.adtelligent.net
```

Expected:
- SPF record includes the approved SES sender policy.
- DMARC policy exists and aligns with sender domain policy.

### 1.3 Smoke email flows

Password reset (public endpoint):

```bash
curl -sS -X POST "$API_BASE_URL/api/auth/password-reset/" \
  -H "Content-Type: application/json" \
  -d '{"email":"<test-user-email>"}'
```

Invite flow (admin token + invite endpoint):

```bash
ADMIN_TOKEN="$(curl -sS -X POST "$API_BASE_URL/api/auth/login/" \
  -H "Content-Type: application/json" \
  -d '{"username":"<admin-username>","password":"<admin-password>"}' \
  | jq -r '.access // .access_token')"

curl -sS -X POST "$API_BASE_URL/api/users/invite/" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email":"<invite-test-email>","role":"ANALYST"}'
```

### 1.4 Evidence file

```bash
cp "$EVIDENCE_DIR/templates/ses-verification-template.md" \
  "$EVIDENCE_DIR/ses-verification-$DATE_EST.md"
```

Attach:
- SES identity screenshots/JSON
- DKIM/SPF/DMARC proof
- invite/password-reset delivery proof (headers/screenshots)

## 2) `P1-X1` KMS production provisioning + wiring

### 2.1 Key + alias

```bash
KEY_ID="$(aws kms create-key \
  --description 'ADinsights production key' \
  --region "$AWS_REGION" \
  --query 'KeyMetadata.KeyId' --output text)"

aws kms create-alias \
  --alias-name alias/adinsights-prod \
  --target-key-id "$KEY_ID" \
  --region "$AWS_REGION"

aws kms describe-key --key-id alias/adinsights-prod --region "$AWS_REGION"
```

### 2.2 Wire app env (Secrets Manager example)

```bash
aws secretsmanager put-secret-value \
  --secret-id <backend-secret-id> \
  --secret-string "{\"KMS_PROVIDER\":\"aws\",\"KMS_KEY_ID\":\"alias/adinsights-prod\",\"AWS_REGION\":\"$AWS_REGION\"}" \
  --region "$AWS_REGION"
```

### 2.3 Smoke + dry-run rotation

```bash
DJANGO_SETTINGS_MODULE=core.settings \
KMS_PROVIDER=aws \
KMS_KEY_ID=alias/adinsights-prod \
AWS_REGION="$AWS_REGION" \
python3 scripts/rotate_deks.py --smoke

DJANGO_SETTINGS_MODULE=core.settings \
KMS_PROVIDER=aws \
KMS_KEY_ID=alias/adinsights-prod \
AWS_REGION="$AWS_REGION" \
python3 scripts/rotate_deks.py --dry-run
```

### 2.4 Evidence file

```bash
cp "$EVIDENCE_DIR/templates/kms-provisioning-template.md" \
  "$EVIDENCE_DIR/kms-provisioning-$DATE_EST.md"
```

Attach:
- key/alias metadata (redacted)
- policy permission proof
- smoke + dry-run outputs

## 3) `P1-X2` Airbyte production credential readiness

### 3.1 Load production credentials

Do this in your secret manager and Airbyte workspace for Meta + Google Ads.

### 3.2 Readiness scripts

```bash
python3 infrastructure/airbyte/scripts/verify_production_readiness.py
python3 infrastructure/airbyte/scripts/validate_tenant_config.py
python3 infrastructure/airbyte/scripts/airbyte_health_check.py
```

### 3.3 Controlled sync trigger (sample)

```bash
curl -sS -X POST "$AIRBYTE_BASE_URL/api/v1/connections/sync" \
  -H "Authorization: $AIRBYTE_API_AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"connectionId":"<connection-uuid>"}'
```

### 3.4 Evidence file

```bash
cp "$EVIDENCE_DIR/templates/airbyte-prod-readiness-template.md" \
  "$EVIDENCE_DIR/airbyte-prod-readiness-$DATE_EST.md"
```

Attach:
- script outputs
- connection IDs (redacted where needed)
- controlled sync proof

## 4) `P1-X4` Observability alert simulations

Use scenario instructions in `docs/runbooks/observability-alert-simulations.md`.

### 4.1 Minimum required proof

Run and capture all four:
1. Consecutive sync failures
2. Unexpectedly empty sync
3. Stale `/api/health/airbyte/`
4. Stale `/api/health/dbt/`

### 4.2 Evidence file

```bash
cp "$EVIDENCE_DIR/templates/observability-simulation-template.md" \
  "$EVIDENCE_DIR/observability-simulation-$DATE_EST.md"
```

Attach:
- alert IDs
- route targets (Slack/email/pager)
- fired + acknowledged timestamps

## 5) `P1-X9` Staging go/no-go rehearsal

### 5.1 Run full staging validation

```bash
cd /Users/thristannewman/ADinsights
backend/.venv/bin/ruff check backend && backend/.venv/bin/pytest -q backend
cd frontend && npm ci && npm test -- --run && npm run build && cd ..
make dbt-deps
DBT_PROJECT_DIR=dbt DBT_PROFILES_DIR=dbt dbt run --select staging
DBT_PROJECT_DIR=dbt DBT_PROFILES_DIR=dbt dbt snapshot
DBT_PROJECT_DIR=dbt DBT_PROFILES_DIR=dbt dbt run --select marts
cd infrastructure/airbyte && docker compose config && cd ../..
```

### 5.2 Health endpoint checks

```bash
curl -sS "$API_BASE_URL/api/health/"
curl -sS "$API_BASE_URL/api/health/airbyte/"
curl -sS "$API_BASE_URL/api/health/dbt/"
curl -sS "$API_BASE_URL/api/timezone/"
```

### 5.3 Evidence file

```bash
cp "$EVIDENCE_DIR/templates/staging-rehearsal-template.md" \
  "$EVIDENCE_DIR/staging-rehearsal-$DATE_EST.md"
```

## 6) `P1-X5-signoff` Raj + Mira gate

1. Add explicit Raj and Mira review comments in release PR/gate issue.
2. Link those URLs in the release evidence note:
   - `docs/project/evidence/phase1-closeout/release/gate-status-<date>-est.md`
3. Mark final decision:
   - `READY` if all external items are complete
   - `READY_PENDING_EXTERNALS` otherwise

## 7) Definition of done

All are true:
1. Evidence files exist for `S7-D`, `P1-X1`, `P1-X2`, `P1-X4`, `P1-X9`.
2. Raj/Mira sign-off links are recorded.
3. `docs/project/phase1-execution-backlog.md` entries are updated to `Done` with evidence paths.
