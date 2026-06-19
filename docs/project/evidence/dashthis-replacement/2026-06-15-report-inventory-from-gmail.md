# DashThis Replacement Report Inventory From Gmail

Evidence timestamp: 2026-06-15T18:49:55-0500
Timezone: America/Jamaica
Source: Gmail search and shortlisted message reads requested by the operator.
Scope: BOJ/Common Cents, Grace, JDIC, and SLB.

This artifact summarizes client/reporting signals from Gmail without copying sensitive source
exports, credentials, card details, ad-account IDs, webhook URLs, or user-level data.

## Search Scope

Queries used:

- `DashThis`
- `SLB OR "Student Loan Bureau" OR "Students Loan Bureau"` plus report/dashboard/campaign terms.
- `Grace OR GraceKennedy OR "Grace Kennedy"` plus report/dashboard/campaign terms.
- `JDIC OR "Jamaica Deposit Insurance"` plus report/dashboard/campaign terms.
- `BOJ OR "Bank of Jamaica"` and `Common Cents` plus report/dashboard/campaign terms.

Shortlisted messages read:

| Gmail message id | Date | Signal |
| ---------------- | ---- | ------ |
| `19db0cd06e9a5618` | 2026-04-21 | DashThis billing/payment pressure. |
| `19ecc324bce0af95` | 2026-06-15 | SLB May 2026 marketing campaign status report thread. |
| `19ec01dad5cd2276` | 2026-06-13 | SLB Meta ads receipt for Ready Set Apply campaigns. |
| `19ec9a2cdd83c4d2` | 2026-06-15 | JDIC Meta ads receipt for engagement campaigns. |
| `19ecd0860fdd2337` | 2026-06-15 | Common Cents/BOJ Meta ads receipt. |
| `19e9324deedceab2` | 2026-06-04 | Grace Foods Search Console performance email. |
| `19ea90a498266bdf` | 2026-06-08 | Grace Foods Google Analytics performance email. |

## Public Lookup Context

Public sources checked to validate client/campaign naming:

| Client/campaign | Public source | Relevance |
| --------------- | ------------- | --------- |
| BOJ/Common Cents | `https://boj.org.jm/` and `https://jis.gov.jm/boj-launches-common-cents-series-to-boost-financial-literacy/` | Confirms Bank of Jamaica identity and public Common Cents campaign context. |
| SLB | `https://portal.slbja.com/` and public SLB social search results for Ready Set Apply | Confirms SLB public portal and that Ready Set Apply is an active public campaign theme. |
| JDIC | `https://www.jdic.org/` and `https://www.jdic.org/about-jdic/` | Confirms JDIC official identity and public role. |
| Grace Foods | `https://www.gracefoods.com/` | Confirms Grace Foods official web property for the GA4/Search Console evidence. |

## Recommended First Proof Target

Select SLB as the first Phase 1 proof target unless the operator overrides it.

Reason:

- Gmail contains an explicit `SLB Marketing Campaign Status Report, May 2026` thread.
- The report scope includes campaign activity, content development, social media support,
  creative/strategic work, platform performance, and top Instagram/Facebook posts.
- Gmail also contains Meta billing/activity evidence for the SLB Ready Set Apply campaign.
- This gives the clearest bridge from an existing client report to ADinsights Meta reporting.

Notable limitation:

- Gmail did not prove Google Ads activity for SLB in this pass. If the DashThis replacement must
  include Google Ads for SLB, that remains a Phase 0 blocker.
- The SLB attachments show the current report is broader than paid media. Exact SLB parity requires
  organic Facebook/Instagram performance, top post/media performance, report narrative sections,
  and recommendations. See
  `docs/project/evidence/dashthis-replacement/2026-06-15-email-attachment-review.md`.

## Report Inventory

