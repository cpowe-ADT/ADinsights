# API Contract Changelog (v0.1)

Purpose: track API payload changes that affect frontend, BI, or integrations.
Keep this brief and link to PRs or commits when available.

## Format

- **Date**
- **Endpoint**
- **Change**
- **Impact**
- **Owner**

## Entries

- **2026-06-25**
  - Endpoint: `GET/POST /api/analytics/report-layouts/` (+ `GET/PATCH/PUT/DELETE
.../{id}/`).
  - Change: Added tenant/owner-scoped CRUD for saved report-builder layouts
    (`SavedReportLayoutViewSet`, migration `0009_savedreportlayout`). Each row is
    `{id, name, description, config, is_shared, created_at, updated_at}` where
    `config` round-trips a `DashboardLayoutConfig` (the grid JSON the frontend
    renders: `{id, title, cols, rowHeight, widgets:[{id,type,x,y,w,h,dataKey,options}]}`).
    Querysets always filter to the request tenant; non-admins see their own
    layouts plus `is_shared` ones; `perform_create` stamps tenant + owner from
    the authenticated user (never from request body). Mirrors the existing
    `GoogleAdsSavedView` surface.
  - Impact: The report builder (`/dashboards/report-preview`) now persists
    layouts per tenant/user via this API, with a localStorage fallback when
    offline/unauthenticated. Fully additive — no existing endpoint or payload
    changed. Aggregate-only: `config` stores widget placement and data-binding
    keys, no per-user or PII data; no Meta Graph or dbt behavior touched.
  - Owner: Raj (integration)

- **2026-06-24**
  - Endpoint: `GET/POST /api/content-ops/brand-kits/` (+ `.../{id}/`, `.../{id}/set-default-logo/`,
    `.../{id}/clear-default-logo/`, `.../{id}/resolved-logo/`); `GET/POST /api/content-ops/footer-presets/`
    (+ `.../{id}/`); `GET/POST /api/content-ops/asset-collections/` (+ `.../{id}/`, `.../{id}/items/`,
    `DELETE .../{id}/items/{asset_id}/`); `GET/POST /api/content-ops/asset-tags/` (+ `.../{id}/`); new
    `assets/` actions `POST .../{id}/apply-overlay/`, `.../{id}/attest-rights/`,
    `.../{id}/approve-reference/`, `.../{id}/revoke-reference/`, `POST .../{id}/tags/` and
    `DELETE .../{id}/tags/{slug}/`; `POST /api/content-ops/sections/preview/`. `POST
/api/content-ops/assets/upload/` now also accepts optional `kind`/`logo_variant`/`reference_role`/
    `reference_region`/`reference_locale`, and the MediaAsset payload gained `kind`, `logo_variant`,
    `reference_role`, `reference_weight`, `reference_descriptor`, `usage_rights_attested` (+`_by`/`_at`/
    `_note`), `content_hash`, `file_size_bytes`, and `deliverable_group_id`.
  - Change: Added the Branded Graphic Composition layer on `content_ops` (Slices 1-3, all default-off,
    no provider call): a tenant-scoped brand-asset library (logos + approved references on MediaAsset
    via a `kind` discriminator with content-hash dedup, light/dark logo variants, usage-rights
    attestation, collections + tags); reusable `FooterPreset` and `BrandKit` (default logo + swap,
    footer/visual config) gated to a new brand-admin role set; a deterministic Pillow brand overlay
    (`apply-overlay` composites a gradient-scrim footer + logo onto a stored asset and snapshots the
    resolved inputs + content hashes into `ai_lineage`, with zero AI spend); and a provider-free
    composer core where `sections/preview/` resolves + defaults + lints a structured creative brief
    (per-field provenance + a weak/ok/strong signal) and returns the sanitized composer payload.
    Migration `0006_asset_library` (additive). New backend dependency: Pillow (pinned).
  - Impact: Frontend Content Ops can manage brand kits / footer presets / logo + reference libraries,
    brand an existing image deterministically, and preview/lint a brief before any spend. Fully
    additive and default-off — no OpenAI/Anthropic call and no tenant content leaves the platform.
    Existing asset/caption/image clients are unaffected: all new MediaAsset fields are optional and
    server-managed, and `assets/upload/` extra fields are optional. Brand-identity mutation (kits,
    footer presets, logos, reference approval) requires `CONTENT_OPS_BRAND_ADMIN_ROLES`; composition,
    tagging, and preview stay at edit level. No OAuth scope, Meta Graph publishing, or dbt mart
    behavior changed; lineage snapshots store ids/hashes/footer text only — no user-level data.
  - Owner: AI-built; Raj (integration) + Mira (architecture) AI review.

- **2026-06-24**
  - Endpoint: `GET/POST /api/content-ops/regional-agents/` (+ `GET/PATCH/DELETE .../{id}/`);
    `POST /api/content-ops/workspaces/{id}/images/generate/`;
    `POST /api/content-ops/briefs/{brief_id}/captions/generate/` (now accepts an optional
    `regional_agent_profile_id`).
  - Change: Added Regional AI Content Agents on the `content_ops` app — tenant-scoped
    `RegionalAgentProfile` CRUD (filterable by `workspace_id`, `region`, `is_active`) carrying
    region, locale/language, brand voice, and approved-reference scoping (locale/language/timezone
    default from the region when blank); a workspace image-generation action that enqueues an AI
    image job and returns `400` with `reason`/`quota` when active/daily-job/daily-image limits are
    reached; an optional regional agent on caption generation; pluggable OpenAI/Anthropic text and
    OpenAI image providers (default `disabled`, fail closed `provider_not_configured`); per-tenant
    `AIUsageRecord` token/image/cost metering plus an additive monthly token cap. Migrations 0003–0005.
  - Impact: Frontend Content Ops can manage regional agents, enqueue image jobs (and surface quota
    blockers), and pass a regional agent into caption generation. Additive and default-off — no live
    OpenAI/Anthropic call, no token spend, and no tenant content leaves the platform unless a provider
    is explicitly enabled. Existing caption clients can omit `regional_agent_profile_id` and are
    unaffected. No OAuth scope, Meta Graph publishing, or dbt mart behavior changed. `AIUsageRecord`
    is aggregate metering only (provider, token/image counts, estimated cost) — no user-level data.
  - Owner: AI-built; Raj (integration) + Mira (architecture) AI review.

- **2026-06-23**
  - Endpoint: `POST /api/integrations/meta/sync/`.
  - Change: Added an additive `organic_sync` response block and dispatch path. The endpoint still
    queues or runs the existing paid Meta direct sync, and now also attempts a bounded organic
    Facebook reporting bundle for selected analyzable Pages (`sync_page_posts`,
    `discover_supported_metrics`, `sync_page_insights`, and `sync_post_insights`). The bundle
    reports `queued`, `skipped`, `completed`, `completed_no_rows`, or `partial` without exposing
    tokens or raw provider payloads.
  - Impact: The Data Sources "Run Meta sync" action now tries the Page/Post reporting data path
    that SLB organic sections need, while existing clients can ignore the additive field. No OAuth
    scopes were added, `read_insights` remains excluded, and report preview/export still read only
    stored aggregate data.
  - Owner: Sofia (Backend API) + Andre (metric/data correctness) + Maya/Leo (Meta sync path)
    - Lina/Joel (Data Sources UX) + Raj/Mira review

- **2026-06-23**
  - Endpoint: `GET /api/reports/data-availability/`, `POST /api/reports/from-template/`, and
    `POST /api/reports/slb-monthly-template/`.
  - Change: Added a read-only report data availability endpoint for selecting reportable
    ad-account/Page/date targets before opening or creating a report. The response is
    tenant-scoped, stored-aggregate-only, and exposes dataset row counts, retained date ranges,
    coverage status, available Meta ad accounts, available Facebook Pages, blocking datasets, and
    recommended next actions. Template-created reports now preserve optional `account_id` and
    `page_id` filters alongside `client_id` and date range.
  - Impact: Frontend report flows can show whether paid Meta Ads, organic Facebook Page/Post, and
    Content Ops data exists before users open a mostly empty SLB report. Existing reports remain
    valid; the new endpoint is additive and does not call live provider APIs. Required datasets
    with `partial` stored coverage are treated as availability blockers so the source-selection
    screen does not present incomplete source data as export-ready.
  - Owner: Sofia (Backend API) + Andre (metric/data correctness) + Lina/Joel (report UX)
    - Maya/Leo (Meta sync path) + Raj/Mira review

- **2026-06-18**
  - Endpoint: `POST /api/dashboards/widget-preview/` and `POST /api/reports/{id}/preview/`.
  - Change: Organic Facebook Page/Post reporting now treats missing stored insight values as
    unavailable (`null`) instead of synthetic zeroes. Top-post table previews can include stored
    post activity columns (`date`, `content`, `permalink`) when synced posts exist even if Graph
    returns no post insight metric rows. Graph v24 Page/Post provider defaults are refreshed from
    the canonical metric catalog, and deprecated post impression keys are no longer requested by
    default.
  - Impact: Existing saved reports keep stable ADinsights product metric keys, but preview/export
    readiness is more truthful. Reports may render real synced post/activity rows with partial
    coverage while hard-blocking exports when required organic Page/Post insight history is
    unavailable.
  - Owner: Sofia (Backend API) + Andre (metric correctness) + Maya/Leo (Meta sync path)
    - Lina/Joel (report UX) + Raj/Mira review

- **2026-06-18**
  - Endpoint: `GET /api/dashboards/reporting-catalog/`, `GET /api/reports/templates/`,
    `POST /api/reports/from-template/`, and `POST /api/reports/slb-monthly-template/`.
  - Change: The reporting catalog now exposes additive `source_metric_semantics` so frontend and
    reporting clients can inspect the governed Graph-v24-aware provider keys behind stable
    ADinsights product metrics. Reports now have a backend template registry plus a generic
    create-from-template path; the SLB monthly endpoint remains as a compatibility wrapper.
  - Impact: Saved reports keep using stable product metric keys while ingestion, preview, Content Ops
    metrics, and exports share one backend metric registry. Future report templates can be added
    without hardcoding SLB-specific creation paths. Clients should ignore unknown additive catalog
    fields.
  - Owner: Sofia (Backend API) + Andre (metric correctness) + Mira (registry boundary)
    - Lina/Joel (frontend payload and UX) + Raj review

- **2026-06-17**
  - Endpoint: management commands `slb_report_evidence_bundle` and
    `slb_report_evidence_validate`.
  - Change: Evidence bundles now preserve diagnostics `source_health`, and offline evidence
    validation requires `slb_source_health.v1` with stored-aggregate/no-live-provider guardrails,
    Meta credential/Page/Airbyte/stored-row sections, required stored-row counts, and recommended
    next actions before a G2-G9 artifact set can pass.
  - Impact: G8 diagnostics/support evidence cannot be skipped during fixed-range cancellation
    evidence collection. Missing source-health proof becomes a validation blocker before G10
    adversarial review or G11 hardening starts.
  - Owner: Sofia (Backend API) + Omar/Hannah (diagnostics/support) + Nina (safety)
    - Raj/Mira review

- **2026-06-17**
  - Endpoint: `GET /api/reports/{id}/diagnostics/`; management command
    `slb_report_history_probe`.
  - Change: Report diagnostics now include a support-safe `source_health` block shared with the
    history probe. The block reports stored-aggregate-only/no-live-provider guardrails, Meta
    credential status counts, required scope coverage, Page connection counts, Meta Airbyte status
    counts and sanitized error categories, stored asset counts, stored row counts, and recommended
    next actions.
  - Impact: Operators can explain why an SLB report is missing or stale from the Report Detail page
    without reading logs or exposing tokens, raw provider payloads, Airbyte logs, ad account IDs,
    Page IDs, delivery emails, or user-level metrics.
  - Owner: Sofia (Backend API) + Omar/Hannah (diagnostics/support) + Lina/Joel (frontend UX)
    - Nina (safety) + Raj/Mira review

