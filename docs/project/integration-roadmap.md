# Integration Roadmap (Connectors + API Plan)

Purpose: define what ADinsights should connect to, what we need to build, which APIs to validate,
and the order of execution based on value and dependency. This is the planning backbone for
connectors beyond Meta + Google Ads.

Baseline: match DashThis out-of-the-box coverage (ads + analytics + SEO + email + call tracking),
then expand toward HubSpot-style ecosystems (CRM, lifecycle, attribution, data destinations).

Constraints:

- Multi-tenant isolation and aggregated metrics only (no user-level data).
- Tokens are encrypted; no secrets logged or stored in docs.
- Prefer Airbyte OSS where possible; custom connectors only when required.

## 1) Prioritization framework

Order decisions use:

1. Revenue impact (paid media + attribution first).
2. Coverage density (multi-channel dashboards with shared KPIs).
3. API stability + auth complexity.
4. Cost-to-implement (Airbyte availability, schema maturity).
5. Risk (rate limits, partner approvals, compliance).

## 2) Integration categories and priority

### A) Paid media (highest value)

Necessaries (Phase 1-2):

- Google Ads (OAuth + developer token; GAQL reports; cost micros conversion).
- Meta Ads/Insights (token lifecycle; lookback windows; hourly sync).
- Microsoft Advertising (OAuth 2.0; reporting API).
- LinkedIn Ads (OAuth; strict API limits; requires app approval).
- TikTok Ads (OAuth + refresh tokens; ad reporting).

Nice-to-haves (Phase 3+):

- Snapchat Ads (bearer access tokens; marketing API).
- Pinterest Ads (OAuth 2.0; ads reporting).
- Reddit Ads (OAuth 2.0; ads reporting).
- X Ads (OAuth 1.0a in ads contexts; higher compliance and limits).
- Amazon Ads (sponsored products/brands/display; access gating).
- The Trade Desk (programmatic; enterprise-level integration).
- Google Display & Video 360 (enterprise programmatic).

### B) Organic social + video analytics

Necessaries (Phase 2-3):

- YouTube Analytics/Reporting (OAuth scopes; reporting jobs).
- Facebook Page Insights (via Meta Graph; permissions review).
- Instagram Insights (via Meta Graph; business accounts).
- LinkedIn Page analytics (OAuth; admin permissions).

Nice-to-haves (Phase 3+):

- TikTok Organic analytics (creator/performance endpoints).
- Additional organic platforms as demand emerges.

### C) Web + product analytics

Necessaries (Phase 2):

- Google Analytics 4 (OAuth; data retention constraints; property-level access).
- Google Search Console (OAuth; SEO-focused metrics).

Nice-to-haves (Phase 3+):

- Adobe Analytics (enterprise access + SCIM alignment).
- Mixpanel (OAuth or service account tokens).
- Amplitude (API keys + secret).

### D) CRM + marketing automation (HubSpot-like stack)

Necessaries (Phase 3):

- HubSpot (OAuth or private app tokens; CRM + marketing events).
- Salesforce (OAuth + connected app; API limits).
- Marketo (client ID/secret; REST API).

Nice-to-haves (Phase 4):

- Klaviyo (API keys; email + ecommerce).
- Mailchimp (OAuth; email performance).
- ActiveCampaign (API keys; automation + CRM).

### E) Ecommerce + revenue attribution

Necessaries (Phase 3):

- Shopify (OAuth + webhooks; orders, refunds).
- Stripe (API keys; payments, subscriptions).

Nice-to-haves (Phase 4):

- WooCommerce (OAuth or keys; orders).
- Additional cart platforms as demand appears.

### F) Call tracking + lead capture

Necessaries (Phase 3):

- CallRail (API key; calls + attribution).
- Twilio (API keys; call logs, messages).

Nice-to-haves (Phase 4):

- Additional call tracking vendors by demand.

### G) Data warehouse / BI destinations

Necessaries (Phase 4):

- BigQuery, Snowflake, Redshift (destinations if ADinsights becomes a hub).
- Looker Studio, Tableau, Power BI (export connectors).

