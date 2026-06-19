# DashThis Replacement Email Attachment Review

Evidence timestamp: 2026-06-15T21:49:07-0500
Timezone: America/Jamaica
Source: Gmail attachment reads requested by the operator.
Related plan: `docs/project/dashthis-replacement-reporting-plan.md`

This artifact summarizes the SLB report attachments found in Gmail. It intentionally does not
commit raw PDFs, payment details, ad-account IDs, transaction URLs, card details, or user-level
data.

## Attachments Reviewed

| Gmail message id | Attachment | Review result |
| ---------------- | ---------- | ------------- |
| `19ebdf5cdfb29c0e` | `SLB Monthly Report - May 2026 Editable v2 (1).pdf` | Parsed 14-page May 2026 SLB campaign status report. |
| `19df52e8ccc43eae` | `SLB Marketing Campaign Status Report - March - April 2026.pdf` | Parsed 15-page March-April 2026 SLB campaign status report. |

## Main Finding

The SLB report is not just a DashThis-style paid-media dashboard. It is a monthly campaign status
report that blends:

- Organic Instagram and Facebook account performance.
- Paid or boosted digital ad top-performer pages.
- Content counts by platform/content format.
- Top creative/post performance.
- Month-over-month platform deltas.
- Narrative summaries of work completed.
- Creative, video, podcast, print, and strategic support.
- Next-month recommendations.

That means a paid Meta Ads dashboard is useful, but it will not replace the report SLB appears to
receive today. If cancellation depends on replacing this SLB report, ADinsights needs a monthly
narrative report template backed by Meta Page/Instagram Insights and Meta Ads data.

## Recurring SLB Report Shape

| Report section | Needed for parity | Data/source implication |
| -------------- | ----------------- | ----------------------- |
| Cover and reporting period | Yes | Report metadata and template rendering. |
| Account activity summary | Yes | Manual/narrative inputs or structured campaign notes. |
| Campaign and content development | Yes | Manual/narrative inputs or Content Operations activity log. |
| Creative and strategic support | Yes | Manual/narrative inputs or Content Operations activity log. |
| Video, podcast, print, or brand support | Sometimes | Manual/narrative inputs unless tracked in ADinsights. |
| Platform performance summary | Yes | Meta Page and Instagram aggregate insights. |
| Instagram metrics | Yes | Views, reach, visits, follows, interactions, link clicks, and MoM deltas. |
| Facebook metrics | Yes | Views, reach/viewers, visits, follows, content interactions, link clicks, and MoM deltas. |
| Content counts | Yes | Posts, reels, stories, statics/carousels by period. |
| Top static/carousel/reel posts | Yes | Post/media insights plus creative metadata. |
| Digital ads top performers | Yes | Meta Ads creative/campaign insights, including reach, impressions, clicks or conversions where available. |
| Recommendations and next steps | Yes | Manual/narrative inputs, optionally assisted by generated summary text. |

## Metrics Observed

The reviewed SLB reports repeatedly use these metric families:

- Instagram: views, reach, visits or profile visits, follows, interactions, link clicks, content
  counts, and month-over-month deltas.
- Facebook: views, viewers or reach, visits, follows, content interactions, link clicks, content
  counts, and month-over-month deltas.
- Top performers: views, interactions, likes/reactions, comments, shares, saves, reach,
  impressions, clicks, and conversions where available.
- Digital ads: reach, impressions, clicks/conversions, views, interactions, and campaign or ad
  creative context.

## What The Operator Needs To Decide

1. Confirm SLB as the first DashThis replacement proof target.
2. Confirm whether the goal is full SLB monthly report parity or a paid-media-only MVP.
3. If full parity is required, authorize or provide Meta Page and Instagram Insights access for
   SLB, not only Meta Ads access.
4. Confirm the first proof range. Recommended: May 2026, because a complete May SLB report exists.
5. Confirm whether March-April 2026 should be used as the comparison/baseline period.
6. Confirm report recipients and whether delivery should be scheduled email, manual download, or
   both.
7. Confirm whether narrative sections should be manually entered, generated from internal notes, or
   excluded from the first build.
8. Provide redacted source-platform totals or screenshots for the selected period so ADinsights can
   be tested against the source of truth.
9. Decide whether Grace is in the first cancellation scope. If yes, GA4 and Search Console must be
   activated too.

## Recommended Build Direction

Build the first replacement around SLB full-report parity, not only paid-media metrics.

Recommended Phase 1 slice:

- Data: Meta Ads plus Meta Page/Instagram aggregate insights for SLB.
- Output: monthly SLB campaign status report template with PDF export and scheduled email.
- Dashboard: keep KPI cards, campaign table, creative table, and platform split for operator review.
- Manual fields: allow account activity, work completed, and recommendations to be entered or
  edited before export.
- Validation: compare ADinsights totals against source-platform totals for May 2026 and compare
  March-April trend math where the report uses MoM deltas.

## Cancellation Warning

Do not cancel DashThis yet. The cancellation bar is not met until ADinsights can generate the SLB
monthly report, send it through the required delivery path, and pass fixed-range source-platform
comparison without relying on demo, stale, upload-only, or wrong-tenant data.

If the operator narrows scope to paid-media-only, Phase 1 can start faster, but the evidence should
explicitly state that the paid-media MVP does not replace the full SLB monthly campaign status
report.
