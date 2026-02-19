# CI Gate Weekly Review (Contract Required, Release Advisory)

Purpose: review CI gate efficiency and signal quality once per week before deciding whether to tighten or relax policy.

## Current Enforcement Model
- Required merge gate: `Contract guard strict check` (`/Users/thristannewman/ADinsights/.github/workflows/contract-guard.yml`).
- Advisory-only gate: `Release readiness advisory summary` (`/Users/thristannewman/ADinsights/.github/workflows/release-readiness-advisory.yml`).
- Branch protection target: require the contract check on `main`; do not require release readiness.

## Weekly Checklist
1. Count `Contract Guard CI` false positives (failed check but no real breaking contract impact).
2. Capture average runtime for both workflows over the last week.
3. Count PRs blocked by true breaking changes and docs-missing contract failures.
4. Track docs-missing CI fail rate (required contract docs omitted vs fixed in PR updates).
5. Track release-readiness `pending_items` volume and clearance rate before merge.
6. Count release-readiness advisory warnings that later mapped to real defects.
7. Record top recurring warning/pending classes and whether runbooks/docs were updated.

## Decision Rule
- If contract false positives remain low and advisory repeatedly catches high-value misses, consider tightening advisory dimensions in a future phase.
- If false positives rise or advisory quality is low, keep release readiness non-blocking and improve rules/tests before any policy hardening.

## Evidence to Collect
- GitHub Actions run history for both workflows.
- Contract guard packet artifacts.
- Release readiness packet-chain artifacts (`router`, `scope`, `contract`, `release`).
- A short notes log summarizing one concrete “saved defect” and one “noise” example.
- Weekly counts for `pending_items` categories and docs-missing CI failures.

## Owner Cadence
- Owner: Ops/AI integration lead with Raj + Mira review when policy changes are proposed.
- Cadence: weekly (America/Jamaica).
