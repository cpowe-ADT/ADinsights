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