| Report/dashboard | Client/tenant | Evidence strength | Sources indicated by Gmail | Required widgets inferred | Outputs inferred | Status |
| ---------------- | ------------- | ----------------- | -------------------------- | ------------------------- | ---------------- | ------ |
| SLB Marketing Campaign Status Report, May 2026 | SLB / Students' Loan Bureau | Strong | Meta Ads, Instagram/Facebook social performance; organic/content activity likely included | KPI summary, platform performance, top posts, campaign activity, creative/work completed, June recommendations | Monthly report attachment/email; ADinsights should support dashboard plus PDF/CSV/PNG export and scheduled email | Select as first proof target; needs recipient/output confirmation |
| JDIC campaign reporting | JDIC | Medium | Meta Ads engagement campaigns and boosted/social posts | KPI summary, campaign table, platform split, creative/post performance | Dashboard/report export not proven by Gmail | Candidate after SLB; needs exact report name and recipient confirmation |
| Common Cents campaign reporting | BOJ/Common Cents | Medium | Meta Ads engagement/awareness campaigns, segmented ad sets, campaign optimization tasks | KPI summary, campaign/ad set table, audience/segment split, platform split | Dashboard/report export not proven by Gmail | Candidate after SLB/JDIC; needs exact report name and BOJ recipient confirmation |
| Grace Foods web performance reporting | Grace Foods | Strong for GA4/Search Console, weak for paid-media DashThis replacement | Search Console and Google Analytics performance reports | Website traffic, search clicks/impressions, top pages, top queries, devices, countries, active users, events, engagement | Google-generated performance email; ADinsights replacement would require GA4/Search Console reporting | Scope expansion; do not use as first paid-media proof target unless GA4/Search Console becomes required |

## Source Decision

| Source | Decision from Gmail evidence | Notes |
| ------ | ---------------------------- | ----- |
| Meta Ads | Required for SLB, JDIC, and BOJ/Common Cents. | Multiple Meta campaign/receipt signals exist. |
| Google Ads | Not proven for BOJ, Grace, JDIC, or SLB in this Gmail pass. | Keep as required only if DashThis or source-platform access proves it. |
| GA4 | Required if Grace is in the cancellation scope. | Grace Foods Google Analytics performance email exists. |
| Search Console | Required if Grace is in the cancellation scope. | Grace Foods Search Console performance email exists. |
| Organic social/content operations | Likely required for exact SLB report parity, but not for paid-media replacement proof. | The SLB report references content/social support and top posts. Treat as a known gap unless operator narrows scope to paid ads. |

## Attachment Review Update

Two SLB monthly report PDFs were read from Gmail after the initial inventory:

- May 2026 SLB monthly campaign status report.
- March-April 2026 SLB campaign status report.

The recurring report shape includes executive/narrative sections, organic Instagram/Facebook
performance, content counts, top performers, digital ad pages, and next-step recommendations. This
changes the recommended first build from a generic paid-media dashboard to an SLB monthly campaign
status report generator backed by Meta Ads plus organic Meta/Page/Instagram insights.

## Required Widgets For First SLB Proof

| Widget or section | Status | Notes |
| ----------------- | ------ | ----- |
| KPI cards | Required | Spend, impressions, clicks, CTR, CPC, CPM, and campaign totals from Meta. |
| Campaign table | Required | Needed for Ready Set Apply campaign proof. |
| Creative/post table | Required for parity, partial for paid-media MVP | Gmail report scope references top Instagram/Facebook posts. |
| Platform split | Required | At minimum Facebook vs Instagram. |
| Date comparison | Recommended | Month-over-month if the existing report uses it. |
| PDF export | Required | Existing report was sent as a report attachment/email; exact format needs confirmation. |
| CSV export | Required by ADinsights cancellation bar | Not proven as required by email, but part of replacement gate. |
| PNG export | Required by ADinsights cancellation bar | Not proven as required by email, but part of replacement gate. |
| Scheduled email | Required | Email delivery must replace manual report sending. |
| Slack/webhook | Not proven | Keep deferred unless operator confirms DashThis currently delivers through Slack/webhook. |

## Open Blockers

- Confirm the exact DashThis report/dashboard names for SLB, JDIC, BOJ/Common Cents, and Grace.
- Confirm whether Grace is in cancellation scope. If yes, GA4 and Search Console become required.
- Confirm whether Google Ads is actually required for these four clients. Gmail did not prove it.
- Confirm first proof date range. Recommended starting point: May 2026 for SLB because Gmail shows a
  May 2026 report and Meta activity around the same reporting period.
- Confirm report recipients and delivery cadence for SLB.
- Collect source-platform totals for SLB Meta campaigns in the selected date range.
- Confirm whether exact SLB parity needs organic/social post performance or only paid Meta.

## Phase 0 Decision

Phase 0 is now partially built from Gmail evidence.

- First proof target: SLB, pending operator confirmation.
- First proof date range: May 2026 recommended, pending operator confirmation.
- First source: Meta Ads.
- Still blocked before Phase 1 exit: Google Ads requirement, recipient list, exact report output
  format, source-platform totals, and whether full SLB parity requires organic/social post metrics
  and narrative report sections.
