# Meta Reporting + Customizable Dashboards — Roadmap

Date: 2026-06-25
Owner: Adtelligent (Craig)
Companion docs: `meta-reporting-data-path.md` (what's in use), `meta-graph-v24-provider-key-audit.md` (Graph v24 verification).

This is the forward plan. The SLB organic-engagement fix (edge-sourced followers + reactions/comments/shares,
no `read_insights`) is **done and shipping**; everything below is what comes next, sequenced by value and risk.

## Now → Next → Later

### NOW (shipping in this PR)
- Edge-sourced organic engagement ingestion (`engagement_edges.py`) wired into `slb_backfill_meta_reporting`.
- Data-path map + Graph v24 verification docs.

### NEXT (highest leverage, unblocked)
1. **Config-driven report layout (foundation for drag-and-drop).**
   - Define a layout schema: `[{ id, type: 'kpi'|'bar'|'line'|'table'|'map', metric, x, y, w, h, options }]`.
   - Render it from the existing viz kit (`KpiTile`, `DistributionBar`, `PieComposition`, `DataTable`, `GaugeRing`, `BubbleScatter`).
   - Convert the SLB report to this schema → instantly cleaner + consistent, and it's the substrate the editor edits.
2. **Unblock SLB export truthfully.** Either let follower history accrue (monthly snapshots), or set the
   follower-comparison widget's `coverage_policy` to `render_with_warning` so the report exports now with the
   real current value + a "no prior-period comparison" caveat. No faked data either way.

### LATER (bigger builds / external gates)
3. **Drag-and-drop view editor** on the config-driven layout (`react-grid-layout`): drag, resize, add/remove
   widgets, a widget palette + metric picker, save per-user / per-tenant views. Reuses the existing dashboard
   builder + saved-dashboard plumbing.
4. **Instagram (App Review gated).** `@StudentsLoanBureau` (page-backed IG `17841404080986070`) is linked but
   unreadable — the app needs `instagram_basic` (+ `instagram_manage_insights`). Path: submit Meta App Review →
   un-filter the scopes in `DEFAULT_META_LOGIN_IGNORED_SCOPES` → SLB re-consents → ingest IG media + engagement
   (mirror `engagement_edges.py`). Also add `page_backed_instagram_accounts` to `list_pages` discovery.
5. **`read_insights` decision.** Reach/impressions/clicks need it (App Review). Decide: pursue it, or ship the
   report on followers + engagement only (recommended for now).

## Refactor pass (do as ONE focused sweep, not piecemeal)
From `meta-reporting-data-path.md` — none are breakage; bundle them:
1. Dedupe `REQUIRED_INSIGHTS_SCOPES` + `_missing_insights_scopes` (`meta_page_views.py` ↔ `page_insights_views.py`) into a shared leaf module.
2. Verify/remove `legacy_source_config` in `views.py` (currently still a live fallback — confirm before removing).
3. Decide the fate of the `/insights` sync path once `read_insights` is settled (overlaps the edges path for engagement).
4. Add a `callable_no_data` metric state so "supported" stops meaning "callable but empty".
5. General dead-code sweep across `integrations/` flagged during the refactor.

## Guardrails carried forward
No `read_insights`/IG scopes un-filtered before App Review (would break live FB login). No faked values. No live
Meta calls in preview/export. Tenant-scoped, aggregate-only. Never log raw tokens.