- **2026-06-17**
  - Endpoint: `POST /api/reports/{id}/preview/`; `POST /api/reports/{id}/exports/`;
    `POST /api/reports/{id}/scheduled-dry-run/`; `GET /api/reports/{id}/diagnostics/`.
  - Change: Tightened `report.v1` export readiness. Report preview still renders available
    stored aggregate data, but dataset coverage statuses `missing_history`,
    `not_previously_synced`, `permission_missing`, and `unsupported_metric` now add
    `blocking_reasons` and set `export_ready=false`. Manual exports return `409` before queueing,
    and scheduled dry-runs create sanitized `blocked_by_coverage` evidence instead of rendering an
    artifact when those hard-blocking states are present.
  - Impact: The frontend must treat missing required stored history as blocked, not merely
    warning-ready. This prevents SLB/DashThis evidence from exporting reports where organic Page,
    top-post, or Content Ops sections have no retained aggregate rows. Stale, partial, and
    source-disconnected retained data can still render with visible coverage notes.
  - Owner: Sofia (Backend API) + Andre (coverage semantics) + Lina/Joel (frontend readiness UI)
    - Omar/Hannah (support/evidence) + Raj/Mira review

- **2026-06-16**
  - Endpoint: management command `slb_report_history_probe`.
  - Change: Added a backend-only retained-history probe for SLB reporting evidence. The command
    renders report preview/diagnostics from stored aggregate data for both a primary monthly range
    and a retained 90-day range, then emits a redacted `slb_history_probe.v1` dataset matrix for
    `paid_meta_ads`, `organic_facebook_page`, and `content_ops`.
  - Impact: Operators can collect G2/G3 monthly and 90-day coverage states consistently before
    copying values into evidence packets. The command does not call live providers, does not expose
    raw rows/tokens, and does not change API responses. G2/G3 still require fixed G1 runtime proof
    and reviewer approval.
  - Owner: Sofia (Backend API) + Andre (coverage semantics) + Omar/Hannah (support/evidence)
    - Raj/Mira review

- **2026-06-16**
  - Endpoint: management command `slb_report_target_intake`.
  - Change: Added a backend-only G1 intake helper for candidate SLB reports. The command validates
    the governed report layout and emits a redacted `slb_target_intake.v1` summary with report
    schema/template identifiers, date-range fields, required dataset/page checks, scope-presence
    booleans, delivery recipient count, schedule flags, validation errors, and operator fields still
    required.
  - Impact: Operators can verify a candidate `ReportDefinition.id` is a valid SLB `report.v1`
    target before collecting G2-G11 evidence. The command does not call live providers, does not
    expose delivery emails/tokens/raw provider payloads, and does not change API responses. G1 still
    requires human confirmation of environment, safe tenant/client, source scopes, DashThis status,
    and Raj/Mira route.
  - Owner: Sofia (Backend API) + Hannah (evidence intake) + Raj/Mira review

- **2026-06-16**
  - Endpoint: management command `slb_report_evidence_validate`.
  - Change: Added a backend-only offline validator for SLB cancellation-readiness evidence
    artifacts. The command reads an evidence bundle and optional parity comparison JSON, then
    reports blockers/warnings for date-range mismatch, missing datasets, blocking coverage states,
    missing report pages, missing or empty CSV/PDF/PNG export summaries, preview/snapshot hash drift,
    missing scheduled dry-run proof, unresolved parity rows, Instagram leakage, and high-signal
    sensitive payload patterns.
  - Impact: Operators and reviewers can run a repeatable pre-G10/pre-G11 artifact check before
    adversarial review or hardening. The command is file-based, does not query providers, does not
    create export jobs, and does not change API responses.
  - Owner: Sofia (Backend API) + Omar/Hannah (evidence/support) + Nina (safety) + Raj/Mira review

- **2026-06-16**
  - Endpoint: management command `slb_report_parity_compare`.
  - Change: Added a backend-only parity comparison command that merges `slb_evidence_bundle.v1`
    parity rows with a redacted comparison-values JSON file, then computes absolute deltas,
    percentage deltas, pass/fail outcomes, and blocked states from approved percent or absolute
    tolerances.
  - Impact: Operators can calculate the G6 worksheet consistently after DashThis/source values are
    provided. The command is file-based, does not call live providers, does not create export jobs,
    and does not change API responses. G6 still requires real comparison values, reviewer-approved
    tolerances, explanations, and sign-off before cancellation review.
  - Owner: Sofia (Backend API) + Andre (metric semantics/tolerances) + Raj review

- **2026-06-16**
  - Endpoint: management command `slb_report_evidence_bundle`.
  - Change: Added a backend-only fixed-range evidence bundle command for SLB cancellation-readiness
    collection. The command emits a redacted `slb_evidence_bundle.v1` JSON payload containing report
    metadata, custom date range, preview hash, coverage summary, diagnostics for the same range,
    rendering page/widget summary, export status/hash/artifact-size summary, and parity rows.
  - Impact: Operators can collect G2-G9 implementation/runtime evidence from one stored-data path
    before filling screenshots, downloaded artifacts, DashThis/source values, and reviewer notes.
    The command does not create export jobs, send email, call live providers, or change API
    responses.
  - Owner: Sofia (Backend API) + Andre (metric semantics) + Omar/Hannah (evidence/support)
    - Raj/Mira review

- **2026-06-16**
  - Endpoint: `GET /api/reports/{id}/diagnostics/`; `POST /api/reports/{id}/preview/`.
  - Change: Report coverage summaries now preserve the latest safe `last_successful_sync_at`
    timestamp from widget coverage, and diagnostics expose that timestamp per dataset when stored
    snapshot coverage provides it.
  - Impact: Support diagnostics can explain when stored aggregate data was last successfully synced
    instead of always returning `null` for dataset sync recency. No live provider calls are added;
    the timestamp comes from stored snapshot/coverage metadata.
  - Owner: Sofia (Backend API) + Omar/Hannah (diagnostics/support) + Andre (coverage semantics)
    - Raj/Mira review

- **2026-06-16**
  - Endpoint: management command `slb_report_parity_evidence`.
  - Change: Aligned seeded parity worksheet rows with the G6 allowed result values. Rows without
    DashThis/source comparison values now use `result="blocked_missing_dashthis_value"` instead of
    the ad hoc `pending_dashthis_value`, and markdown output uses the same result. Regression
    coverage also verifies manually authored report sections do not appear as parity rows.
  - Impact: The ADinsights-side worksheet seed can be pasted into the G6 parity packet without
    introducing a non-governed result state. G6 still cannot pass until DashThis/source values,
    deltas, tolerances, explanations, and reviewer approvals are filled.
  - Owner: Sofia (Backend API) + Andre (metric semantics) + Raj review

- **2026-06-16**
  - Endpoint: `POST /api/reports/{id}/preview/`; `GET /api/reports/{id}/diagnostics/`;
    `POST /api/reports/{id}/exports/`; `POST /api/reports/{id}/scheduled-dry-run/`.
  - Change: Corrected `report.v1` coverage rollups so manually authored `report_section`
    widgets do not contribute to `coverage_summary.datasets`, retained-history row counts, or
    diagnostics dataset retained ranges. Coverage payloads with `row_count == 0` now report
    `covered_start_date=null` and `covered_end_date=null` even when a widget can display a zero
    value for the requested end date.
  - Impact: Report coverage and diagnostics no longer overstate stored Content Ops history because
    of cover/recommendation/appendix narrative sections or zero-count placeholders. Frontend clients
    should continue to render widget-level report section notes, while dataset-level coverage should
    be treated as data-widget evidence only.
  - Owner: Sofia (Backend API) + Andre (coverage semantics) + Omar/Hannah (diagnostics/support)
    - Raj/Mira review

- **2026-06-16**
  - Endpoint: `POST /api/reports/{id}/preview/`; `POST /api/reports/{id}/exports/`;
    `GET /api/reports/{id}/diagnostics/`; `POST /api/reports/{id}/scheduled-dry-run/`;
    `POST/PATCH /api/reports/`; management command `slb_report_parity_evidence`.
  - Change: Added governed `report.v1` layout validation for report definitions, a read-only
    report preview endpoint that renders ordered report pages from stored aggregate widget preview
    data, and report export preflight metadata capture for `report.v1`. Exports now preserve a
    server-computed report preview metadata block with schema/template/catalog identifiers, date
    range, full ordered `report_snapshot`, coverage summary, blocking reasons, export readiness,
    delivery status, and preview hash; blocking coverage returns `409` before queueing a manual
    export. Added diagnostics for support-safe dataset/export-history states, scheduled delivery
    dry-run evidence jobs, report-specific privilege gates, conservative report preview/export/dry-run
    quotas, and a parity evidence command that outputs ADinsights-side aggregate rows with manual
    DashThis comparison columns. Legacy reports without `schema_version` remain accepted.
  - Impact: Frontend report pages can render SLB `report.v1` previews with coverage notes and avoid
    misleading exports when required coverage is missing; support can diagnose stale/missing/partial
    data without reading logs; scheduled report delivery can be proven in dry-run mode before real
    client sends. No live provider calls are introduced at report render/export-preflight time, and
    existing legacy report export behavior remains compatible.
  - Owner: Sofia (Backend API) + Andre (Analytics catalog) + Lina/Joel (Frontend rendering)
    - Omar/Hannah (coverage/support states) + Raj/Mira review

- **2026-06-16**
  - Endpoint: `POST /api/dashboards/widget-preview/`.
  - Change: Added an authenticated, `dashboard_edit`-gated read-only widget preview endpoint for
    `dashboard.v1` configs. The request accepts one governed widget plus optional date/client/account/page
    scope fields, reuses the backend reporting catalog validator, reads only stored ADinsights aggregate
    data, and returns `{widget_id, dataset, type, data, coverage, warnings}`. Coverage states include
    fresh, stale, partial, disconnected-source-with-history, missing history, not previously synced, and
    permission/unsupported blocks. Coverage policies can return `409` when a widget must not render.
  - Impact: Frontend builders can preview governed widgets without hardcoding metric compatibility or
    calling upstream providers at render time. Existing dashboard CRUD, legacy layouts, and audit behavior
    remain unchanged.
  - Owner: Sofia (Backend API) + Lina (Frontend contract) + Andre (Analytics catalog) + Raj/Mira review

- **2026-06-16**
  - Endpoint: `POST /api/reports/slb-monthly-template/`; report export metadata.
  - Change: Added a tenant-scoped SLB monthly report template creation action that creates a `report.v1`
    layout using active v1 datasets `paid_meta_ads`, `organic_facebook_page`, and `content_ops`; Instagram
    remains deferred. Generic report export job metadata now preserves report schema version, template key,
    catalog schema version, generation timestamp, and any report coverage metadata stored on the layout.
  - Impact: ADinsights can create an SLB-style monthly report scaffold from the governed reporting schema
    and retain contract/coverage metadata on generated export jobs. Existing generic CSV/PDF/PNG artifact
    generation and download safety behavior are unchanged.
  - Owner: Sofia (Backend API) + Lina (Frontend contract) + Andre (Analytics catalog) + Raj/Mira review