Nice-to-haves (Phase 4+):

- Custom warehouse exports and reverse ETL integrations.

### H) Universal connectors (must-have)

Necessaries (Phase 1):

- Google Sheets / CSV import / S3 uploads for offline conversions and long-tail sources.
  Nice-to-haves (Phase 2+):
- Additional file sources (SharePoint, OneDrive) if tenant demand appears.

## 3) API requirements checklist (per connector)

- Auth type (OAuth 2.0, OAuth 1.0a, API keys, refresh tokens).
- Required scopes/permissions and approval workflows.
- Rate limits + quota units; backoff + jitter requirements.
- Data model coverage (campaign/adset/ad, creatives, geo, conversions, revenue).
- Historical lookback limits; late conversion handling windows.
- Timezone + currency expectations.
- Known data delays; freshness SLA targets.
- Compliance and legal constraints (terms, data retention).
- Airbyte support status and connector maturity.

## 4) Phased roadmap and logical build order

### Phase 0: Foundation (current)

- Meta Ads + Google Ads ingestion (Airbyte), dbt marts, snapshot API, frontend dashboards.
- Universal connectors: CSV import and Google Sheets stub (planning only).

### Phase 1: Core paid media expansion

Order:

1. Microsoft Advertising (close parity to Google Ads metrics).
2. LinkedIn Ads (B2B demand; approval + limits).
3. TikTok Ads (high growth; refresh token lifecycle).

### Phase 2: Analytics + SEO + organic

Order:

1. GA4 + Search Console (measurement + SEO).
2. YouTube Analytics (video performance).
3. Facebook/Instagram Insights and LinkedIn Page analytics (brand health).

### Phase 3: CRM + revenue attribution

Order:

1. HubSpot (fastest path to lifecycle attribution).
2. Salesforce (enterprise demand).
3. Shopify + Stripe (revenue linkage).
4. CallRail/Twilio (lead tracking).

### Phase 4: Programmatic + enterprise + destinations

Order:

1. Amazon Ads, DV360, The Trade Desk (enterprise).
2. Data warehouse + BI exports (BigQuery, Snowflake, Redshift, Tableau, Power BI).

## 5) Build sequence per connector

1. Validate API access (scopes, approvals, rate limits).
2. Confirm Airbyte connector availability or decide on custom build.
3. Define warehouse schema + dbt staging/marts.
4. Add adapter payload mapping + snapshot generation.
5. Update frontend filters and dashboards to expose new metrics.
6. Add runbooks, tests, and telemetry for sync health.

## 6) Necessaries vs Nice-to-haves (summary)

Necessaries:

- Meta Ads, Google Ads, Microsoft Ads, LinkedIn Ads, TikTok Ads.
- GA4, Search Console.
- YouTube Analytics, Facebook/Instagram Insights, LinkedIn Page analytics.
- HubSpot, Salesforce, Shopify, Stripe, CallRail.
- Universal CSV/Sheets/S3.

Nice-to-haves:

- Snapchat, Pinterest, Reddit, X Ads, Amazon Ads, DV360, The Trade Desk.
- Adobe Analytics, Mixpanel, Amplitude.
- Marketo, Klaviyo, Mailchimp, ActiveCampaign.
- WooCommerce and other commerce platforms.
- Warehouse/BI destinations once demand is proven.

## 7) Open questions

- Which connectors need agency-level entitlements vs tenant-level defaults?
- What is the minimum viable set for each vertical (retail, finance, tourism)?
- Which vendors require partner approval and lead time?
- Do we support multi-currency and multi-timezone per tenant in Phase 2?

## 8) Related docs

- `docs/task_breakdown.md` (priorities and sequencing).
- `docs/project/integration-api-validation-checklist.md` (Phase 1 validation template).
- `docs/workstreams.md` (owners, tests, DoD).
- `docs/project/frontend-finished-product-spec.md` (UI implications).
- `docs/security/uac-spec.md` (entitlements and access control).
