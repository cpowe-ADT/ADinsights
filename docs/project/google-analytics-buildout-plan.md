# Google Analytics + Ads Data Buildout Plan

**Goal:** Enable full lifecycle integration for Google Analytics (GA4) alongside the existing Google Ads and Meta Ads integrations. This includes connection management, data ingestion (Airbyte/SDK), and unified KPI reporting.

## 1. Architecture & Module Structure

We will mirror the existing `backend/integrations/google_ads` pattern for `backend/integrations/google_analytics`.

### Directory Structure
```text
backend/integrations/google_analytics/
├── __init__.py
├── client.py           # GA4 Admin/Data API client wrappers
├── catalog.py          # Metric/Dimension reference catalog
├── ga4_templates.py    # Pre-defined report requests (e.g., traffic acquisition)
├── repository.py       # DB persistence helpers
├── views.py            # API views for connection/OAuth
├── urls.py             # URL routing
└── tasks.py            # Celery tasks for sync/caching
```

### Data Models
We need a connection model to track GA4 properties linked to a tenant.

- **`GoogleAnalyticsConnection`** (in `backend/integrations/models.py`)
    - `tenant`: ForeignKey(Tenant)
    - `property_id`: str (GA4 Property ID)
    - `property_name`: str
    - `credentials`: ForeignKey(PlatformCredential)
    - `is_active`: bool
    - `sync_frequency`: str (e.g., 'daily')

## 2. Authentication & Connection Flow

We will reuse `PlatformCredential` (provider='google_analytics') to store OAuth tokens.

1.  **OAuth Flow:**
    -   Reuse `accounts.views.GoogleOAuthStartView` pattern but with GA4 scopes (`https://www.googleapis.com/auth/analytics.readonly`).
    -   Implement `GoogleAnalyticsOAuthExchangeView` to swap code for tokens and store in `PlatformCredential`.

2.  **Property Selection:**
    -   Implement `GoogleAnalyticsPropertiesView` to list available GA4 properties for the authenticated user.
    -   Implement `GoogleAnalyticsProvisionView` to save the selected `property_id` to `GoogleAnalyticsConnection`.

## 3. Data Ingestion (Airbyte vs. SDK)

We will support a hybrid approach similar to Google Ads:
-   **SDK (Real-time/Preview):** Use `google-analytics-data` Python client for live dashboard checks and "today" stats.
-   **Airbyte (Warehouse):** Provision Airbyte connection for historical backfills and nightly syncs into Postgres.

### Helper Functions (KPI Extraction)
We need a unified interface to pull standard web KPIs that correlate with ad performance.

**`backend/integrations/google_analytics/client.py`**
```python
def fetch_traffic_acquisition(property_id: str, date_range: tuple[date, date]):
    """
    Returns:
        [
            {
                "date": "2024-01-01",
                "source": "google",
                "medium": "cpc",
                "campaign": "summer_sale",
                "sessions": 120,
                "users": 100,
                "events": 500,
                "conversions": 5
            },
            ...
        ]
    """
```

**KPIs to Extract:**
-   **Traffic:** Sessions, Total Users, New Users.
-   **Engagement:** Engagement Rate, Average Engagement Time.
-   **Conversion:** Key Events (Conversions), Event Count.
-   **Attribution:** Session Source, Session Medium, Session Campaign.

## 4. Unified Views (Data Merging)

To combine Google Analytics, Google Ads, and Facebook data into one view, we will enhance `backend/analytics/combined_metrics_service.py`.

1.  **Normalization:**
    -   Map GA4 `sessionSource` -> `platform` (google, meta, etc.)
    -   Map GA4 `sessionCampaignName` -> `campaign_name`
    -   Map GA4 `date` -> `date_day`

2.  **Join Logic:**
    -   **Ads Data:** Provides Spend, Impressions, Clicks (Upper Funnel).
    -   **Analytics Data:** Provides Sessions, Engagement, On-site Conversions (Lower Funnel).
    -   **Join Key:** `date` + `campaign_name` + `platform`.

3.  **View Layer:**
    -   Update `CombinedMetricsView` to fetch from `GoogleAnalyticsConnection` (via SDK or DB view) if enabled.
    -   Merge datasets in pandas or SQL (CTE join) to produce a "Full Funnel" row:
        `[Date, Campaign, Spend, Impressions, Clicks, Sessions, Conversions, ROAS]`

## 5. Implementation Steps

### Phase 1: Connection & Auth
-   [ ] Add `GoogleAnalyticsConnection` model.
-   [ ] Implement GA4 OAuth flow views.
-   [ ] Implement Property selection view.

### Phase 2: Ingestion Helpers
-   [ ] Add `google-analytics-data` dependency.
-   [ ] Implement `GoogleAnalyticsClient` wrapper for Data API (v1beta).
-   [ ] Create `fetch_daily_metrics` helper for core KPIs.

### Phase 3: Analytics Integration
-   [ ] Create `GoogleAnalyticsAdapter` implementing `MetricsAdapter` interface.
-   [ ] Update `CombinedMetricsView` to include GA4 adapter in the registry.
-   [ ] Add "Web Analytics" section to the Dashboard.

### Phase 4: Airbyte Setup (Optional/Later)
-   [ ] Configure Airbyte source definition for `source-google-analytics-data-api`.
-   [ ] Add provisioning logic in `GoogleAnalyticsProvisionView`.

## 6. Execution

Start with **Phase 1 & 2** to get live data flowing via SDK, then **Phase 3** to visualize it.