- **2026-06-15**
  - Endpoint: `GET /api/dashboards/reporting-catalog/`.
  - Change: Added an authenticated read-only reporting catalog endpoint backed by the backend
    registry. The response exposes `reporting_catalog.v1` metadata for `dashboard.v1` builders,
    including datasets, metrics, dimensions, widget types, coverage policies/statuses, and
    compatibility rules such as required table row limits, line-chart time dimensions, map geography
    dimensions, future-gated datasets/widgets, relative date ranges, and deprecated Page metrics.
  - Impact: Frontend dashboard/report builders can fetch governed reporting options from the
    backend instead of hardcoding dataset, metric, dimension, widget, and compatibility lists.
    Existing dashboard CRUD and legacy saved layouts are unchanged.
  - Owner: Sofia (Backend API) + Lina (Frontend contract) + Andre (Analytics catalog) + Raj review

- **2026-06-15**
  - Endpoint: `POST/PATCH /api/dashboards/definitions/`.
  - Change: Added backend reporting catalog validation for saved dashboard layouts with
    `layout.schema_version="dashboard.v1"`. The validator now rejects unknown/future-gated
    datasets, dataset-incompatible metrics or dimensions, invalid widget types, table widgets
    without row limits, source-comparison widgets without source labels, deprecated or unknown
    Page metrics, invalid coverage policies, unbounded date ranges, and malformed slot/widget
    references.
  - Impact: Legacy saved dashboard layouts without `schema_version` remain accepted, and existing
    `template_key`/`default_metric` behavior is unchanged. New `dashboard.v1` clients must follow
    `docs/project/reporting-builder-catalog-contract.md` before persisted dashboard configs save.
  - Owner: Sofia (Backend API) + Lina (Frontend contract) + Andre (Analytics catalog) + Raj review

- **2026-06-10**
  - Endpoint: Content Ops Instagram publisher boundary,
    `content_ops.instagram_graph.InstagramGraphPublisher`.
  - Change: Added a disabled-by-default Instagram Graph adapter behind
    `CONTENT_OPS_META_INSTAGRAM_BETA`. When enabled, the adapter resolves the tenant-local selected
    `MetaPage` through the Instagram publishing identity, decrypts the active Meta connection token
    or Page token inside the provider boundary, creates media containers through
    `/{ig-user-id}/media`, polls container status through `/{container-id}`, and publishes with
    `/{ig-user-id}/media_publish`.
  - Impact: Existing API payloads and default runtime behavior remain fail-closed with
    `provider_not_configured`. No OAuth scopes are activated and no live Instagram publishing occurs
    unless the beta flag is explicitly enabled in a gated environment. Frontend clients continue to
    consume existing publish-attempt container states, retry states, and safe failure fields.
  - Owner: Sofia (Backend API) + Maya (Meta integration) + Leo (Scheduler/retry) + Nina (Security)
    - Raj/Mira review

- **2026-06-10**
  - Endpoint: Content Ops Facebook Page publisher boundary,
    `content_ops.facebook_graph.FacebookGraphPagePublisher`.
  - Change: Added a disabled-by-default live Facebook Page Graph adapter behind
    `CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING`. When enabled, the adapter resolves the selected
    tenant-local `MetaPage`, decrypts the stored Page token inside the provider boundary, and posts
    approved caption text to the configured Graph API Page feed endpoint. Provider failures are
    mapped to safe retryable or terminal Content Ops failure codes before persistence.
  - Impact: Existing API payloads and default runtime behavior remain fail-closed with
    `provider_not_configured`. No OAuth scopes are activated and no live Graph publishing occurs
    unless the new flag is explicitly enabled in a gated environment. Frontend clients continue to
    consume the existing publish-attempt states and safe failure fields.
  - Owner: Sofia (Backend API) + Maya (Meta integration) + Nina (Security) + Raj/Mira review

- **2026-06-10**
  - Endpoint: `GET /api/content-ops/public-media/{asset_id}/`,
    `GET /api/content-ops/assets/{asset_id}/public-media-proof/`.
  - Change: Added an opaque public media fetch path for Meta/CDN access and an authenticated,
    redacted public-media proof action. The public fetch path serves only available assets attached
    to the active version of a client-approved or later draft. The proof action reports HTTPS
    readiness, safe failure code, redacted URL, host, MIME type, content length, and
    `storage_key_exposed=false`.
  - Impact: Instagram publishing can use a Meta-fetchable HTTPS asset URL without exposing
    tenant-private `storage_key` values or local paths. `CONTENT_OPS_PUBLIC_MEDIA_BASE_URL` must be
    configured to the deployed HTTPS app/CDN route before live Instagram adapter work. No OAuth
    scope, Graph publishing call, token decryption, or live provider adapter behavior changed.
  - Owner: Sofia (Backend API) + Nina (Security) + Maya (Meta integration) + Hannah evidence review

- **2026-06-10**
  - Endpoint: `POST /api/content-ops/published-posts/{post_id}/refresh-metrics/`; task contract
    for `content_ops.tasks.refresh_content_published_post_metrics`.
  - Change: Replaced the inert `501 not_implemented` metric-refresh action with a backend refresh
    path that bridges already-synced Meta post insight rows into aggregate-only
    `OrganicPostMetricSnapshot` records. Added an hourly `content-organic-metrics-refresh` beat
    entry on the sync queue for tenant-scoped published-post refresh scans.
  - Impact: Publish-capable clients can trigger a per-post refresh and receive `200 refreshed` with
    `snapshot_id` when provider rows exist, or `409 organic_metrics_unavailable` when no aggregate
    provider data is available. The worker updates `reporting_link_state` and
    `last_metrics_refresh_at`. No user-level insight identifiers, live Meta Graph publishing, OAuth
    scope, Graph-version, dbt mart, or frontend behavior changed.
  - Owner: Sofia (Backend Metrics/API) + Omar (Observability/Evals) + Nina (Security) + Raj review

- **2026-06-10**
  - Endpoint: `POST /api/content-ops/exports/`, `GET /api/content-ops/exports/{export_id}/`,
    `GET /api/content-ops/exports/{export_id}/download/`.
  - Change: Added persisted Content Ops content-plan export artifacts. Export creation writes a
    client-safe JSON packet under the configured report artifact root, returns server-safe export
    metadata plus `download_url`, and keeps the storage `artifact_path` out of public payloads.
    Download validates the stored path remains under the export root before serving the packet.
  - Impact: Frontend clients can list, retrieve, and redownload prior content-plan packets without
    retaining private storage keys, provider prompts, or AI lineage. Existing
    `POST /api/content-ops/exports/content-plan/` remains available for immediate client-safe
    JSON snapshots. No live Meta Graph publishing, OAuth scope, metric refresh, dbt mart, or
    frontend export-history behavior changed.
  - Owner: Sofia (Backend Metrics/API) + Nina (Security) + Lina (Frontend contract) + Raj review

- **2026-06-10**
  - Endpoint: `/api/content-ops/*` OpenAPI contract.
  - Change: Added OpenAPI regression coverage for Content Ops routes, custom action request
    serializers, schedule `channels`, public serializer state enums, credential/storage
    write-only fields, and read-only workflow/runtime fields. Updated Content Ops viewsets so
    custom actions such as schedule, draft versions, approval submission/decisions, and caption
    generation expose action-specific serializers in the generated schema.
  - Impact: Frontend clients have a pinned schema surface for path availability and state-bearing
    enums before deeper live integration. Remaining schema work is limited to richer custom
    response payloads for readiness/reporting/export actions and deeper write-contract examples.
    Runtime behavior is unchanged except that the schedule serializer now explicitly documents the
    write-only `channels` list accepted by the schedule action.
  - Owner: Sofia (Backend Metrics/API) + Lina (Frontend contract) + Raj review

- **2026-06-10**
  - Endpoint: `POST /api/content-ops/drafts/{draft_id}/schedule/`; task contract for
    `content_ops.tasks.dispatch_due_content_schedules`.
  - Change: Schedule creation now freezes publish destinations into
    `approval_snapshot.target_channels`. Requests can provide `channels` as strings or target
    objects with `type`, `page_id`, or `ig_user_id`; omitted `channels` snapshot the current
    workspace target channels. Due-schedule dispatch now uses the frozen targets and narrows
    publishing identity selection by snapshotted `page_id` or `ig_user_id` when present.
  - Impact: Frontend clients can present schedule-level destination choice without relying on
    mutable workspace defaults. Existing schedules without `approval_snapshot.target_channels`
    retain compatibility by falling back to workspace channels. No live Meta Graph publishing,
    token decryption, queued-attempt processor scan, Instagram container creation, metric refresh,
    dbt mart, or OAuth scope behavior changed.
  - Owner: Sofia (Backend Metrics/API) + Leo (Scheduler) + Lina (Frontend contract) + Raj review

- **2026-06-10**
  - Endpoint: `PATCH /api/content-ops/assets/{asset_id}/`, `GET /api/content-ops/readiness/`.
  - Change: Public asset updates now ignore server-owned storage/runtime metadata, including
    `source`, `storage_key`, `mime_type`, dimensions, `renditions`, and `status`. Publishing
    readiness now requires selected publishing identities to be explicitly `ready`; `unknown`
    identity readiness blocks the Facebook Page or Instagram publishing axis with
    `publishing_identity_blocked`.
  - Impact: Frontend clients must treat asset storage metadata and publishing identity readiness as
    server-owned. Publishing controls should remain disabled until identity validation has produced
    an explicit ready state. No live Meta Graph publishing, token decryption, queued-attempt
    processor scan, Instagram container creation, metric refresh, dbt mart, or OAuth scope behavior
    changed.
  - Owner: Nina (Security) + Sofia (Backend Metrics/API) + Raj review

- **2026-06-10**
  - Endpoint: task contracts for `content_ops.tasks.dispatch_due_content_schedules` and `content_ops.tasks.requeue_due_content_publish_attempts`.
  - Change: Added explicit Celery sync-queue routes and beat entries for Content Ops due schedule dispatch and retry requeue scans. Both scans run every minute on the `sync` queue and continue to use existing tenant-scoped, idempotent task behavior.
  - Impact: Operators can expect due schedules and due retryable attempts to be scanned automatically by Celery beat. This does not add live Meta Graph publishing, token decryption, an automatic queued-attempt processor, Instagram container creation, metric refresh, dbt marts, or API payload changes.
  - Owner: Leo (Scheduler) + Sofia (Backend Metrics/API) + Raj review

- **2026-06-09**
  - Endpoint: `POST /api/content-ops/approval-requests/{approval_id}/decisions/`, `GET/POST/PATCH /api/content-ops/generation-jobs/`, `GET/POST/PATCH /api/content-ops/assets/`, `POST /api/content-ops/assets/upload/`, `GET /api/content-ops/assets/{asset_id}/download/`, `GET/POST/PATCH /api/content-ops/publishing-identities/`; task contracts for `content_ops.tasks.process_content_caption_generation_job`, `dispatch_due_content_schedules`, `process_content_publish_attempt`, and `requeue_due_content_publish_attempts`.
  - Change: Hardened Content Ops API and task contracts. Approval decisions now reject non-pending requests, stale non-active versions, and drafts outside the expected review state before persisting a decision. Caption-generation task execution now resolves tenant context from the `GenerationJob` instead of treating the job UUID as a tenant identifier. Public serializers no longer return publishing credential references or media `storage_key`/`ai_lineage`; publishing readiness fields and generation runtime result fields are server-owned/read-only. Public asset creation now requires `POST /assets/upload/`, stores image/video uploads under a generated tenant/workspace storage key, and serves available assets through an authenticated download action. Content Ops Celery tasks now allow five retries; scheduler/publisher row locks skip locked rows; retryable publisher failures use jittered exponential retry delays and become terminal after the fifth failed attempt.
  - Impact: Frontend clients must not depend on mutating generation runtime fields, publishing readiness fields, asset status, or reading credential/storage internals from public Content Ops payloads. Operators can expect bounded retry attempts and non-blocking queue scans. Existing workflow actions remain the supported path for approvals, generation, scheduling, and publishing queue operations. No live Meta Graph call, AI provider activation, externally signed URL service, dbt mart, or metric refresh behavior changed at that time; due/retry beat scans were activated in a later 2026-06-10 entry.
  - Owner: Sofia (Backend Metrics/API) + Nina (Security) + Lina (Frontend contract) + Raj review

- **2026-06-06**
  - Endpoint: `POST /api/content-ops/briefs/{brief_id}/captions/generate/`.
  - Change: Added tenant-scoped caption-generation quota guardrails. Requests are blocked before job creation when active caption jobs, rolling 24-hour caption jobs, or rolling 24-hour requested candidates exceed configured limits. Quota blocks return safe `400` payloads with `reason` values `caption_active_limit_exceeded`, `caption_daily_limit_exceeded`, or `caption_candidate_limit_exceeded` plus numeric quota counters/limits.
  - Impact: Frontend clients can display actionable quota blockers and retry later without creating hidden queued jobs. No live AI provider, billing integration, graphics, scheduling, publishing, metric refresh, or Celery beat behavior is active.
  - Owner: Nina (Security) + Sofia (Backend Metrics/API) + Omar (Observability/Evals) + Raj review

- **2026-06-06**
  - Endpoint: `POST /api/content-ops/briefs/{brief_id}/captions/generate/`; task contract for `content_ops.tasks.process_content_caption_generation_job`.
  - Change: Added a tenant-scoped caption-generation request endpoint that creates queued `GenerationJob` records with capped `candidate_count`, supported `facebook_page`/`instagram` platforms, redacted prompt summary, and safe prompt policy metadata. Added a fakeable caption processor that validates provider candidate schema, enforces blocked/required terms, fails closed by default with `provider_not_configured`, and creates editable `generated` drafts plus active versions linked to `source_generation_job` only when injected provider output is valid.
  - Impact: Future frontend clients can request caption generation jobs and poll existing generation-job endpoints. No live OpenAI/API provider call, AI graphic generation, approval, schedule, publish attempt, published post, metric refresh, Celery beat activation, frontend client, or dbt behavior is active.
  - Owner: Sofia (Backend Metrics/API) + Nina (Security) + Omar (Observability/Evals) + Lina (Frontend contract) + Raj/Mira review

- **2026-06-06**
  - Endpoint: `GET /api/content-ops/publishing/attempts/?state=&channel=&scheduled_from=&scheduled_to=&retry_due=`; task contract for `content_ops.tasks.requeue_due_content_publish_attempts`.
  - Change: Added schedule-window and retry-due filters to the publish-attempt list endpoint. Added due-retry requeue scanner/task that moves tenant-scoped `failed_retryable` attempts back to `queued` when `next_retry_at` has arrived.
  - Impact: Operators and future queue UI can find due retryable attempts without scanning client-side, and workers can requeue due retry attempts without calling Meta. No beat cadence, processor scan, live Graph adapter, token decryption, Instagram container flow, or metric refresh is active.
  - Owner: Leo (Scheduler) + Sofia (Backend Metrics/API) + Lina (Frontend contract) + Raj/Mira review

- **2026-06-06**
  - Endpoint: `POST /api/content-ops/publishing/attempts/{attempt_id}/retry/`; task contract for `content_ops.tasks.process_content_publish_attempt`.
  - Change: Publish-attempt retry now requeues only `failed_retryable` attempts, clears safe failure/retry fields, and returns the refreshed attempt payload. Added a single-attempt Celery task wrapper around the disabled-by-default Facebook Page processor.
  - Impact: Publish-capable users can safely requeue retryable attempts without calling Meta immediately. Workers have a task boundary for one-attempt processing, but no beat cadence, retry worker, live Graph adapter, token decryption, Instagram container flow, or metric refresh is active.
  - Owner: Leo (Scheduler) + Maya (Integrations) + Sofia (Backend Metrics/API) + Raj/Mira review

- **2026-06-05**
  - Endpoint: none; service contract for `content_ops.publisher.process_facebook_page_publish_attempt`.
  - Change: Added fakeable Facebook Page publish-attempt processor and disabled-by-default publisher boundary. Injected publisher success creates `PublishedPost`, marks attempts `published`, persists returned post IDs, and refreshes schedule/draft state. Provider failures are classified as retryable or terminal with sanitized failure details.
  - Impact: Future worker wiring can exercise the Page publishing state machine without live Meta calls. No public endpoint, token decryption, live Graph provider adapter, Celery beat cadence, Instagram container flow, or metric refresh behavior is live.
  - Owner: Maya (Integrations) + Leo (Scheduler) + Sofia (Backend Metrics/API) + Nina (Security) + Raj/Mira review

- **2026-06-05**
  - Endpoint: none; service contract for `content_ops.publisher.preflight_facebook_page_attempt`.
  - Change: Added Facebook Page publish preflight contract that validates tenant ownership, supported channel, publishable state, active scheduled version, client approval snapshot, publishing identity readiness, Facebook Page publishing readiness, and caption content before any provider handoff.
  - Impact: Future publisher workers can block unsafe attempts with stable client-safe failure codes before calling Meta. No public endpoint, token decryption, Graph publish call, attempt mutation, Instagram container flow, Celery beat cadence, or metric refresh behavior is live.
  - Owner: Maya (Integrations) + Sofia (Backend Metrics/API) + Nina (Security) + Raj/Mira review

- **2026-06-05**
  - Endpoint: none; operational task contract for `content_ops.tasks.dispatch_due_content_schedules`.
  - Change: Added app-owned due-schedule dispatcher that scans scheduled drafts and creates idempotent per-channel `PublishAttempt` rows after validating tenant scope, active draft version, client approval snapshot, selected publishing identity, and separated publishing readiness.
  - Impact: Scheduler/runtime workers can safely queue Facebook Page or Instagram publish attempts without calling Meta. No public endpoint, Celery beat cadence, Graph publishing call, Instagram container flow, or metric refresh behavior is live yet.
  - Owner: Leo (Scheduler) + Sofia (Backend Metrics/API) + Maya (Integrations) + Raj/Mira review

- **2026-06-05**
  - Endpoint: `GET /api/content-ops/reports/overview/`, `GET /api/content-ops/reports/posts/`, `POST /api/content-ops/exports/content-plan/`.
  - Change: Added aggregate-only Content Ops overview/post reporting over stored published-post metric snapshots, plus client-safe JSON content-plan export for workspace drafts/versions/approvals/schedules.
  - Impact: Frontend clients can render basic organic content reporting and approval/export packets before live publishing is enabled. Reports do not fetch Meta and expose aggregate metrics only; content-plan exports omit private storage keys, raw prompts, and AI lineage.
  - Owner: Sofia (Backend Metrics/API) + Lina (Frontend) + Raj review

- **2026-06-05**
  - Endpoint: `/api/content-ops/drafts/{id}/`, `/api/content-ops/versions/`, `/api/content-ops/approval-requests/`, `/api/content-ops/schedules/`.
  - Change: Hardened workflow bypasses by making draft `state` read-only and keeping draft-version, approval-request, and schedule collection endpoints read-only. Version creation, approval submission, and scheduling must go through the draft workflow actions.
  - Impact: Clients cannot directly force approval/schedule states or create workflow records without the action-level role, audit, approval-snapshot, and state-transition logic. Existing read surfaces remain available.
  - Owner: Sofia (Backend Metrics/API) + Nina (Security) + Raj review

- **2026-06-05**
  - Endpoint: `GET /api/content-ops/readiness/` and role-gated mutations on existing `/api/content-ops/*` workflow endpoints.
  - Change: Added separated Content Operations readiness axes for Meta auth, Page selection, Instagram linkage, Facebook Page publishing, Instagram publishing, and reporting readiness. Added module-local role gates for read, edit, internal approval, client approval, publishing actions, and publishing identity mutation.
  - Impact: Frontend clients can render independent blockers without changing `/api/integrations/social/status/` or `/api/datasets/status/`. Non-publish roles now receive `403` on schedule/publish/retry-style Content Ops actions.
  - Owner: Sofia (Backend Metrics/API) + Nina (Security) + Maya (Integrations) + Raj/Mira review

- **2026-06-05**
  - Endpoint: additive `/api/content-ops/*` backend skeleton including workspaces, publishing identities, briefs, generation jobs, assets, drafts, versions, approval requests/decisions, schedules, publish attempts, published posts, and metric snapshots.
  - Change: Added tenant-scoped serializers/viewsets/routes plus draft version, internal/client approval, decision, schedule, unschedule, generation-job cancel, and explicit inert publish/retry/metric-refresh actions. `publish-now`, publish-attempt `retry`, and published-post `refresh-metrics` return `501` with `reason: "not_implemented"` until their runtime tickets ship.
  - Impact: Backend clients can begin integrating Content Operations CRUD/workflow skeletons. No Meta OAuth, Meta Graph publishing, Instagram container, scheduler, AI provider, frontend, dbt, or reporting-readiness behavior changed.
  - Owner: Sofia (Backend Metrics/API) + Raj/Mira/Sofia/Hannah review

- **2026-06-05**
  - Endpoint: proposal only, future additive `/api/content-ops/*` surfaces documented in `docs/project/content-operations-api-contract.md`.
  - Change: Added a planned API contract doc plus eval/runbook/evidence documentation for Content Operations. No runtime endpoint, serializer, frontend client, scheduler task, Meta/OAuth behavior, AI provider call, or dbt model changed in this docs pack.
  - Impact: Future backend tickets must treat the documented endpoint shapes/enums as the planning baseline and update this changelog when serializers/viewsets become live.
  - Owner: Raj (Cross-Stream Integration) + Sofia (Backend Metrics/API) + Lina (Frontend)

- **2026-06-05**
  - Endpoint: none; backend data foundation only for future `/api/content-ops/*`.
  - Change: Added the `content_ops` Django app and initial tenant-scoped model/migration foundation for Content Operations records. No DRF endpoint, serializer, frontend contract, Meta call, scheduler task, AI provider call, or runtime OAuth scope changed.
  - Impact: Future API work can build on durable backend tables, but clients cannot call Content Operations APIs yet. Treat later serializers/viewsets as additive contract work and update this changelog again when endpoints ship.
  - Owner: Sofia (Backend Metrics/API) + Raj/Mira review

- **2026-06-05**
  - Endpoint: proposal only, future additive `/api/content-ops/*` surface for Meta/Facebook/Instagram organic content operations.
  - Change: Added `docs/project/content-operations-meta-publishing-spec.md` with proposed contracts for readiness, workspaces, briefs, AI generation jobs, drafts, approvals, scheduling, publish attempts, exports, and aggregate organic post reporting. No runtime endpoint or serializer changed in this docs slice.
  - Impact: Future backend/frontend implementation must treat the proposed surface as contract-sensitive, keep Meta auth/Page selection/Instagram linkage/publishing readiness/reporting readiness separate, and update this changelog again when real endpoints ship.
  - Owner: Raj (Cross-Stream Integration) + Sofia (Backend Metrics/API) + Lina (Frontend) + Maya/Leo (Integrations/Scheduler)

- **2026-06-05**
  - Endpoints: error paths of `/api/clients/` (create + attach-account), `/api/analytics/web/*`, the AI summary refresh endpoint, and the GA4 OAuth callback (`/api/integrations/google_analytics/oauth/*`).
  - Change: on broad/unexpected failures these endpoints no longer return raw exception text. The `clients` 409 drops its `error` key (DB constraint text); web analytics returns `"detail": "Query failed."`; summary refresh returns `"Failed to refresh summary."`; GA4 token-exchange/userinfo/property-discovery return generic details (`"Token exchange failed."`, etc.). Full exceptions are logged server-side. Controlled config/validation messages (e.g. `"... must be configured"`) are unchanged.
  - Impact: clients relying on the raw exception string in these error bodies will now see a generic message; status codes unchanged; the `clients` 409 `error` field is removed.
  - Owner: Backend Integrations (CodeQL stack-trace-exposure remediation)

- **2026-06-05**
  - Endpoints: integration endpoints that surface Airbyte errors (e.g. `POST /api/integrations/{provider}/provision/`, `.../sync/`, and Google Ads provision/sync paths) via `_airbyte_exception_response`.
  - Change: the `detail` returned on Airbyte upstream errors is now length-bounded to 1000 chars (`client_safe_detail`); the full, untruncated error is logged server-side. Short, actionable config/validation messages are unchanged.
  - Impact: clients no longer receive arbitrarily large raw upstream Airbyte response bodies; oversized details are truncated with a `… (truncated)` suffix. No change to status codes or to short error messages.
  - Owner: Backend Integrations (defense-in-depth for CodeQL stack-trace-exposure)

- **2026-05-28**
  - Endpoint: `GET /api/health/version/`, `GET /api/schema/`
  - Change: Wired the configured public DRF throttle to lightweight version and public schema endpoints, and added `backend_release_smoke --check-rate-limits` to prove configured auth/public `429` behavior.
  - Impact: Public callers may receive `429` on these endpoints when `DRF_THROTTLE_PUBLIC` is exceeded; release evidence now has a repeatable local/staging command.
  - Owner: Sofia (Backend Metrics) + Nina (Security)

- **2026-05-27**
  - Endpoints: `GET /api/exports/{job_id}/download/`,
    `GET /api/analytics/google-ads/exports/{job_id}/download/`,
    `POST/GET/PATCH /api/notification-channels/`
  - Change: Post-implementation audit hardening now rejects report artifact paths that resolve
    outside the configured export tree, rejects empty generic artifacts, neutralizes
    formula-leading text values in generated generic and Google Ads CSV downloads, and sanitizes
    export scheduling failures. Notification-channel model saves now extract Slack/webhook
    secret keys into encrypted storage even when serializer validation is bypassed; serialization
    strips any residual secret keys from legacy ordinary configuration.
  - Impact: Existing valid download and notification-channel requests remain compatible. Unsafe
    stored paths return an error rather than serving files, and spreadsheet consumers see
    formula-leading data as safe literal text. Scheduled daily-summary delivery also suppresses
    duplicate sends for a previously delivered snapshot without adding a public API contract.
  - Owner: Sofia (Backend Metrics) + Nina (Security) + Lina (Frontend) + Raj/Mira review

- **2026-05-26**
  - Endpoints: `POST/GET/PATCH /api/notification-channels/`, `POST /api/reports/{id}/exports/`,
    `GET /api/exports/{job_id}/download/`
  - Change: Slack/webhook notification destinations are accepted through write-only
    `secret_config` input, encrypted with the tenant DEK/KMS pattern, and no longer returned
    inside `config`; responses add safe `credentials_configured` and `masked_destination`
    fields. Legacy request bodies containing `config.url`, `config.webhook_url`, or
    `config.headers` remain accepted but those keys are removed from response/storage plaintext.
    Generic report export jobs now write and verify tenant-scoped aggregate CSV/PDF/PNG artifacts
    before returning `completed`, with sanitized failures otherwise. Completed export artifacts
    are downloadable from the existing endpoint.
  - Impact: Frontend/clients should submit Slack/webhook secrets through `secret_config` and use
    safe status fields when rendering a channel. Clients may rely on completed generic export
    jobs being backed by a non-empty downloadable artifact. Existing email-channel `config.emails`
    behavior remains compatible.
  - Owner: Sofia (Backend Metrics) + Nina (Security) + Lina (Frontend) + Raj/Mira review

- **2026-05-01**
  - Endpoint: `GET /api/alerts/runs/`
  - Change: Alert run metadata now resolves `tenant_alert:<uuid>` slugs generated from DB-backed `AlertRuleDefinition` rows. Responses remain additive/shape-compatible: existing fields are unchanged, while `rule_name`, `rule_description`, and `severity` are populated for DB-defined alert runs instead of returning `null`.
  - Impact: Frontend alert history can show user-defined alert names/severity for real evaluation runs. Existing hardcoded alert run slugs and clients that tolerate nullable metadata are unaffected.
  - Owner: Sofia (Backend Metrics) + Raj (Integrations review)

- **2026-04-13** (Sprint 10 of Client grouping — FX refresh task, warehouse scoping, suggestion snapshot surface)
  - Endpoints added:
    - `GET /api/clients/suggestions/latest/` — returns `{snapshot: <ClientSuggestionSnapshot> | null}` where the snapshot has `{id, trigger_reason, threshold, suggestion_count, payload, generated_at, acknowledged_at, is_unacknowledged}`. `trigger_reason` ∈ `"meta_sync" | "google_sync" | "manual"`. `payload` is the serialized suggest-clients output captured at snapshot time; `is_unacknowledged=true` when `acknowledged_at IS NULL AND suggestion_count > 0`.
    - `POST /api/clients/suggestions/latest/refresh/` — accepts `{threshold?: float in [0,1]}`, enqueues `integrations.clients.refresh_client_suggestions`, and returns 202 with `{status: "enqueued", threshold}`. 400 when `threshold` is out of range or not a number.
    - `POST /api/clients/suggestions/latest/acknowledge/` — marks the latest snapshot acknowledged (`acknowledged_at = now`) and returns the refreshed snapshot. 404 when no snapshot exists.
  - New Celery task: `integrations.clients.refresh_client_suggestions(tenant_id, *, trigger_reason, threshold)` runs the suggest pipeline and upserts a single `ClientSuggestionSnapshot` per tenant via `OneToOneField`. `acknowledged_at` is preserved only when the new `suggestion_count` and `trigger_reason` match the prior row — any change resurfaces the banner. Wired as a fire-and-forget trigger at the tail of `integrations.tasks._sync_meta_accounts_core` (reason `meta_sync`) and `integrations.tasks.sync_google_ads_sdk_incremental` (reason `google_sync`); dispatch errors are swallowed so sync never fails on suggestion bookkeeping.
  - New Celery task: `integrations.tasks.refresh_fx_rates(base_currency=None, symbols=None, *, manual_rows=None)` — two modes. With `manual_rows` it upserts the provided `[{rate_date, base_currency, quote_currency, rate, source?}]` list into `analytics_dailyfxrate` (malformed rows skipped, return shape `{upserted, skipped, source: "manual"}`). Without it, calls Frankfurter (`https://api.frankfurter.app/latest`, ECB-backed, free, no key) for `USD → (GBP, CAD, JPY, EUR)` by default, persists with `source="ecb"`, and retries with a 300s countdown on `httpx.HTTPError`/`ValueError`.
  - Warehouse adapter: `adapters.warehouse.WarehouseAdapter._apply_filters` now folds `client_scoped_google_customer_ids` + `client_scoped_meta_ad_account_ids` into the `account_ids` filter when `client_scope_requested=True`. When scoping is requested but the resolved account list is empty, the adapter returns an empty-shaped payload (preserves `snapshot_generated_at`, empties `campaign/creative/audience/geo/parish/metrics`) instead of leaking the tenant's unfiltered dataset.
  - Impact: Frontend can now show a "new suggestions" banner (mounted in `DashboardLayout`) that consumes `/api/clients/suggestions/latest/`, and the warehouse adapter honours Client scoping end-to-end. Currency conversion has a live daily feed without an API key.
  - Owner: Raj (Integrations) + Mira (Architecture) + Sofia (Backend Metrics)

- **2026-04-13** (Sprint 6 of Client grouping — Combined view + platform registry + FX layer)
  - Endpoint updated: `GET /api/metrics/combined/` now accepts `client_id=<uuid>` and optional `platforms=<csv>`. Affects the meta_direct adapter path today (warehouse/demo/fake inherit the options mapping transparently; real scoping for warehouse lands with Sprint 10 dbt wiring). The combined serializer gained a `client_id` field.
  - Change: When `client_id` is present, the view resolves the Client's linked Meta ad account external_ids (variant-expanded) and Google customer_ids (MCC-expanded) and injects them into adapter options via the keys `client_scoped_meta_ad_account_ids`, `client_scoped_google_customer_ids`, and the `client_scope_requested=True` sentinel (so an empty-but-requested scope filters to zero rows instead of falling through to the unscoped query). The optional `platforms=meta_ads,google_ads` param toggles which configured platforms contribute — unknown keys are dropped silently for deploy-skew resilience. Responses gain a `client_resolution` block: `{client_id, reason, google_customer_ids, meta_ad_account_ids, mcc_expansions, platforms: {configured, enabled, combined_supported, entries[]}}` where `reason` ∈ `null`, `"client_not_found"`, `"no_platform_accounts_for_client"`, `"no_enabled_platforms"`, `"all_platforms_disabled"`. Responses also set `X-Adinsights-Resolved-Via: client:<id>`. Without `client_id`, responses are byte-for-byte unchanged.
  - New module: `analytics.platform_registry` provides `PlatformRegistry`, `COMBINED_SUPPORTED` (currently `{meta_ads, google_ads}`), and `parse_enabled_param()`. GA4/Search Console/LinkedIn/TikTok are enumerated in the registry order but excluded from `COMBINED_SUPPORTED` until their Phase 2 pilots land.
  - New table: `analytics_dailyfxrate` (migration `analytics/0008_dailyfxrate`) — global (not tenant-scoped) daily FX rates keyed by `(rate_date, base_currency, quote_currency)` with a `source` enum (`manual`, `openexchangerates`, `ecb`, `boj`). Helpers in `analytics.fx`: `resolve_rate()` (on-or-before fallback + inverse-pair flip, no triangulation), `convert()` (returns `None` when unconvertible so callers can warn rather than silently zero), and `load_rate_table()` (batch pre-fetch keyed by `(date, ccy)` to avoid N+1 in adapter loops). Currency normalization will be consumed by combined totals in Sprint 10; the schema ships now so the daily refresh job can start populating history.
  - Impact: Frontend can drive the combined dashboard from a Client selector; `platforms=` enables per-platform toggles for the combined view. No breaking change for clients that continue to call without `client_id`.
  - Owner: Raj (Integrations) + Mira (Architecture) + Sofia (Backend Metrics)

- **2026-04-13** (Sprint 5 of Client grouping — Meta-only view)
  - Endpoints updated: all Meta read endpoints now accept an optional `client_id=<uuid>` query param. Affects: `GET /api/integrations/meta/accounts/` (`meta-accounts`), `GET /api/integrations/meta/campaigns/` (`meta-campaigns`), `GET /api/integrations/meta/adsets/` (`meta-adsets`), `GET /api/integrations/meta/ads/` (`meta-ads`), `GET /api/integrations/meta/insights/` (`meta-insights`), and `GET /api/meta/pages/` (`meta-pages-insights-list`).
  - Change: When `client_id` is present the query is scoped to the Client's Meta ad account external_ids (for the first five) or Meta page_ids (for the pages endpoint). Matching is permissive: `act_123` and `123` are treated as the same id. If both `client_id` and `account_id` are passed, the intersection wins. Responses gain a `client_resolution` object: `{client_id, meta_ad_account_ids | meta_page_ids, reason}` where `reason` ∈ `null`, `"client_not_found"`, `"no_meta_accounts_for_client"`, `"no_meta_pages_for_client"`, `"client_plus_account"`, `"account_not_in_client"`. Responses also set the `X-Adinsights-Resolved-Via: client:<id>` header. Without `client_id`, responses are byte-for-byte unchanged.
  - Impact: Frontend can drive Meta-only dashboards from a selected Client; pairs with Sprint 4 for Google Ads.
  - Owner: Raj (Integrations) + Mira (Architecture)

