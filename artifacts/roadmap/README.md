# Roadmap

Living source of truth for what's left to ship. Two docs, read in this order:

1. **[project-punchlist.md](./project-punchlist.md)** — every open task across the project, tiered by priority (T1 ship-blocker, T2 polish, T3 post-launch). Start here.
2. **[google-ads-completion-plan.md](./google-ads-completion-plan.md)** — phased plan specific to Google Ads (referenced from T1-03 / T2-02 in the punchlist).

## Baseline

- Last known-good commit: **`7a0e701b`** (April 2026) — ships 4-sprint viz-kit migration + Q1 accumulated workstreams
- Full gate matrix at baseline: frontend lint clean, build clean, 770/770 vitest, backend 727 pytest + 1 skip, ruff clean

## How to use this

- Pick a task from the punchlist (highest-tier + no blocking deps)
- Read its DoD + Work items
- Check tests pass before AND after your change
- Update the task's checkbox/status in-line in the punchlist
- Commit with conventional-commits prefix (`feat:`, `fix:`, `docs:`, etc.)

## When to revisit

- When starting a new planning cycle — triage unchecked tasks
- When a task completes — check it off, note any follow-ups discovered
- If scope changes — add/edit tasks here, keep it concrete

## Session prompts (for running as dedicated workstreams)

Paste these into fresh Claude Code sessions to run a full workstream end-to-end:

**Use v2 prompts** (v1 kept for history; v2 incorporates adversarial-audit fixes):
- [prompts/finish-google-ads.v2.md](./prompts/finish-google-ads.v2.md) — Google Ads 72% → ship-ready (~15–20 working days)
- [prompts/finish-ga4.v2.md](./prompts/finish-ga4.v2.md) — GA4 80% → ship-ready (~1–5 working days depending on verdict)

Paper trail:
- [prompts/AUDIT-v1-to-v2.md](./prompts/AUDIT-v1-to-v2.md) — what 4 persona reviewers found and how v2 addresses each finding

Superseded:
- ~~prompts/finish-google-ads.md~~ (v1)
- ~~prompts/finish-ga4.md~~ (v1)
