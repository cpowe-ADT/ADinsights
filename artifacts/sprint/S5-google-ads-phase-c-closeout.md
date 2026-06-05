# Sprint 5 Phase C — Google Ads Finish (T1-03 Phase C) — Partial Closeout

**Inputs cited:** `finish-google-ads.v2.md §Phase C gate`, Phase B closeout (`S5-google-ads-phase-b-closeout.md`), `S5-google-ads-state.json`.

**Baseline commit:** `4e1733ec` (Phase B closeout final commit).

## 1. Status: **AMBER (C3 blocked on credentials; C1/C2 shipped green)**

Two of three Phase C tasks shipped atomically. GA-C1 (integration test suite) and GA-C2 (runbook + CLAUDE.md update) are both complete with green gates. GA-C3 (staging regression) is **blocked** per v2 protocol — it requires staging Google Ads OAuth credentials and a test tenant with linked customer_ids, which have not been surfaced.

## 2. Commits on `main`

- `37ff1b77` — `docs(google-ads): GA-C2 operations runbook + CLAUDE.md status update`
- `81df0c18` — `test(google-ads): GA-C1 integration test suite for 10 tab sections`

## 3. File register

### New documentation

| File                                     | Change                                                                                                                                                                                                                                                                   | LoC |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --- |
| `docs/runbooks/google-ads-operations.md` | NEW — operations runbook (10 `##` sections: Scope, SDK-vs-Airbyte hybrid architecture, Endpoint register table, Day-2 operations (tenant onboarding triage, pacing cache invalidation, LOCAL-ONLY dismiss posture, saved-view drift banner), Known quirks, Related docs) | 96  |
| `CLAUDE.md`                              | "Google Ads SDK migration in progress" → "Google Ads surface complete through Phase B (SDK primary, Airbyte fallback); see docs/runbooks/google-ads-operations.md"                                                                                                       | ±1  |

### New integration tests

| File                                                                                           | LoC | Branches covered            |
| ---------------------------------------------------------------------------------------------- | --- | --------------------------- |
| `frontend/src/components/google-ads/workspace/__tests__/AssetsTabSection.integration.test.tsx` | 58  | loading / empty / populated |
| `…/CampaignsTabSection.integration.test.tsx`                                                   | 76  | loading / empty / populated |
| `…/ChangesTabSection.integration.test.tsx`                                                     | 61  | loading / empty / populated |
| `…/ConversionsTabSection.integration.test.tsx`                                                 | 95  | loading / empty / populated |
| `…/OverviewTabSection.integration.test.tsx`                                                    | 91  | loading / empty / populated |
| `…/PacingTabSection.integration.test.tsx`                                                      | 60  | loading / empty / populated |
| `…/PmaxTabSection.integration.test.tsx`                                                        | 61  | loading / empty / populated |
| `…/RecommendationsTabSection.integration.test.tsx`                                             | 77  | loading / empty / populated |
| `…/ReportsTabSection.integration.test.tsx`                                                     | 86  | loading / empty / populated |
| `…/SearchTabSection.integration.test.tsx`                                                      | 79  | loading / empty / populated |

**Totals:** 12 files created/modified, +744 test LoC + 96 doc LoC + 1 CLAUDE.md line.

## 4. Final gate matrix

| Gate                                     | Command                                                                                     | Result                           |
| ---------------------------------------- | ------------------------------------------------------------------------------------------- | -------------------------------- |
| Phase C gate — runbook section count     | `grep -c "^##" docs/runbooks/google-ads-operations.md`                                      | **PASS** — 10 ≥ 4                |
| Phase C gate — integration test count    | `ls frontend/src/components/google-ads/workspace/__tests__/*.integration.test.tsx \| wc -l` | **PASS** — 10 ≥ 10               |
| Phase C gate — CLAUDE.md status updated  | `grep -c "migration in progress" CLAUDE.md`                                                 | **PASS** — 0                     |
| Frontend lint                            | `cd frontend && npm run lint`                                                               | **PASS** — 0 errors, 0 warnings  |
| Frontend build                           | `cd frontend && npm run build`                                                              | **PASS** — `✓ built in 4.04s`    |
| Frontend vitest (workspace `__tests__/`) | `cd frontend && npx vitest --run src/components/google-ads/workspace/__tests__/`            | **PASS — 57/57** across 16 files |

## 5. Contract checks

| Contract                                                 | Location                                                                                                                                                                             | Verified                                       |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------- |
| Each tab section has an integration test file            | 10 files under `workspace/__tests__/*.integration.test.tsx`                                                                                                                          | ✓                                              |
| Each integration test covers loading / empty / populated | `describe('<TabName> — integration', …)` × 3 `it(…)`                                                                                                                                 | ✓                                              |
| Runbook documents SDK-vs-Airbyte dual path               | §SDK-vs-Airbyte hybrid architecture                                                                                                                                                  | ✓                                              |
| Runbook documents endpoint register                      | §Endpoint register (17-row table)                                                                                                                                                    | ✓                                              |
| Runbook documents LOCAL ONLY dismiss posture             | §Recommendation dismiss posture                                                                                                                                                      | ✓                                              |
| Runbook documents whitelist maintenance cost             | §Saved-view drift banner                                                                                                                                                             | ✓                                              |
| Phase A + B owned tests continue passing                 | `ChangesTabSection.pagination`, `ReportsTabSection.driftBanner`, `PacingTabSection.campaigns`, `RecommendationsTabSection.dismiss`, `ReportsTabSection.polling`, `WorkspaceKpiStrip` | ✓ — all 6 pass alongside new integration tests |