- **2026-04-13** (Sprint 4 of Client grouping — Google Ads-only view)
  - Endpoints updated: all `GET /api/analytics/google-ads/*` endpoints that currently accept `customer_id`/`campaign_id`/date params now also accept an optional `client_id=<uuid>` query param. Affects: `executive/`, `workspace/summary/`, `campaigns/`, `campaigns/<id>/`, `ad-groups/`, `ads/`, `assets/`, `keywords/`, `search-terms/`, `search-terms/insights/`, `pmax-asset-groups/`, `breakdowns/`, `conversions/by-action/`, `budget/pacing/`, `change-events/`, `recommendations/`, `channels/`.
  - Change: When `client_id` is present the query is scoped to the Client's Google customer_ids (resolved through `integrations.clients.resolver.resolve_client_accounts`, which expands linked MCCs to their non-manager descendants). If both `client_id` and `customer_id` are passed, the intersection wins. Responses gain a `client_resolution` object: `{client_id, google_customer_ids, mcc_expansions, reason}`. `reason` is `null` (normal), `"client_not_found"`, `"no_google_accounts_for_client"`, `"client_plus_customer"`, or `"customer_not_in_client"`. Responses also set the `X-Adinsights-Resolved-Via: client:<id>` header for easy network-tab debugging. When `client_id` is omitted, responses are byte-for-byte unchanged (no `client_resolution` key, no header).
  - Impact: Frontend can drive the Google Ads dashboard from a single selected Client instead of a raw customer_id. Empty states (zero-Google client, stale client) are honest rather than error-y.
  - Owner: Raj (Integrations) + Mira (Architecture)

- **2026-04-13** (Sprint 3 of Client grouping)
  - Endpoints added:
    - `GET /api/clients/` — list tenant's clients with `{id, name, slug, industry, parish, is_active, platform_counts, updated_at}`.
    - `POST /api/clients/` — create client; slug auto-derived from name if omitted.
    - `GET/PATCH/DELETE /api/clients/<uuid:id>/` — retrieve (includes nested `platform_accounts`), update, delete.
    - `GET /api/clients/<uuid:id>/accounts/` — list linked platform accounts.
    - `POST /api/clients/<uuid:id>/accounts/` — attach `{platform, external_id, display_name?, is_primary?}`. Returns 409 with `claimed_by` when the account already belongs to another client.
    - `DELETE /api/clients/<uuid:id>/accounts/<uuid:account_id>/` — detach.
    - `GET /api/clients/suggest/?threshold=0.7` — auto-suggest cross-platform groupings via name-match.
    - `POST /api/clients/suggest/apply/` — atomic: either `client_id` or `create_name` plus an `accounts[]` array; all attachments succeed or none do (pre-flight check returns 409 on any conflict).
  - Change: new `integrations.Client` + `ClientPlatformAccount` data model with one-account-one-client semantics per tenant, enforced by `unique_together(tenant, platform, external_id)`. Platforms supported today: `google_ads`, `meta_ads`, `meta_page`. Platform choices also pre-reserve `ga4`, `search_console`, `linkedin`, `tiktok` for future sprints.
  - Impact: Frontend can build cross-platform client management UI. Google Ads, Meta, and combined dashboards will later accept `?client_id=<id>` to filter by Client (Sprints 4/5/6) — this sprint ships only the CRUD + suggest surface, no downstream consumers yet.
  - Owner: Raj (Integrations) + Mira (Architecture)

- **2026-04-10**
  - Endpoint: `POST /api/airbyte/connections/:id/trigger-sync/`
  - Change: Upgraded from 501 stub to full Airbyte integration. Returns 200 with `{ status, connection_id, job_id }` on success. Returns 501 with descriptive message when Airbyte is not configured, 502 on Airbyte communication failure, and 404 for non-existent connections. Logs audit event with `trigger_source: "trigger-sync"`.
  - Impact: Operators and frontend sync controls can trigger real Airbyte syncs from the UI; consumers should handle 501/502/404 error shapes.
  - Owner: Maya (Integrations) + Omar (SRE)

- **2026-04-10**
  - Endpoint: `GET /api/audit-logs/`
  - Change: Added `start_date` and `end_date` query params (ISO date or datetime format) for date-range filtering. Uses `created_at__date__gte/lte` for date-level filtering. Invalid dates return an empty result set (no 500).
  - Impact: Consumers can scope audit log queries to a date window; existing `?action=` and `?resource_type=` filters unchanged.
  - Owner: Sofia (Backend Metrics)

- **2026-04-10**
  - Endpoint: Frontend Phase 2 polish (no backend contract changes)
  - Change: Added `/me` profile page, alert history/runs view, CSV upload detail page, alert pause/resume controls, report inline editing (name/description), audit log pagination/date-range UI, sync connection detail page at `/ops/sync-health/:connectionId`, health overview auto-refresh (30s interval), global error boundary wrapping app, 404 catch-all page, skeleton loader components for loading states, unified Zustand `useToastStore` notifications, and shared error-state handling across Google Ads pages.
  - Impact: Frontend routes and UX improved across account/profile, alerts, uploads, reporting, operations, and error handling without changing backend payload contracts.
  - Owner: Lina (Frontend)

- **2026-04-09**
  - Endpoint: `POST /api/integrations/{provider}/reconnect/`, `GET /api/integrations/{provider}/jobs/`, `GET /api/integrations/{provider}/status/`, `POST /api/integrations/{provider}/sync/`, `POST /api/integrations/{provider}/disconnect/`, `POST /api/integrations/{provider}/oauth/callback/`, `POST /api/integrations/{provider}/provision/`
  - Change: Recovered the provider-generic connector lifecycle contract for Airbyte-managed Google providers on top of current `main`. The generic lifecycle now supports `ga4` and `search_console` end-to-end and adds the missing reconnect/job surfaces used by shared connector operations. `google_ads` keeps its existing provider-specific setup/status/sync/disconnect payloads on the same concrete paths, while the generic lifecycle adds shared reconnect/job behavior and OAuth callback/provisioning support.
  - Impact: Operators and frontend lifecycle flows can use stable generic connector paths for GA4/Search Console and shared reconnect/jobs workflows without regressing the current Google Ads-specific API contract. Clients should treat `ga4` as the generic Airbyte lifecycle slug and `google_analytics` as the existing dedicated GA4 onboarding/status surface.
  - Owner: Maya (Integrations) + Sofia (Backend Metrics)

- **2026-04-08**
  - Endpoint: `GET /api/audit-logs/`
  - Change: Response is now paginated (`{count, next, previous, results}`). Previously returned a bare array. Supports `?page=N&page_size=N` (default 50, max 200). Filtering by `?action=` and `?resource_type=` unchanged.
  - Impact: Consumers iterating the raw array must unwrap `results`; paginated clients can use `count` and `next`/`previous` for traversal.
  - Owner: Sofia (Backend Metrics)

- **2026-04-07**
  - Endpoints: `GET /api/adapters/`, `GET /api/datasets/status/`, `GET /api/dashboards/recent/`, `GET /api/dashboards/saved/<id>/`, `POST /api/dashboards/`, `PUT /api/dashboards/<id>/`, `DELETE /api/dashboards/<id>/`, Meta Pages and Google Ads integration endpoints
  - Change: Added `meta_direct` adapter to the adapter registry (enabled via `ENABLE_META_DIRECT_ADAPTER`). `GET /api/adapters/` now includes `meta_direct` when enabled, ordered before `demo`/`fake`. Added `GET /api/dashboards/recent/` returning user-scoped saved dashboards with `id`, `name`, `owner`, `last_viewed_at`, `last_viewed_label`, `route` fields (route: `/dashboards/saved/<id>`). Added full saved-dashboard CRUD via `DashboardDefinition` model. dbt models `vw_campaign_daily`, `all_ad_performance`, `dim_campaign`, `fact_performance` updated with additive fields. Added `GET /api/datasets/status/` dataset freshness endpoint. Meta Pages, Google Ads, Google Analytics integration views hardened with explicit error shapes.
  - Impact: Frontend `liveAccountSelection` and Meta Pages dashboard consume `meta_direct` adapter; saved dashboard flows use the new CRUD endpoints; downstream consumers of `vw_campaign_daily` and `dim_campaign` should expect additive columns.
  - Owner: Integration / Dashboard team

- **2026-04-05**
  - Endpoint: `GET /api/metrics/combined/`
  - Change: Combined-metrics responses now preserve an explicit `snapshot_generated_at: null` from non-warehouse adapters instead of rewriting it to request time. Cached snapshot hits also preserve the payload's explicit `null` freshness marker rather than substituting the cache row timestamp.
  - Impact: Frontend can distinguish `no_recent_data` from a genuinely fresh live snapshot and avoids showing empty Meta-direct accounts as "updated just now" after refresh.
  - Owner: Sofia (Backend Metrics) + Lina (Frontend)

- **2026-04-04**
  - Endpoint: `GET /api/datasets/status/`, `GET /api/integrations/social/status/`, `GET /api/integrations/meta/setup/`, `POST /api/integrations/meta/oauth/start/`, `GET /api/integrations/google_ads/setup/`, `POST /api/integrations/google_ads/oauth/start/`, `GET /api/integrations/google_analytics/setup/`, `POST /api/integrations/google_analytics/oauth/start/`
  - Change: Added additive live-reporting readiness contract on `GET /api/datasets/status/` with `live.enabled`, `live.reason` (`adapter_disabled`, `missing_snapshot`, `stale_snapshot`, `default_snapshot`, `ready`), `live.snapshot_generated_at`, `demo.enabled`, and `warehouse_adapter_enabled`. `GET /api/integrations/social/status/` now includes additive Meta `reporting_readiness` fields (`stage`, `message`, `direct_sync_status`, `warehouse_status`, `dataset_live_reason`) and the Instagram row now truthfully reports that Instagram business linking is managed through Meta setup rather than a standalone OAuth flow. OAuth setup/start contracts continue to preserve explicit redirect URIs deterministically, expose runtime redirect mismatch diagnostics, and reject OAuth start when the active frontend origin does not match the configured redirect origin. Launcher-backed dev runtime now forwards `META_OAUTH_REDIRECT_URI` with the selected frontend origin so alternate local profiles can work when the Meta app is configured for that exact redirect.
  - Impact: Frontend can separate “Meta connected” from “direct sync complete” and “live reporting ready,” render truthful environment/snapshot-state blockers across dashboard routes, and stop offering an Instagram CTA that appears to be a broken standalone login path.
  - Owner: Sofia (Backend Metrics) + Maya (Integrations) + Lina (Frontend)

- **2026-04-01**
  - Endpoint: `GET /api/metrics/combined/`, dashboard aggregate snapshots, `GET /api/dashboards/library/`
  - Change: Campaign and creative row contracts now use `parishes: string[]` instead of `parish: string`. Warehouse-backed campaign rows now return truthful `status` and additive `objective` fields when present, campaign/parish currency values resolve from tenant ad-account metadata instead of a hardcoded `USD`, and `availability.parish_map` includes additive `coverage_percent`. Warehouse `503` responses now include machine-readable `code` and `reason` fields so stale snapshots can be distinguished from default or missing snapshots. Dashboard library reads now bootstrap three system presets for tenants with no active saved dashboards.
  - Impact: Frontend and any downstream consumers must migrate row-level parish access to arrays, handle dynamic currencies and additive campaign metadata, branch stale-snapshot UX from generic failures using `reason/code`, and expect first-load preset creation as a side effect of the library endpoint.
  - Owner: Sofia (Backend Metrics) + Priya (dbt) + Lina (Frontend)

