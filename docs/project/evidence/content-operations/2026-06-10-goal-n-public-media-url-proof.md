# Content Operations Goal N Public Media URL/CDN Proof

Date: 2026-06-10
Timezone: America/Jamaica
Scope: backend/docs/deploy as needed
Status: backend proof path implemented; live publishing remains disabled

## Summary

Goal N adds the public media boundary required before live Instagram publishing. ADinsights can now
produce a Meta-fetchable HTTPS URL using `CONTENT_OPS_PUBLIC_MEDIA_BASE_URL` plus an opaque media
asset UUID, while keeping tenant-private `storage_key` values and filesystem paths out of public API
responses and evidence.

No Facebook Page or Instagram Graph publishing call is enabled by this goal.

## Implemented Proof Boundary

- `CONTENT_OPS_PUBLIC_MEDIA_BASE_URL`: deployment-controlled HTTPS base URL for public media fetches.
- `GET /api/content-ops/public-media/<asset_id>/`: unauthenticated public fetch path intended for
  Meta/CDN fetches.
- `GET /api/content-ops/assets/<asset_id>/public-media-proof/`: authenticated operator proof action
  that returns redacted fetchability metadata.

Public fetch serves an asset only when all of these are true:

- asset exists and `status=available`
- storage key resolves safely under `CONTENT_OPS_ASSET_ROOT`
- file exists and has non-zero length
- asset is attached to the active version of a draft in one of these states:
  - `client_approved`
  - `scheduled`
  - `publishing`
  - `published`
  - `partially_published`

## Security Properties

- Public URLs use asset UUIDs, not `tenant_id`, `workspace_id`, `storage_key`, or local paths.
- Public proof responses expose only scheme, host, redacted URL, MIME type, content length, approval
  state, safe failure code, and `storage_key_exposed=false`.
- Public fetch responses use generic `404` messages for missing, unsafe, or unapproved assets.
- Authenticated asset `download_url` remains separate and must not be used for Meta container
  creation.
- Signed object-store URL generation remains out of scope. If a future CDN uses signed URLs, query
  secrets must be stripped from evidence and never logged.

## Operator Proof Checklist

1. Set `CONTENT_OPS_PUBLIC_MEDIA_BASE_URL` to the deployed HTTPS route that maps to
   `/api/content-ops/public-media/<asset_id>/`.
2. Upload or generate an image/video asset.
3. Attach it to a draft version.
4. Complete internal and client approval so the exact version is active and `client_approved`.
5. Call `GET /api/content-ops/assets/<asset_id>/public-media-proof/`.
6. Confirm:
   - `ready=true`
   - `public_url_is_https=true`
   - `approved_for_public_fetch=true`
   - `content_length > 0`
   - `mime_type` starts with `image/` or `video/`
   - `storage_key_exposed=false`
7. Fetch the public media URL from a clean unauthenticated session.
8. Confirm:
   - HTTP `200`
   - expected `Content-Type`
   - expected `Content-Length`
   - no tenant ID, workspace ID, `storage_key`, or filesystem path in response headers/body

## Remaining Launch Blockers

- Deployed CDN/app route must be configured and tested in staging.
- Goal O/P live provider adapters are not implemented.
- Goal R/S staging publish evidence does not exist.
- Meta App Review approval and final release gates remain required.

## Validation Results

- `backend/.venv/bin/pytest -q backend/tests/test_content_ops_api.py backend/tests/test_content_ops_publisher.py backend/tests/test_schema_regressions.py` passed.
- `make backend-lint && make backend-test` passed.
- `git diff --check -- backend/content_ops/assets.py backend/content_ops/views.py backend/content_ops/urls.py backend/core/settings.py backend/.env.sample backend/tests/test_content_ops_api.py backend/tests/test_schema_regressions.py docs/project/content-operations-api-contract.md docs/runbooks/content-operations-publishing.md docs/project/feature-flags-reference.md docs/project/api-contract-changelog.md docs/project/evidence/content-operations/2026-06-10-goal-n-public-media-url-proof.md docs/ops/doc-index.md docs/ops/agent-activity-log.md` passed.
- Scope gatekeeper advisory packet: `ESCALATE_ARCH_RISK` for backend plus docs, with architecture-sensitive settings change and contract-risk API path changes. Required reviewers: Raj, Mira, Sofia, Hannah.
- Contract guard advisory packet: `WARN_POSSIBLE_CONTRACT_CHANGE`; non-breaking API contract change with required changelog/docs already updated.
- ADinsights preflight packet persisted at `docs/project/evidence/content-operations/preflight-2026-06-10-goal-n-public-media/`.
- ADinsights preflight result: `GATE_BLOCK`, expected until architecture/contract review, security follow-up, live adapters, staging proof, App Review approval, and final release approval are complete.
