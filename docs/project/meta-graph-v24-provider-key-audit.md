# Meta Graph v24 Provider Key Audit

Date: 2026-06-23  
Status: needs logged-in official verification

## Purpose

This audit is the handoff artifact for verifying ADinsights Meta Page/Post reporting semantics against official Meta Graph API behavior. It should be completed before changing OAuth scopes, `META_GRAPH_API_VERSION`, or the canonical metric registry.

## Current Repo Position

ADinsights is intentionally pinned to:

- `META_GRAPH_API_VERSION=v24.0`

The current repo contract says:

- Do not add `read_insights`.
- Page Insights uses Page-scoped permissions such as `pages_show_list`, `pages_read_engagement`, and `pages_manage_metadata`.
- Instagram reporting is optional and remains outside the current SLB v1 report scope.
- Stable ADinsights product metrics should resolve through `backend/integrations/services/metric_registry.py`.

## Provider Key Verification Matrix

| ADinsights product metric | Current primary provider key(s) | Current fallback key(s) | Needs official verification | Notes |
| --- | --- | --- | --- | --- |
| `page_reach` | `page_total_media_view_unique` | `page_impressions_unique` | yes | Verify whether this is the correct v24 reach proxy. |
| `page_impressions` | `page_media_view` | `page_impressions` | yes | Verify whether media view semantics should replace legacy impressions. |
| `page_engagements` | `page_post_engagements` | none | yes | Confirm availability for Page/date range. |
| `page_actions` | `page_total_actions` | none | yes | Confirm current Page metric status. |
| `page_follows` | `page_daily_follows_unique`, `page_follows` | none | yes | Confirm reporting period support. |
| `post_impressions` | `post_media_view` | `post_impressions` | yes | Legacy key should remain fallback-only unless verified otherwise. |
| `post_reach` | `post_total_media_view_unique` | `post_impressions_unique`, `post_impressions_organic_unique` | yes | Confirm current v24 post reach semantics. |
| `post_clicks` | `post_clicks` | none | yes | Confirm period and availability. |
| `post_reactions_like` | `post_reactions_by_type_total`, `post_reactions_like_total` | none | yes | Confirm breakdown response shape. |
| `post_reactions_love` | `post_reactions_by_type_total`, `post_reactions_love_total` | none | yes | Confirm breakdown response shape. |
| `content_ops_impressions` | `post_media_view` | `post_impressions` | yes | Content Ops depends on stored Meta post IDs and post insight rows. |
| `content_ops_reach` | `post_total_media_view_unique` | `post_impressions_unique`, `post_impressions_organic_unique` | yes | Content Ops should not synthesize missing values. |

## Official Verification Checklist

Complete this in a logged-in Meta Developer or Graph Explorer session:

1. Confirm current official latest Graph API version.
2. Confirm `v24.0` remains callable for the configured app.
3. Confirm Page Insights endpoint and metric names for a selected Page.
4. Confirm Post Insights endpoint and metric names for a selected Page post.
5. Confirm Marketing API ad account insights still works for the selected ad account.
6. Capture whether each metric returns data, an empty list, or a Graph error.
7. Record error codes without tokens or raw sensitive payloads.

## Decision Rules

- If a provider key is invalid in v24, update the registry, tests, generated catalog docs, and runbook together.
- If a provider key is valid but returns no rows for the selected Page/range, keep report coverage blocked and do not invent values.
- If a newer Graph version changes semantics, create a separate v25 migration plan instead of changing the v24 runtime pin in-place.
- If official docs require a scope change, route to Raj, Mira, Sofia, Andre, Maya, Leo, and Nina before implementation.

## Verification Results (2026-06-25)

Verified against the live SLB Page `106570709383133` ("Students' Loan Bureau") using the stored
Page access token via a tenant-scoped diagnostic probe (no tokens printed; aggregate-only).

Token state (from `debug_token`):

- Type `PAGE`, `is_valid=true`, `profile_id=106570709383133`, non-expiring.
- Scopes granted: `pages_show_list`, `pages_read_engagement`, `pages_manage_metadata`,
  `pages_manage_ads`, `pages_messaging`, `ads_management`, `ads_read`, `business_management`,
  `catalog_management`, `public_profile`.
- **`read_insights` is NOT granted.**

Provider-key validity:

- Every registry Page and Post metric key resolved as **valid** in v24 — the `/insights` calls
  return HTTP 200 with **no `error_code` 100/3001**, and `MetaMetricSupportStatus` marks all 21
  probed metrics `supported=true`. The registry keys (`page_media_view`,
  `page_total_media_view_unique`, `page_post_engagements`, `page_daily_follows_unique`,
  `post_media_view`, `post_total_media_view_unique`, `post_clicks`,
  `post_reactions_by_type_total`) are correct for v24. **No registry change is required.**

Data result:

- Page Insights: HTTP 200 with empty `data: []` for May 2026 **and** for a recent control window.
- Post Insights: HTTP 200 with empty `data: []` for a stored May post.
- `fan_count` / `followers_count` / `is_published` returned `null` (Page name resolved normally).
- `normalize_insights_payload` correctly yields 0 points (no parse/store bug).

Classification: **`valid_zero_rows` driven by the permission model.** Graph API v24 requires the
`read_insights` permission for `/{page}/insights`, `/{post}/insights`, and Page stat fields such as
`fan_count`. With only `pages_read_engagement`, Graph returns 200-with-empty-data (silently, not a
permission error), so the pipeline correctly stores zero rows and keeps the report export-blocked.

Decision (per the rules above): provider keys are valid → do **not** rewrite the registry; do **not**
invent values; keep coverage blocked. Because `read_insights` is intentionally out of scope, real
organic numbers can only enter the report via an operator upload of Meta-exported Page/Post values
mapped into the existing aggregate tables. Required human verification before that build: confirm in
a logged-in Meta Business Suite session whether this Page actually has May 2026 Page/Post insight
values — if Meta UI shows none, the empty report is correct; if it shows values, decide between
read_insights approval (App Review) or the export-upload fallback.

## Resolution (2026-06-25): edge-sourced engagement (no read_insights)

`/{object}/insights` is read_insights-gated, but the Graph object **edges** are not — they resolve
with `pages_read_engagement` / `pages_show_list`, which the stored Page token already holds. Re-tested
against the SLB Page:

- `GET /{page}?fields=followers_count,fan_count` → `6023` (real; the earlier `null` was an artifact of
  a combined multi-field request, not a permission block).
- `GET /{post}?fields=shares,reactions.summary(true),comments.summary(true)` → real per-post reaction,
  comment, and share counts.
- Instagram: the SLB Page has **no** linked `instagram_business_account` / `connected_instagram_account`,
  so there is no IG organic data to pull for this report.

Implemented `backend/integrations/meta_page_insights/engagement_edges.py` and wired it into
`slb_backfill_meta_reporting` (organic_facebook_posts dataset). It stores real follower counts under
`page_follows` and per-post engagement under `post_reactions_total` / `post_comments_total` /
`post_shares_total` in the existing aggregate tables — no `read_insights`, no Graph-version bump, no
faked values (a measured `0` is kept; an unreadable metric is skipped), and no live calls during
preview/export. Reach/impressions/clicks remain read_insights-gated and stay absent. After backfill the
SLB report's organic Page/Post sections move from "metrics unavailable" to real follower + engagement
values; the remaining export gate is comparison-history coverage (backfill prior months), not a
permission or code defect.