- **2026-03-30**
  - Endpoint: Warehouse contract (`dbt` backend raw bridge + Meta/Google staging/reference marts)
  - Change: Preserved real backend `tenant_id` values through bridge-backed Postgres warehouse builds instead of restamping rows as `tenant_demo`. Bridge-backed fixture views now refresh on dbt runs when their SQL changes so live warehouse marts stay aligned with the latest bridge contract.
  - Impact: Tenant-scoped warehouse snapshots and `/api/metrics/combined/?source=warehouse` can resolve live Meta client data for the correct tenant instead of producing empty/stale results behind a successful dbt run.
  - Owner: Priya (dbt) + Sofia (Backend Metrics)
- **2026-03-30**
  - Endpoint: `GET /api/metrics/combined/`
  - Change: Added warehouse-only filtered query support for `start_date`, `end_date`, `account_id`, `channels`, `campaign_search`, and `parish` through direct warehouse daily aggregates. Warehouse responses now include additive `coverage` and `availability` metadata for truthful section states, while non-warehouse sources remain shape-compatible with the prior combined payload contract.
  - Impact: Meta dashboard filters can drive real account/range/search queries without mutating cached fake/demo payloads or silently falling back when warehouse data is unavailable.
  - Owner: Sofia (Backend Metrics) + Priya (dbt) + Lina (Frontend)
- **2026-03-30**
  - Endpoint: `GET /api/dashboards/library/`, `GET|POST /api/dashboards/definitions/`, `GET|PATCH|DELETE /api/dashboards/definitions/{id}/`, `POST /api/dashboards/definitions/{id}/duplicate/`
  - Change: Added tenant-scoped saved-dashboard definition CRUD plus duplicate workflow, and changed dashboard library responses from a flat mixed list into `{ generatedAt, systemTemplates, savedDashboards }`. Saved dashboards are now backed by dedicated `DashboardDefinition` records and route to `/dashboards/saved/{id}` instead of reusing report definitions.
  - Impact: The dashboard builder/library can create, open, rename, duplicate, archive/delete, and list tenant-scoped Meta dashboard presets separately from `/reports/*` export definitions.
  - Owner: Sofia (Backend Metrics) + Lina (Frontend)

- **2026-03-21**
  - Endpoint: `GET /api/integrations/google_analytics/setup/`, `POST /api/integrations/google_analytics/oauth/start/`, `POST /api/integrations/google_analytics/oauth/exchange/`, `GET /api/integrations/google_analytics/properties/`, `POST /api/integrations/google_analytics/provision/`, `GET /api/integrations/google_analytics/status/`
  - Change: Added tenant-scoped GA4 onboarding and connection-management contract for runtime readiness, OAuth state exchange, property discovery, provisioning, and connection status. Status surfaces preserve canonical onboarding states (`not_connected`, `started_not_complete`, `complete`, `active`) and expose redirect/runtime diagnostics needed by the Data Sources flow.
  - Impact: Frontend can connect a GA4 property and monitor its sync/setup lifecycle through dedicated integration endpoints without changing the existing pilot reporting endpoint shape on `/api/analytics/web/ga4/`.
  - Owner: Maya (Integrations) + Sofia (Backend Metrics) + Lina (Frontend)
- **2026-03-21**
  - Endpoint: Operational probe `python3 infrastructure/airbyte/scripts/airbyte_health_check.py`
  - Change: Extended the Airbyte health-check script to derive stale thresholds from both basic schedules and a limited supported subset of cron expressions before falling back to `AIRBYTE_FALLBACK_STALE_MINUTES`.
  - Impact: CI/operators get deterministic health classifications for cron-scheduled Airbyte connections instead of treating every cron connection as fallback-threshold based.
  - Owner: Maya (Integrations) + Omar (SRE)
- **2026-03-06**
  - Endpoint: `GET /api/health/airbyte/`
  - Change: Added degraded-mode fallback when Airbyte status tables are unavailable (for example, pre-migration smoke environments). Endpoint now returns `503` with `status="status_store_unavailable"` instead of surfacing an internal `500` error.
  - Impact: Release smoke checks and operators get deterministic health output during bootstrap/migration gaps; no changes to healthy-path payload fields.
  - Owner: Sofia (Backend Metrics) + Omar (SRE)
- **2026-02-23**
  - Endpoint: `GET /api/analytics/google-ads/workspace/summary/`
  - Change: Added non-breaking composite workspace summary payload for unified Google Ads first paint. Response extends executive payload shape with `alerts_summary`, `governance_summary`, `top_insights`, and `workspace_generated_at`.
  - Impact: Unified `/dashboards/google-ads` workspace can load KPI strip, top insights rail, and governance/alert badges in one call while keeping existing tab-detail endpoints unchanged. Legacy dashboard routes (`/dashboards/google-ads/*`) continue through compatibility redirects to query-driven workspace tabs.
  - Owner: Sofia (Backend Metrics) + Lina (Frontend) + Maya (Integrations)
- **2026-02-22**
  - Endpoint: `GET /api/analytics/google-ads/executive/`, `GET /api/analytics/google-ads/campaigns/`, `GET /api/analytics/google-ads/campaigns/{campaign_id}/`, `GET /api/analytics/google-ads/channels/`, `GET /api/analytics/google-ads/ad-groups/`, `GET /api/analytics/google-ads/ads/`, `GET /api/analytics/google-ads/assets/`, `GET /api/analytics/google-ads/keywords/`, `GET /api/analytics/google-ads/search-terms/`, `GET /api/analytics/google-ads/search-term-insights/`, `GET /api/analytics/google-ads/pmax/asset-groups/`, `GET /api/analytics/google-ads/breakdowns/`, `GET /api/analytics/google-ads/conversions/actions/`, `GET /api/analytics/google-ads/budgets/pacing/`, `GET /api/analytics/google-ads/change-events/`, `GET /api/analytics/google-ads/recommendations/`, `POST /api/analytics/google-ads/exports/`, `GET /api/analytics/google-ads/exports/{job_id}/`, `GET /api/analytics/google-ads/exports/{job_id}/download/`, `GET|POST|PATCH|DELETE /api/analytics/google-ads/saved-views/`, `GET|POST|PATCH|DELETE /api/analytics/google-ads/account-assignments/`
  - Change: Added MVP Google Ads analytics API surface for executive reporting, campaign/channel/keyword/search-term/PMax/breakdown/conversion/pacing/governance/recommendation views, plus Google Ads-specific export jobs and saved views. Added account-assignment management endpoint for tenant-scoped account RBAC and customer filtering in reporting endpoints.
  - Impact: Frontend can render dedicated Google Ads dashboard navigation and data pages using tenant-scoped server aggregation without changing existing integration setup/sync/status routes.
  - Owner: Sofia (Backend Metrics) + Lina (Frontend) + Maya (Integrations)
- **2026-02-21**
  - Endpoint: `GET /api/integrations/meta/setup/`, `GET /api/integrations/google_ads/setup/`, `POST /api/integrations/meta/oauth/start/`, `POST /api/integrations/meta/oauth/exchange/`, `POST /api/meta/connect/callback/`
  - Change: Added additive `runtime_context` diagnostics payload on setup responses containing resolved redirect details (`redirect_uri`, `redirect_source`), request host/origin metadata, launcher profile/runtime URLs (`DEV_ACTIVE_PROFILE`, `DEV_BACKEND_URL`, `DEV_FRONTEND_URL` when present), and optional dataset source echo. Added optional `runtime_context` request payload support on Meta OAuth start/exchange/callback for tracking-only metadata (non-breaking).
  - Impact: Frontend/operator setup flows can verify localhost profile/port alignment and redirect-source precedence without changing existing required response fields.
  - Owner: Sofia (Backend Metrics) + Lina (Frontend)
- **2026-02-21**
  - Endpoint: `GET /api/integrations/google_ads/status/`, `POST /api/integrations/google_ads/sync/`, `POST /api/integrations/google_ads/provision/`
  - Change: Added Google Ads SDK migration status metadata (`sync_engine`, `fallback_active`, `parity_state`, `last_parity_passed_at`) and runtime sync-engine preference handling in provisioning. Sync endpoint now dispatches SDK task execution when tenant sync state engine is `sdk`; otherwise it preserves existing Airbyte trigger behavior.
  - Impact: Existing Google Ads routes remain path-compatible while clients gain visibility into SDK/rollback state during migration.
  - Owner: Maya (Integrations) + Sofia (Backend Metrics)
- **2026-02-21**
  - Endpoint: `GET /api/meta/metrics/`, `GET /api/meta/pages/{page_id}/timeseries/`, `GET /api/meta/pages/{page_id}/posts/`, `GET|POST /api/meta/pages/{page_id}/exports/`, `GET /api/exports/{export_job_id}/download/`
  - Change: Added Meta Page metric registry listing (`/api/meta/metrics/`) and page timeseries (`/api/meta/pages/{page_id}/timeseries/`) to support metric/period pickers. Extended `/api/meta/pages/{page_id}/posts/` with filtering/sorting/pagination (`q`, `media_type`, `sort`, `sort_metric`, `limit`, `offset`) and added pagination metadata fields (`count`, `next_offset`, `prev_offset`). Added dashboard export lifecycle for Facebook Pages: `/api/meta/pages/{page_id}/exports/` creates queued export jobs (CSV/PDF/PNG) and `/api/exports/{export_job_id}/download/` streams completed artifacts.
  - Impact: Facebook Pages dashboard can render server-derived timeseries by period, paginate/filter posts without client-side overfetch, and generate downloadable exports using aggregated metrics only.
  - Owner: Sofia (Backend Metrics) + Lina (Frontend) + Maya (Integrations)
- **2026-02-20**
  - Endpoint: `POST /api/meta/connect/start/`, `POST /api/meta/connect/callback/`, `POST /api/integrations/meta/oauth/exchange/`, `POST /api/integrations/meta/pages/{page_id}/select/`
  - Change: Split OAuth flow intent for Page Insights vs marketing exchange. `/api/meta/connect/start/` now uses page-only OAuth scopes from `META_PAGE_INSIGHTS_OAUTH_SCOPES`, while `/api/meta/connect/callback/` executes page-connection persistence (`MetaConnection` + `MetaPage`) and returns `default_page_id` plus bootstrap task ids. Marketing exchange rejects page-flow state with `code=wrong_oauth_flow`. Scope sanitization now strips invalid Facebook Login scopes (`read_insights`, `instagram_*`) case-insensitively before building authorize URL.
  - Impact: Facebook Page dashboard can onboard/connect without ad-account access and no longer gets blocked by “no ad accounts returned” or invalid-scope OAuth errors; ad-account marketing setup remains unchanged on `/api/integrations/meta/oauth/exchange/`.
  - Owner: Sofia (Backend Metrics) + Lina (Frontend) + Maya (Integrations)
- **2026-02-19**
  - Endpoint: `POST /api/meta/connect/start/`, `POST /api/meta/connect/callback/`, `GET /api/meta/pages/`, `POST /api/meta/pages/{page_id}/sync/`, `GET /api/meta/pages/{page_id}/overview/`, `GET /api/meta/pages/{page_id}/posts/`, `GET /api/meta/posts/{post_id}/`, `GET /api/meta/posts/{post_id}/timeseries/`
  - Change: Added canonical Facebook Page/Post Insights contract aliases under `/api/meta/*` with per-metric availability metadata, last-sync timestamps, and background sync trigger orchestration (`sync_page_posts`, `discover_supported_metrics`, `sync_page_insights`, `sync_post_insights`).
  - Impact: Frontend can render a dedicated Facebook analytics slice without relying on legacy `/api/metrics/meta/*` paths; unsupported metrics are surfaced as availability flags instead of hard failures.
  - Owner: Sofia (Backend Metrics) + Lina (Frontend) + Maya (Integrations)
