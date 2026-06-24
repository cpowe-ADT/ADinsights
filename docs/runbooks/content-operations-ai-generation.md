# Content Operations — AI Generation Runbook

Status: disabled by default; live provider calls are gated.
Timezone baseline: `America/Jamaica`.

Operates the AI caption (text) and image generation surfaces for Content Ops,
including the Regional AI Content Agents. Live calls to OpenAI/Anthropic are
**disabled by default** and must be enabled deliberately, per environment, with
cost and quota controls verified and a rollback ready. Enabling a provider turns
on real outbound API calls that **spend money** and **send tenant content to a
third party**, so treat enablement as a gated change.

## Scope

- Endpoints:
  - `GET/POST /api/content-ops/regional-agents/` (+ detail) — RegionalAgentProfile CRUD.
  - `POST /api/content-ops/workspaces/{id}/images/generate/` — enqueue an image job.
  - `POST /api/content-ops/briefs/{brief_id}/captions/generate/` — now accepts `regional_agent_profile_id`.
- Code: `backend/content_ops/providers/` (factory + OpenAI/Anthropic caption, OpenAI image),
  `image_generation.py`, `generation.py`, `metering.py`, `assets.py`.
- Models/migrations: `RegionalAgentProfile`, `AIUsageRecord` (+ MediaAsset reference fields); `0003`–`0005`.

## Providers (default OFF, fail closed)

- Text: `CONTENT_OPS_TEXT_PROVIDER` = `disabled` (default) | `openai` | `anthropic`.
- Image: `CONTENT_OPS_IMAGE_PROVIDER` = `disabled` (default) | `openai` (reuses the OpenAI key/base URL).
- When `disabled`, generation fails closed with `provider_not_configured`; no outbound call, no spend.
- OpenAI: `CONTENT_OPS_OPENAI_API_KEY`, `CONTENT_OPS_OPENAI_BASE_URL` (`https://api.openai.com/v1`),
  `CONTENT_OPS_OPENAI_MODEL` (`gpt-5.1`), `CONTENT_OPS_OPENAI_IMAGE_MODEL` (`gpt-image-1`),
  `CONTENT_OPS_OPENAI_IMAGE_SIZE` (`1024x1024`). The caption adapter auto-selects
  `max_completion_tokens` (GPT‑5/o‑series) vs `max_tokens`; the image adapter
  handles `gpt-image-1` vs `dall-e-*` parameter differences.
- Anthropic: `CONTENT_OPS_ANTHROPIC_API_KEY`, `CONTENT_OPS_ANTHROPIC_BASE_URL`
  (`https://api.anthropic.com/v1`), `CONTENT_OPS_ANTHROPIC_MODEL` (`claude-opus-4-8`),
  `CONTENT_OPS_ANTHROPIC_VERSION` (`2023-06-01`).
- Timeouts: `CONTENT_OPS_TEXT_TIMEOUT` (30s), `CONTENT_OPS_IMAGE_TIMEOUT` (60s).

## Caps, quotas & cost rates

- Per-tenant monthly token cap: `CONTENT_OPS_TENANT_MONTHLY_TOKEN_CAP` (0 = unlimited);
  checked before each text provider call; over-cap jobs fail `token_quota_exceeded`.
  Image generation is metered as **images**, not tokens, so it does NOT count against this cap.
- Caption quotas: `CONTENT_OPS_CAPTION_ACTIVE_JOB_LIMIT` (25), `..._DAILY_JOB_LIMIT` (100),
  `..._DAILY_CANDIDATE_LIMIT` (300) → reasons `caption_active_limit_exceeded`, etc.
- Image quotas: `CONTENT_OPS_IMAGE_ACTIVE_JOB_LIMIT` (10), `..._DAILY_JOB_LIMIT` (50),
  `..._DAILY_IMAGE_LIMIT` (100) → reasons `image_active_limit_exceeded`,
  `image_daily_limit_exceeded`, `image_daily_image_limit_exceeded` (HTTP 400 with `reason`/`quota`).
- Generated asset size guard: `CONTENT_OPS_GENERATED_ASSET_MAX_BYTES` (15 MiB). Oversized or
  wrong-mime output is quarantined with no stored file and can never be published.
- Cost rates (0 unless set; persisted to `AIUsageRecord.estimated_cost`):
  `CONTENT_OPS_OPENAI_USD_PER_1K_TOKENS`, `CONTENT_OPS_ANTHROPIC_USD_PER_1K_TOKENS`,
  `CONTENT_OPS_OPENAI_USD_PER_IMAGE`. Set these BEFORE enabling so metering is accurate from the first call.

## Publishing prerequisite

Publishing a generated (or uploaded) asset to Meta requires a public HTTPS fetch URL.
Set `CONTENT_OPS_PUBLIC_MEDIA_BASE_URL` to the deployed public-media base; generated assets
then seed their own `renditions.public_url`. Without it, an image-only draft is blocked at
publish preflight with `asset_public_url_missing`. Live publishing stays gated by
`CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING` / `CONTENT_OPS_META_INSTAGRAM_BETA` (both default off).

## Metering & observability

- Every successful generation writes an `AIUsageRecord` (provider, input/output/total tokens,
  images, estimated_cost) — aggregate only, no user-level data.
- Emit structured logs with `tenant_id` / `task_id`; never log API keys, prompts, or raw provider payloads.
- Monitor: tokens & images per tenant vs caps, estimated cost, quota-block counts, provider error/timeout rate.

## Safe enablement checklist (per environment)

1. Confirm this is a gated/staging environment, not blind production.
2. Set the relevant cost rate env(s) to real non-zero values first.
3. Set `CONTENT_OPS_TENANT_MONTHLY_TOKEN_CAP` to a deliberate non-zero value (avoid unlimited initially).
4. Review/lower image quotas if the defaults (10/50/100) are too high.
5. Provide the provider API key(s); confirm base URL + model are intended.
6. Flip exactly one provider: `CONTENT_OPS_TEXT_PROVIDER=openai|anthropic` and/or `CONTENT_OPS_IMAGE_PROVIDER=openai`.
7. Smoke test one caption and (if enabled) one image for a safe tenant; confirm an `AIUsageRecord` row with a sane cost.
8. Force one quota block (e.g. `image_active_limit_exceeded`) and confirm the 400 `reason`/`quota` is returned.
9. Confirm no secrets/prompts appear in logs.

## Rollback

1. Set `CONTENT_OPS_TEXT_PROVIDER=disabled` and `CONTENT_OPS_IMAGE_PROVIDER=disabled`.
2. Confirm generation now fails closed with `provider_not_configured` and no outbound calls occur.
3. Optionally rotate the provider API key.
4. `AIUsageRecord` rows are durable for cost reconciliation; rollback does not delete them. No migration rollback needed.

## Triage

- `provider_not_configured` → provider env is `disabled` or key missing (expected default).
- `*_limit_exceeded` / `token_quota_exceeded` → quota; raise limits deliberately or wait for the window.
- Provider timeout/error → check base URL, model name, key validity, upstream status. The client only
  ever sees a safe reason code; check server logs for the upstream detail.

## Related docs

- `docs/runbooks/content-operations-publishing.md`
- `docs/project/api-contract-changelog.md`
- `docs/project/feature-flags-reference.md`