## 6. GA-C3 blocker detail

Per `finish-google-ads.v2.md §Phase C` the staging smoke (GA-C3) requires credentials that agents cannot self-provision:

- A staging Google Ads OAuth refresh token with access to at least one live customer_id
- A staging-tenant row in the ADinsights database wired to that OAuth connection
- Enough real ad traffic on that customer_id to exercise campaigns / keywords / assets / conversions / change events in the last 30 days

The v2 prompt explicitly instructs: _"C3 requires test-account credentials — escalate to user before starting."_ Recording as `status: "blocked"` in `S5-google-ads-state.json` with a blocker entry. Work cannot proceed until the user surfaces these credentials.

**Unblock path:** user provides staging credentials (or confirms they should be pulled from a named secret store), then re-run `/finish-google-ads.v2` with `GA-C3` as the only remaining task — the state-file resume protocol will pick it up from the blocker.

## 7. Deviations from design

- No architect doc for Phase C. The v2 prompt's Phase C section is descriptive enough (integration test pattern, runbook section count target, CLAUDE.md grep target) that a separate design doc would be overhead. Phase A and Phase B each warranted one because the backend + frontend contracts needed explicit alignment; Phase C is all additive documentation + tests.
- Integration test fixture type: each test file uses a minimal `as unknown as SummaryRecord` / similar cast where the full response type has many optional fields. Documented inline.

## 8. Follow-ups

- **GA-C3 staging regression** — blocked as documented. Unblock = user provides credentials.
- **Integration test expansion** — current tests cover 3 render branches per tab. Deeper interaction tests (click → detail row, filter → refetch, hover → tooltip) are still narrower than owned Phase A+B tests. Could be expanded if tab-level regressions start surfacing in QA, but scope cap held at the v2 gate (≥10 files, 3 branches each).
- **Runbook whitelist-drift alert** — the `KNOWN_FILTER_KEYS` / `KNOWN_COLUMN_KEYS` maintenance cost is documented. If we add saved-view persistence changes often, a CI grep that diffs the whitelist against the saved-view serializer could preempt the drift banner false-alarm case.

## 9. Verdict

**AMBER — T1-03 Phase C ships two of three tasks green; third is credential-blocked as anticipated.** GA-C1 and GA-C2 both land atomically with passing gates (30 new tests, 10 runbook sections, 0 "migration in progress" hits in CLAUDE.md, frontend lint+build clean, 57/57 workspace vitest pass). GA-C3 is `status=blocked` in state.json with a blocker entry; unblock requires user to surface staging Google Ads OAuth creds. No schema changes. No migrations. Rollback trivial (revert the 2 commits).

Overall T1-03 (Phases A + B + C1/C2) ships approximately **95% of the planned Google Ads finish scope**; the remaining 5% is the external-dependency-gated staging smoke.

---

## Addendum — 2026-04-23 — GA-C3 deliverable prepared

At user direction (after the AMBER close), a full operator-runnable staging-regression checklist shipped as `S5-google-ads-phase-c-staging-smoke-checklist.md`. The checklist does **not** execute the regression (still blocked on credentials) but packages everything needed to execute it as a zero-judgment walkthrough:

- **Pre-flight** table listing every credential / access item required (OAuth refresh token, tenant id, customer_ids, JWT, frontend/backend URLs, DB shell, Redis access). Explicit "stop here if any item missing" instruction.
- **Phase 1** — 6 health + connection sanity checks with exact curl commands.
- **Phase 2** — per-tab smoke for all 10 tabs, each covering both UI render + underlying API + tenant isolation, plus Phase-A-specific (pacing cache, dismiss audit, export polling) and Phase-B-specific (`next_cursor` pagination, saved-view verify) verification steps.
- **Phase 3** — 6 cross-cutting checks (auth required, cross-tenant pk → 404, no 5xx, adapter flag isolation, whitelist drift sanity).
- **Phase 4** — record-results procedure that includes the exact state.json and punchlist updates to make when the regression passes (or fails).
- **Triage cheat sheet** mapping 7 common failure symptoms to the first thing to check.

When credentials arrive, an agent re-running `/finish-google-ads.v2` with GA-C3 as the only remaining task can walk the checklist top-to-bottom and close out T1-03 at 100%. State file still reads `GA-C3: blocked` because the _execution_ has not happened — the deliverable is the _plan for execution_, not the execution itself.