- **2026-02-19**
  - Endpoint: `GET /api/integrations/meta/oauth/callback/`, `GET /api/integrations/meta/pages/`, `POST /api/integrations/meta/pages/{page_id}/select/`, `POST /api/metrics/meta/pages/{page_id}/refresh/`, `GET /api/metrics/meta/pages/{page_id}/overview/`, `GET /api/metrics/meta/pages/{page_id}/timeseries/`, `GET /api/metrics/meta/pages/{page_id}/posts/`, `GET /api/metrics/meta/posts/{post_id}/timeseries/`
  - Change: Added Page/Post Insights contract surfaces backed by new encrypted page-credential and timeseries persistence models (`MetaConnection`, `MetaPage`, `MetaMetricRegistry`, `MetaInsightPoint`, `MetaPost`, `MetaPostInsightPoint`) with asynchronous refresh and registry-based invalid metric fallback.
  - Impact: Frontend can render Page/Post Insights dashboards exclusively from backend storage, while invalid/deprecated metrics are represented explicitly in registry status and hidden by default in metric pickers.
  - Owner: Sofia (Backend Metrics) + Lina (Frontend) + Maya (Integrations)
- **2026-02-19**
  - Endpoint: Warehouse contract (`dbt` Meta staging + snapshots + marts)
  - Change: Hardened `stg_meta_insights` cross-database JSON parsing (DuckDB/Postgres compatibility), added fallback behavior when upstream `reach` is absent, and moved Meta SCD2 snapshots to explicit nodes (`meta_campaign_snapshot`, `meta_adset_snapshot`, `meta_ad_snapshot`) keyed by tenant-aware identifiers.
  - Impact: Stabilizes local/CI dbt execution path and preserves tenant-safe snapshot grain without colliding with legacy snapshot relations.
  - Owner: Priya (dbt) + Sofia (Backend Metrics)
- **2026-02-19**
  - Endpoint: `GET /api/meta/accounts/`, `GET /api/meta/campaigns/`, `GET /api/meta/adsets/`, `GET /api/meta/ads/`, `GET /api/meta/insights/`
  - Change: Added tenant-scoped paginated Meta read APIs backed by PostgreSQL persistence, with query filters for status/search/date windows and foreign-key filters (`account_id`, `campaign_id`, `adset_id`, `level`).
  - Impact: Frontend Meta account/campaign/insights screens can read directly from backend tables without querying Airbyte APIs; existing `/api/integrations/meta/*` OAuth/provision/sync routes remain unchanged.
  - Owner: Sofia (Backend Metrics) + Lina (Frontend) + Maya (Integrations)
- **2026-02-19**
  - Endpoint: `POST /api/integrations/meta/oauth/exchange/`, `POST /api/integrations/meta/pages/connect/`
  - Change: Enforced required scope gate as `(ads_read OR ads_management) AND business_management AND pages_read_engagement AND pages_show_list`; missing permissions now persist actionable credential status reasons for reauth/rerequest flow.
  - Impact: OAuth completion blocks provisioning/sync when minimum Meta permissions are missing and surfaces deterministic remediation in UI.
  - Owner: Sofia (Backend Metrics) + Maya (Integrations)
- **2026-02-19**
  - Endpoint: Scheduled tasks (`integrations.tasks.refresh_meta_tokens`, `integrations.tasks.sync_meta_accounts`, `integrations.tasks.sync_meta_hierarchy`, `integrations.tasks.sync_meta_insights_incremental`)
  - Change: Added hourly token/account/insights sync and daily hierarchy sync schedules in `America/Jamaica`, plus persistent upstream failure records via `integrations.APIErrorLog`.
  - Impact: Operational visibility for Meta failures improved (`tenant/account/endpoint/status_code/retryable`), and direct-sync datasets remain fresh for `/api/meta/*` consumers.
  - Owner: Sofia (Backend Metrics) + Omar (SRE)
- **2026-02-17**
  - Endpoint: `GET /api/integrations/meta/setup/`, `POST /api/integrations/meta/oauth/start/`, `POST /api/integrations/meta/oauth/exchange/`, `POST /api/integrations/meta/pages/connect/`, `POST /api/integrations/meta/logout/`
  - Change: Added manual browser-redirect OAuth hardening for Meta Login for Business (required `config_id` support), optional OAuth `auth_type=rerequest`, token identity validation via `debug_token`, permission diagnostics (`granted/declined/missing_required_permissions`), and tenant-scoped Meta logout/disconnect endpoint.
  - Impact: Data Sources now supports permission-rerequest and stricter readiness validation before Meta provisioning; clients can call `POST /api/integrations/meta/logout/` to clear tenant Meta credentials.
  - Owner: Sofia (Backend Metrics) + Lina (Frontend) + Maya (Integrations)
- **2026-02-17**
  - Endpoint: `GET /api/integrations/social/status/`
  - Change: Added tenant-scoped social connection status payload for Meta + Instagram with canonical statuses (`not_connected`, `started_not_complete`, `complete`, `active`), reason metadata, recommended actions, and sync timestamps.
  - Impact: Frontend Data Sources now renders social onboarding/health cards and Home links directly into social setup mode.
  - Owner: Sofia (Backend Metrics) + Lina (Frontend) + Maya (Integrations)
- **2026-02-17**
  - Endpoint: `GET /api/schema/` metadata, `GET|POST /api/reports/{id}/exports/`, `GET|POST /api/alerts/`, `GET|POST /api/admin/alerts/`
  - Change: OpenAPI operation IDs were deduplicated for report exports (method-specific) and tenant/admin alert-rule surfaces (distinct operation ID bases) without changing route paths or payloads.
  - Impact: Schema consumers/codegen no longer receive duplicated `operationId` values.
  - Owner: Sofia (Backend Metrics)
- **2026-02-17**
  - Endpoint: `POST /api/integrations/meta/oauth/start/` (frontend orchestration update)
  - Change: Data Sources social card CTA now starts Meta OAuth directly for `connect_oauth` actions and falls back to opening the setup panel with errors surfaced when OAuth start fails.
  - Impact: “Connect with Facebook” on social cards now initiates OAuth in one click while preserving setup troubleshooting flow.
  - Owner: Lina (Frontend) + Maya (Integrations)
- **2026-02-13**
  - Endpoint: `GET /api/integrations/meta/setup/`, `POST /api/integrations/meta/oauth/start/`, `POST /api/integrations/meta/oauth/exchange/`, `POST /api/integrations/meta/pages/connect/`, `POST /api/integrations/meta/provision/`, `POST /api/integrations/meta/sync/`
  - Change: Finalized Meta Marketing API connector flow with Facebook Login OAuth state validation, ad-account-required page connect, optional Instagram account selection, and Airbyte source/connection provisioning + initial sync trigger.
  - Impact: Data Sources can complete Meta onboarding in one guided flow and immediately start Insights ingestion for reporting marts.
  - Owner: Sofia (Backend Metrics) + Lina (Frontend) + Maya (Integrations)
- **2026-02-08**
  - Endpoint: Integration lifecycle APIs (planned, superseded by provider-specific rollout)
  - Change: Initial plan captured for provider-generic connector lifecycle APIs; implementation proceeded with provider-specific Meta endpoints first.
  - Impact: Historical planning reference only; use 2026-02-13 entry for currently implemented connector contracts.
  - Owner: Sofia (Backend Metrics) + Lina (Frontend)
- **2026-02-06**
  - Endpoint: `GET /api/dashboards/library/`
  - Change: Added dashboard library API endpoint to replace frontend mock data and include saved report-backed items.
  - Impact: Frontend dashboard library now relies on backend response shape (`id`, `name`, `type`, `owner`, `updatedAt`, `tags`, `description`, `route`).
  - Owner: Lina (Frontend) + Sofia (Backend)
- **2026-02-06**
  - Endpoint: `GET|POST /api/reports/`, `GET|PATCH|DELETE /api/reports/{id}/`, `GET|POST /api/reports/{id}/exports/`
  - Change: Added report definition CRUD + export-job request/listing contracts.
  - Impact: Enables Post-MVP report surfaces and export lifecycle UI; clients should handle queued/running/completed/failed job statuses.
  - Owner: Sofia (Backend Metrics)
- **2026-02-06**
  - Endpoint: `GET /api/alerts/`, `GET /api/alerts/{id}/`
  - Change: Added tenant-facing alert rule routes (mirroring admin rule definitions) for frontend alerts management pages.
  - Impact: Post-MVP alerts list/detail pages can consume tenant-scoped rule definitions directly.
  - Owner: Sofia (Backend Metrics)
- **2026-02-06**
  - Endpoint: `GET /api/summaries/`, `GET /api/summaries/{id}/`, `POST /api/summaries/refresh/`
  - Change: Added persisted AI summary list/detail contracts and manual refresh endpoint.
  - Impact: Frontend summaries views can render generated/fallback status and payload snapshots.
  - Owner: Sofia (Backend Metrics)
- **2026-02-06**
  - Endpoint: `GET /api/ops/sync-health/`, `GET /api/ops/health-overview/`
  - Change: Added operational aggregation endpoints for sync-health counts/rows and consolidated health cards.
  - Impact: Powers Post-MVP `/ops/sync-health` and `/ops/health` pages with unified status semantics.
  - Owner: Omar (SRE) + Sofia (Backend Metrics)
- **2026-02-06**
  - Endpoint: `GET /api/analytics/web/ga4/`, `GET /api/analytics/web/search-console/`
  - Change: Added Phase 2 pilot web analytics endpoints for GA4/Search Console marts.
  - Impact: Provides API exposure path for GA4/Search Console pilot ingestion without changing `/api/metrics/combined/`.
  - Owner: Priya (dbt) + Sofia (Backend Metrics)
- **2026-02-06**
  - Endpoint: `POST /api/token/`, `POST /api/token/refresh/`, `POST /api/auth/login/`, `POST /api/auth/password-reset/`, `POST /api/auth/password-reset/confirm/`, `POST /api/tenants/`, `POST /api/users/accept-invite/`
  - Change: Added DRF rate limiting for unauthenticated/auth flows; clients may now receive `429` when thresholds are exceeded.
  - Impact: API clients and smoke tests should handle throttled responses and retry/backoff accordingly.
  - Owner: Sofia (Backend Metrics) + Nina (Security)
- **2026-02-06**
  - Endpoint: Cross-origin responses on API routes
  - Change: Added explicit environment-driven CORS policy (`CORS_ALLOWED_ORIGINS`, preflight handling, allow-method/header controls).
  - Impact: Browser callers must originate from configured allowlist entries in production.
  - Owner: Sofia (Backend Metrics) + Victor (Infra/DevOps)
- **2025-01-05**
  - Endpoint: `/api/metrics/combined/`
  - Change: Added `snapshot_generated_at` for freshness banner.
  - Impact: Frontend snapshot freshness UI and monitoring.
  - Owner: Sofia (Backend Metrics)
- **2026-01-22**
  - Endpoint: `/api/metrics/combined/`
  - Change: Warehouse-backed `budget` array now populated from Meta ad set daily budgets with pacing fields (`monthlyBudget`, `spendToDate`, `projectedSpend`, `pacingPercent`, optional `parishes`, `startDate`, `endDate`).
  - Impact: Budget pacing widgets can rely on live data; consumers should handle non-empty arrays and parse ISO date fields.
  - Owner: Priya (dbt)

## Update Rules

- Update this file whenever an endpoint schema or payload changes.
- Coordinate with frontend + BI when fields are added/removed.
