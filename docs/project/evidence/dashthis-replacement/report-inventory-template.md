# DashThis Report Inventory Template

Use this in Phase 0 to list the exact DashThis reports that must be replaced. Keep business data
aggregated and do not attach unredacted customer-sensitive exports.

## Inventory Header

- Operator:
- Inventory timestamp:
- DashThis subscription/account:
- First proof tenant/client:
- Cancellation target date:
- DashThis reports reviewed:

## Report Inventory

| DashThis report/dashboard | Client/tenant | Sources | Required widgets | Outputs | Recipients | Status |
| ------------------------- | ------------- | ------- | ---------------- | ------- | ---------- | ------ |
| TBD | TBD | Meta Ads, Google Ads, TBD | TBD | Dashboard, PDF, CSV, PNG, scheduled email, TBD | TBD | blocked |

## Required Widgets

Mark each as required, deferred, or not used.

| Widget or section | Status | Notes |
| ----------------- | ------ | ----- |
| KPI cards | TBD | Spend, impressions, clicks, CTR, CPC, CPM, conversions, CPA, ROAS. |
| Campaign table | TBD | Confirm dimensions and sort order. |
| Creative table | TBD | Confirm whether asset thumbnails are required. |
| Budget pacing | TBD | Confirm monthly budget source. |
| Parish/map view | TBD | Confirm geo grain and data availability. |
| Channel/platform split | TBD | Confirm Meta vs Google grouping. |
| Date comparison | TBD | Confirm previous period or year-over-year requirement. |
| Scheduled email | TBD | Confirm recipients and cadence. |
| Slack/webhook | TBD | Required only if DashThis currently provides an equivalent workflow. |

## Source Decision

| Source | Required for cancellation | Notes |
| ------ | ------------------------- | ----- |
| Meta Ads | yes | Default paid-media scope. |
| Google Ads | yes | Default paid-media scope. |
| GA4 | TBD | Mark required only if current DashThis reports depend on it. |
| Search Console | TBD | Mark required only if current DashThis reports depend on it. |
| LinkedIn | TBD | Deferred unless current DashThis reports depend on it. |
| TikTok | TBD | Deferred unless current DashThis reports depend on it. |
| Organic social | TBD | Deferred unless current DashThis reports depend on it. |

## Inventory Decision

- Reports fully represented:
- Reports missing ADinsights coverage:
- Required sources deferred:
- Required outputs deferred:
- Phase 0 can exit:
- Reason:
