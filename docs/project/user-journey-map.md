# User Journey Map (v0.2)

Purpose: capture the main user paths, page roles, and recovery actions so reporting users are never stranded without a clear route to setup or home.

## Navigation Hierarchy

- `Home` (`/`) is the launchpad for tenants, high-level navigation, and recovery when a user wants to leave reporting.
- `Dashboard shell` (`/dashboards/*`) is the reporting workspace and must always expose a visible path back to `Home`.
- `Connect socials` (`/dashboards/data-sources?sources=social`) is the canonical setup and management hub for Facebook and Instagram connections.
- `Facebook pages` (`/dashboards/meta/pages`) is the page inventory and content entry point once a social connection exists.
- `Connection status` (`/dashboards/meta/status`) is the diagnostics view for connection health and sync state.
- `Live reporting status` is driven by `GET /api/datasets/status/` and describes whether warehouse-backed dashboards are actually ready after setup.

## Journey 1 — Connect Socials From Reporting

1. User opens any dashboard route such as Campaigns, Creatives, or Budget pacing.
2. The dashboard shell shows persistent `Home` and `Connect socials` shortcuts.
3. One click on `Connect socials` opens the canonical setup hub at `/dashboards/data-sources?sources=social`.
4. From the setup hub, the user can continue to `Facebook pages`, `Meta accounts`, `Meta insights`, or `Connection status`.

## Journey 2 — Recover From Missing Meta Setup

1. User opens a Meta-dependent page such as `Facebook pages` or `Connection status`.
2. If Meta is not connected or no Page is available, the empty state shows a primary `Connect socials` CTA.
3. The same empty state also shows a secondary recovery action such as `Home` or `Facebook pages`, depending on context.
4. The user never needs to hunt through breadcrumbs or return to the launch page just to find setup again.

## Journey 3 — Restore Orphaned Meta Marketing Access

1. User opens `Meta accounts`, `Connection status`, `Facebook pages`, or a Page overview/posts screen.
2. If Page Insights is still connected but the marketing credential is missing, the UI shows `Restore Meta marketing access`.
3. One click returns the user to `Connect socials` at `/dashboards/data-sources?sources=social`.
4. The recovery flow reuses the stored Meta token when possible, lets the user confirm the page/ad-account selection, then restores provisioning and sync.
5. After recovery, Meta ad accounts become visible again and reporting routes stop showing the orphaned-access warning.

## Journey 4 — Daily Reporting Workspace

1. User opens a reporting dashboard from the dashboard shell.
2. The shell nav keeps `Home` visible as the first persistent destination.
3. The header actions keep `Connect socials` visible for setup and troubleshooting without leaving the workspace context.
4. Users can move between reporting, setup, diagnostics, and content inventory with a single obvious click.

## Journey 5 — Meta Connected, Live Reporting Not Ready Yet

1. User completes `Connect socials` and restores or reconnects Meta.
2. The product reports staged readiness instead of a generic failure:
   - `Meta connected`
   - `Direct sync complete`
   - `Waiting for warehouse snapshot`
   - `Live reporting disabled in this environment`
3. `Connection status` remains about auth/setup health only.
4. Dashboard-shell banners use dataset readiness, not social connection state, to explain why Campaigns, Creatives, Budget, or Create may still be blocked.
5. The user can tell whether the next action is:
   - wait for snapshot generation
   - enable the warehouse adapter in the current environment
   - reconnect setup if Meta itself is broken

## Failure States

- Airbyte sync failed: show alert plus runbook or diagnostics path.
- Snapshot stale: show warning banner plus retry action.
- Live reporting disabled in environment: show a clear config banner, not a generic data failure.
- Meta connected but first warehouse snapshot missing: show a staging banner instead of pretending the connection failed.
- No data because setup is incomplete: show `Connect socials` as the primary CTA and a contextual secondary CTA.
- No Facebook Pages available: keep the user on a clear path to `Connect socials`, with `Home` available as a recovery route.
- Meta marketing credential missing while Page Insights still works: show `Restore Meta marketing access` and route back to `Connect socials`.
