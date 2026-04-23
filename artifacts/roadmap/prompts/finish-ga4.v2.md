# Prompt v2 — Finish GA4 Integration

**Paste the entire block below as the first message in a new Claude Code session opened at `/Users/thristannewman/ADinsights/`.**

**Why v2:** adversarial review surfaced (a) dbt models actually exist (`stg_ga4_reports.sql`, `agg_ga4_daily.sql`) — v1 implied they might not, (b) client.py dimensions diverge from mart schema — verdict investigation needs to compare both, (c) Verdict A was too attractive as an easy exit, (d) needed PII allowlist, OAuth token handling, tenant-isolation tests. v2 adds all of these + state-file resumability + CoT scaffolding.

---

```
# Identity & posture

You are a staff engineer with prior GA4 Data API v1 and Search Console shipping scars. You default to "verify what exists" before "build." You are comfortable reading dbt SQL, Airbyte configs, and Django integration modules in parallel. You know GA4 API has per-project quotas; you know OAuth access tokens expire hourly and refresh tokens must be AES-GCM+KMS encrypted per AGENTS.md §90; you know GA4 dimensions can include PII (`user_pseudo_id`, `device_id`, `ip_address`) that must NOT enter the mart. You have authority to pick between Verdicts A/B/C but NOT to escalate a C into a full new integration without the user's green light on a revised scope + budget.

# Required reading (in order)

1. `CLAUDE.md` — project guardrails
2. `AGENTS.md` — pay attention to §83 (RLS), §86 (aggregated metrics only, never user-level), §90 (OAuth token AES-GCM+KMS), §104 (structured logs), §130 (PII policy), §140 (America/Jamaica timezone)
3. `artifacts/roadmap/project-punchlist.md` §T1-04 + §T1-05 (GA4 + Search Console spec)
4. `artifacts/sprint/S4-final-closeout.md` — what shipped in Sprint 4 for the GA4 dashboard page
5. `artifacts/sprint/S4-deep-review.md` §Contract regression check — specifically R3 (web pages must NOT hit `/api/metrics/combined/`)

# Baseline state (verify before investigation)

- Commit `git rev-parse HEAD` should match `7a0e701b` or a descendant; record actual baseline in state file
- Frontend: 770 vitest, build clean, lint clean
- Backend: 727 pytest + 1 skip, ruff clean

# What's already built (starting state)

Do NOT rebuild — verify + finish:

- **Backend integration module**: `backend/integrations/google_analytics/` with `client.py`, `views.py`, `serializers.py`, `urls.py`
- **Backend adapter**: `backend/adapters/google_analytics.py`
- **Backend API view**: `backend/analytics/web_views.py:126` (`GA4WebInsightsView`) reads `agg_ga4_daily` mart with dimensions `property_id, channel_group, country, city, campaign_name` and metrics `sessions, engaged_sessions, conversions, purchase_revenue, engagement_rate, conversion_rate`
- **dbt models**: `dbt/models/staging/stg_ga4_reports.sql` + `dbt/models/marts/agg_ga4_daily.sql` (verified exist)
- **Tests**: `backend/tests/test_google_analytics_api.py` + `test_google_analytics_client.py`
- **Frontend dashboard**: `frontend/src/routes/GoogleAnalyticsDashboardPage.tsx` migrated to viz kit in Sprint 4
- **R3 contract test**: `GoogleAnalyticsDashboardPage.test.tsx` asserts `/metrics/combined/` is never called — do NOT break

**Likely verdict (read before investigating):** `backend/integrations/google_analytics/client.py` fetches via GA4 Data API v1beta with dimensions `date, sessionSource, sessionMedium, sessionCampaignName` and metrics `sessions, totalUsers, newUsers, engagementRate, averageSessionDuration, keyEvents, eventCount`. `web_views.py` reads `agg_ga4_daily` with a DIFFERENT set of dimensions/metrics. These schemas don't line up. Likely verdict is **B or C** — the SDK client runs but nothing connects it to the mart. Favor verdict B/C unless evidence clearly contradicts.

# Pre-flight verification (MANDATORY before coding)

Run these greps and paste results into the investigation doc:

1. `find dbt/models -name "*ga4*" -o -name "*google_analytics*"` — expect `stg_ga4_reports.sql` + `agg_ga4_daily.sql`
2. Read `dbt/models/staging/stg_ga4_reports.sql` fully — what's the source table? If it's `ga4.reports_raw` or similar Airbyte-populated, note the expected source system.
3. Read `dbt/models/marts/agg_ga4_daily.sql` fully — confirm dimension/metric columns match `web_views.py:29`.
4. `grep -rn "GoogleAnalyticsClient\|google_analytics" backend/integrations/tasks.py backend/integrations/celery.py` — is there a Celery task wiring `GoogleAnalyticsClient.fetch_traffic_acquisition` into persistence? If zero hits: **strong Verdict C signal**.
5. `find infrastructure/airbyte -type f | xargs grep -l "ga4\|google_analytics" 2>/dev/null` — is Airbyte configured as the source?
6. `grep -rn "ga4\|google_analytics" backend/integrations/models.py` — is there an OAuth credential model row?

# Scope fence

## In scope

- Investigate the ingestion path end-to-end
- Pick Verdict A, B, or C with binary evidence (see §Verdict criteria)
- If A or B: write runbook + add missing test coverage. Done.
- If C: write a detailed gap analysis AND STOP. Do NOT attempt full ingestion in this session — it's 1–2 weeks of work that needs a separate, scoped prompt.

## Out of scope (do not touch)

- **Search Console** — separate prompt; don't sidebar-creep into it even if you finish GA4 early
- Any structural edit to `GoogleAnalyticsDashboardPage.tsx` (data-path only)
- Any new OAuth flow that changes Google Cloud project / redirect URI config
- R3 contract — don't weaken the fetch-spy test
- Any call to `/api/metrics/combined/` from the GA4 page
- Re-writing dbt marts (if `agg_ga4_daily.sql` is broken, escalate)

# Verdict criteria (binary, evidence-required)

Paste command output directly into `artifacts/roadmap/ga4-investigation.md` to support the verdict.

## VERDICT A — "Live end-to-end"
Requires ALL four:
1. Query output: `SELECT MAX(date_day), COUNT(*), COUNT(DISTINCT property_id) FROM agg_ga4_daily WHERE date_day >= NOW() - INTERVAL '7 days'` returns ≥ 1 row, MAX within 48h, with tenant RLS set: `SET app.tenant_id = '<known_tenant_id>'` before the query (zero rows under RLS does NOT mean empty mart)
2. A live sync run completes during your investigation without error
3. Dashboard at `/dashboards/google-analytics` renders non-zero KPIs in the dev stack for at least one tenant × property
4. Runbook already exists OR you can write one in < 1 hour of investigation

## VERDICT B — "Wired but untested in this environment"
- Integration module + adapter exist
- Sync task defined but not running OR ran last > 7 days ago OR returned 0 rows last run
- Dashboard renders but empty
- Path from client.py → mart is partially wired (e.g., client exists but no Celery task; OR Celery task exists but Airbyte connector not configured)

## VERDICT C — "Not wired"
- No Celery task invokes `GoogleAnalyticsClient`
- No Airbyte connector for GA4
- Mart is empty OR doesn't have upstream data source
- Schema mismatch between client.py dimensions and mart columns is unresolved

# State-file protocol

Path: `artifacts/sprint/S5-ga4-state.json` (create only if verdict = C, since A/B fit in one session)

Schema:
```json
{
  "schema_version": 1,
  "started_at": "<ISO-8601>",
  "baseline_commit": "<sha>",
  "verdict": "A|B|C|undecided",
  "step": "investigation|verification|fix|runbook|done",
  "milestones": {
    "oauth_wired": null,
    "sync_task_wired": null,
    "dbt_model_exists": true,
    "tests_green": null,
    "runbook_written": null
  },
  "last_commit": null
}
```

For Verdict A/B, one session suffices; no state file needed, just atomic commits.

# Phased execution with hard gates

## Step 1 gate — Investigation complete

Before moving to Step 2, `artifacts/roadmap/ga4-investigation.md` must contain:
- 5 file reviews (one per entry in Pre-flight Verification)
- Explicit verdict (A/B/C) with rationale + evidence commands pasted
- If verdict = C: a 1-page gap analysis naming the missing pieces

Print: `STEP 1 COMPLETE, verdict <X>`

## Step 2 gate — Verification in dev stack

Document in the investigation doc:
- Dev stack state (`lsof -iTCP:5173 -sTCP:LISTEN` output — if no PID, launch; if non-Vite PID, escalate)
- Dashboard rendered outcome (screenshot path / DOM text / row-count query output)
- Mart row count with tenant RLS set correctly

Print: `STEP 2 COMPLETE, dashboard state <empty | populated | error>`

## Step 3 gate — Gap closed (A/B only)

- Runbook `docs/runbooks/ga4-operations.md` exists with sections [Architecture], [How to connect a GA4 property], [How to trigger a sync], [How to verify live], [Troubleshooting], [Rate limits]
- At least 1 new backend pytest covering the ingestion path (or the R3 contract, whichever is currently undertested)
- All baseline gates still green
- Commit(s) made

Print: `STEP 3 COMPLETE, final commit <sha>`

If verdict = C, do NOT proceed past Step 2 with code changes. Commit the investigation doc + gap analysis and stop.

# Chain-of-thought scaffolding at decision points

Before writing the verdict in Step 1, reason explicitly in the investigation doc:

1. List every file you read with a 1-line finding each
2. Map each file to one of {auth, sync, storage, read-path, test}
3. Name the single component that is most likely the gap (not the symptom)
4. Pick verdict A/B/C only after (1–3)
5. If (3) surfaces a "sync runs but no data in mart" pattern, favor B not A

Before writing any code in Step 3, reason explicitly about:

1. Will this edit touch anything under R3? (If yes → STOP, escalate)
2. Will this edit modify `GoogleAnalyticsDashboardPage.tsx`? (If yes → STOP, out of scope)
3. Does the test I'm about to add still pass if the implementation is deleted? (If yes, it's not a meaningful test)

# Context budget caps

- Investigation (Step 1): ≤ 20 tool calls
- Dev-stack verification (Step 2): ≤ 10 tool calls + 1 dev-stack launch
- Gap-close (Step 3): ≤ 60 tool calls for Verdict A/B
- Verdict C: investigation + gap analysis only, ≤ 40 tool calls total

If a cap threatens to exceed, pause, update state, ask user.

# Escalation triggers (stop and ask)

Start message with `ESCALATE:` and end with `Waiting for decision.`

1. Verdict = C and estimated fix effort > 1 week → out of scope for this session
2. `agg_ga4_daily` mart referenced by backend view but has no upstream source in dbt — do NOT fabricate a source table
3. OAuth flow needs a new Google Cloud project or new redirect URI (config change, not code)
4. R3 contract accidentally broken by existing code (don't silently patch)
5. Any baseline test (770 frontend, 727 backend) starts failing
6. Pre-flight grep finds PII columns (`user_pseudo_id`, `device_id`, `ip_address`, `client_id`, `stream_id`) in the mart or staging
7. Step 2 verification contradicts Step 1 verdict (max 1 revision allowed; revise twice → escalate)

# Pre-mortem

- [ ] **GA4 OAuth scopes differ between Data API and Search Console** — do NOT conflate. GA4 needs `analytics.readonly`; anything broader scares enterprise reviewers
- [ ] **`agg_ga4_daily` might be a view over Airbyte-staging rather than a physical table** — verify before assuming sync is wired in Django
- [ ] **R3 fetch-spy test may fail if you add any new apiClient import** — audit before committing
- [ ] **Multi-tenant GA4 property selection** — a tenant can own multiple GA4 properties; must test the multi-property case
- [ ] **Data API v1 has a free quota** — dev smoke tests should use cached/VCR responses, not live calls
- [ ] **OAuth token refresh** — access tokens expire hourly; integration must handle `401 refresh-needed` gracefully
- [ ] **PII leakage risk** — GA4 default schemas include `user_pseudo_id`; the mart/staging must NOT include it
- [ ] **Raw SQL under RLS returns 0 rows if tenant not set** — always `SET app.tenant_id = '<known>'` before mart queries

# Anti-patterns (reject work product)

1. Do NOT call `/api/metrics/combined/` from the GA4 page (R3 contract)
2. Do NOT rewrite `GoogleAnalyticsDashboardPage.tsx`; data-path only
3. Do NOT create a fake `agg_ga4_daily` mart or its upstream — if missing, escalate
4. Do NOT add a second OAuth flow; reuse existing Google OAuth consent where possible
5. Do NOT extend scope into Search Console unless GA4 is done AND user explicitly says so
6. Do NOT commit `.env` files or any file matching `*credentials*`, `*secret*`, `*key*.json` (run `git diff --cached --name-only | grep -E '\.env|credential|secret|key\.json'` before every commit, must return empty)
7. Do NOT skip the fetch-spy test that asserts R3
8. Do NOT include PII columns in any dbt model or Django model you add
9. Do NOT attempt full ingestion in this session if Verdict = C
10. Do NOT push to remote or open PRs — stay on local `main`

# PII allowlist (enforced)

GA4 staging and mart models may only include these columns:

`property_id, tenant_id, date_day, channel_group, country, city, campaign_name, sessions, engaged_sessions, conversions, purchase_revenue, engagement_rate, conversion_rate`

Write a dbt test (or pytest introspecting the mart schema) that FAILS if any of these appear: `user_pseudo_id, device_id, client_id, ip_address, stream_id, user_id`.

# Testing rigor

- R3 fetch-spy test stays green
- If verdict A/B and you touch the ingestion path: add ≥ 3 new backend pytest that cover (a) tenant isolation (read as tenant B, get tenant A's data? test must fail), (b) OAuth token refresh on 401, (c) PII allowlist enforcement
- No arbitrary count targets — "≥ 770 tests" is a regression floor, not an addition target

# Communication contract

**End of Step 1**
```
### Step 1 complete — Verdict <A/B/C>
Files reviewed: <5 paths with 1-line findings>
Likely gap (if B/C): <component>
Evidence: <pasted command output>
```

**End of Step 2**
```
### Step 2 complete — Dashboard state <empty/populated/error>
Mart row count (tenant-RLS'd): <number>
Live sync run: <success/fail/not-attempted>
```

**End of Step 3 (or stop for Verdict C)**
```
### Step 3 complete
Verdict: <A/B/C>
Commits: <sha list>
Runbook: docs/runbooks/ga4-operations.md
New tests: <count> covering <areas>
Gate matrix: <✓/✗>
Self-eval: <pasted checklist>
```

**Escalation**
```
ESCALATE: <threshold hit>
Context: <1-2 sentences>
Options: (a) ... (b) ... (c) ...
Waiting for decision.
```

# Commit discipline

- Commit per milestone (investigation-doc commit, verification-evidence commit, runbook commit, test commits)
- Conventional prefix: `docs(ga4):` for investigation/runbook, `feat(ga4):` or `fix(ga4):` for code
- Co-Authored-By trailer matching recent commits (`git log --format=%B -n 3 main`)

# Global Definition of Done

- [ ] `artifacts/roadmap/ga4-investigation.md` exists with verdict + evidence
- [ ] If Verdict A/B: dashboard at `/dashboards/google-analytics` renders real data OR a documented empty state with visible explanation
- [ ] If Verdict C: investigation doc contains a 1-page gap analysis + you stopped and escalated
- [ ] Runbook `docs/runbooks/ga4-operations.md` exists (new or updated) with required sections
- [ ] R3 contract still holds (fetch-spy test green)
- [ ] Baseline gates green (770 frontend, 727 backend)
- [ ] Commits have conventional prefix + Co-Authored-By trailer
- [ ] Self-evaluation pasted at top of investigation doc

# Self-evaluation (paste at top of investigation doc)

```
- [ ] Every DoD bullet has a matching evidence line
- [ ] R3 fetch-spy test output pasted (confirms green)
- [ ] Runbook opens clean and includes "how to verify live" one-liner
- [ ] Commits use conventional prefix
- [ ] State file removed (A/B) or marked for handoff (C)
- [ ] One-line answer: what did I change and why is it safe? — <answer>
- [ ] If Verdict C: I did NOT attempt full ingestion; I escalated.
```

# First response (before any code)

Respond with ≤ 250 words:

1. 2–3 sentence summary of what you read (cite specific file paths)
2. Pre-flight grep results (all 6 from the Pre-Flight section)
3. Your verdict (A/B/C) with brief rationale
4. Planned work items in order, with rough effort per item
5. Any clarifying questions (or "no questions, proceeding")

Then proceed autonomously. Expect 1–5 working days if Verdict A/B; if Verdict C, expect Step 1+2 only in this session and a separate multi-week prompt afterward.
```
