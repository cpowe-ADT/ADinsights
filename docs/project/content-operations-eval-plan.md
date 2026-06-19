# Content Operations Eval Plan

Status: partially implemented eval contract
Related:

- `docs/project/content-operations-meta-publishing-spec.md`
- `docs/project/content-operations-api-contract.md`

Timezone baseline: `America/Jamaica`
Last updated: 2026-06-06

## Purpose

Define repeatable evals for AI captions, AI graphics, approvals, scheduler behavior, reporting
privacy, exports, and readiness separation.

## Eval Principles

- AI output can create draft versions only. It cannot approve, schedule, or publish.
- Local deterministic tests own safety invariants.
- Model/provider evals measure generation quality and regression risk.
- Every eval fixture must be tenant-safe and contain no real secrets or raw client PII.
- Failing evals should block provider tuning and production rollout.

## Eval Suites

| Suite                         | Ticket      | Owner         | Gate                                                                                      |
| ----------------------------- | ----------- | ------------- | ----------------------------------------------------------------------------------------- |
| Caption schema                | CO-3A       | Sofia         | Implemented deterministic schema tests; live provider outputs must stay 100% schema-valid |
| Caption brand fit             | CO-3E       | Sofia + Omar  | >=90% reviewer/model pass                                                                 |
| Caption safety                | CO-3E       | Nina + Sofia  | 0 critical policy failures                                                                |
| Prompt redaction              | CO-3B       | Nina          | Implemented deterministic no-secret tests; 0 secret-like leaks                            |
| Caption golden fixtures       | CO-3E       | Omar + Sofia  | Implemented local fixture harness; provider/model quality scoring remains future tuning   |
| Graphic technical QA          | CO-3C       | Sofia + Joel  | >=95% dimension/nonblank pass                                                             |
| Approval integrity            | CO-4A       | Sofia         | 100% approved-version invariant pass                                                      |
| Scheduler correctness         | CO-5D/CO-7D | Leo           | 0 duplicate publish attempts                                                              |
| Instagram container lifecycle | CO-7D       | Leo + Maya    | 100% deterministic state transition pass                                                  |
| Readiness separation          | CO-1D/CO-2E | Maya + Lina   | all axes independently covered                                                            |
| Aggregate reporting privacy   | CO-6B       | Sofia + Priya | 0 user-level fields                                                                       |
| Export packet fidelity        | CO-4D/CO-4E | Sofia + Lina  | exported artifact matches approved snapshot                                               |

## Golden Fixture Set

Implemented by `CO-3E`.

Fixture location:

- `backend/tests/fixtures/content_ops/caption_eval_cases.json`

Harness location:

- `backend/content_ops/evals.py`

Current caption fixture file covers:

- Facebook caption with required terms.
- Instagram caption schema.
- Blocked-term failure.
- Missing required-term failure.
- Invalid provider schema failure.
- Secret-like prompt redaction.
- Multi-candidate generated-draft output with no publish side effects.

Program-level fixture roadmap still includes:

- Jamaican retail weekend promotion with required terms.
- B2B service thought-leadership post.
- Restaurant/event announcement with date and address.
- Regulated/healthcare-like claim prompt that must be flagged.
- Prompt containing blocked terms.
- Prompt containing secret-like values that must be redacted.
- Instagram short caption with hashtags.
- Facebook longer caption with CTA and URL.
- Single-image graphic batch in 1:1, 4:5, and 1.91:1 formats.
- Missing Meta auth readiness.
- Page selected but Instagram not linked.
- Instagram permission missing.
- Approved draft edited after approval.
- Due schedule locked by another worker.
- Instagram container expired before publish.
- Meta retryable rate-limit error.
- Meta terminal permission error.
- Reporting linked but metrics unavailable.

Fixture rules:

- no real client names unless they are synthetic
- no real secrets, tokens, signed URLs, or credentials
- every case declares expected platforms, required terms, blocked terms, and expected result class
- every expected failure uses stable `content_ops.generation` failure codes
- fake provider outputs are embedded or generated locally; the harness does not call OpenAI or any
  network provider

## Caption Output Contract

Caption evals validate this structure:

```json
{
  "candidates": [
    {
      "platform": "facebook_page",
      "caption": "string",
      "hashtags": ["string"],
      "cta": "string",
      "alt_text": "string",
      "risk_flags": ["string"],
      "quality_score": 0.0
    }
  ],
  "warnings": []
}
```

## Deterministic Backend Tests

Implemented tests as of 2026-06-06:

- caption generate endpoint creates a tenant-scoped queued caption job
- caption generate endpoint rejects cross-tenant briefs
- raw prompt and secret-like values are redacted from returned job payloads
- injected fake provider success creates `generated` drafts and active versions
- generated caption output does not create approvals, schedules, publish attempts, published posts,
  or metric rows
- invalid provider schema marks the job failed with `caption_schema_invalid` and creates no drafts
- blocked terms mark the job failed with `caption_policy_blocked`
- required terms missing from all candidates mark the job failed with `required_terms_missing`
- cancelled jobs are no-op and do not call the provider
- default disabled provider fails closed with `provider_not_configured`
- generated `platform_overrides` contain only safe structured metadata
- caption golden fixture harness runs fixture cases and reports expected versus actual failures
- caption quota tests block active-job and rolling candidate limit overruns before provider handoff

Required future deterministic/model evals:

- approval snapshots supersede after draft edits
- schedule rejects unapproved versions
- publish attempt idempotency prevents duplicates
- Instagram expired container causes recreation path
- reporting serializers reject user-level fields
- readiness payload keeps all axes separate

## Visual/Graphic Checks

Generated graphics must pass:

- decodable image bytes
- nonblank pixel check
- expected aspect ratio
- minimum resolution per format
- text legibility/manual review flag
- moderation status captured
- safe asset metadata stored

## CO-3E Acceptance

CO-3E is done:

- fixture cases cover at least: required term pass, blocked term failure, missing required term
  failure, secret-like prompt redaction, Facebook caption schema, Instagram caption schema, and
  no-side-effect draft generation
- a single local command or pytest file runs all caption fixtures without network access
- failure output reports fixture ID, expected result, actual result, and stable failure code
- passing fixture output creates generated drafts/versions only in test DB state
- docs identify the harness as deterministic safety coverage, not as human approval

CO-3E must not:

- activate a live model/provider
- score creative quality through a remote model
- generate graphics
- approve, schedule, publish, or refresh metrics

## Release Gates

MVP gate:

- deterministic caption schema tests green
- deterministic prompt redaction tests green
- approval integrity green
- export fidelity green
- aggregate reporting privacy green

Provider activation gate:

- golden caption fixture harness exists
- live provider remains disabled by default
- provider output passes schema, blocked-term, required-term, and no-secret tests
- caption cost/tenant quota policy is documented and enforced; graphics/provider billing budgets
  remain disabled until later review
- generated output still creates editable drafts only

Facebook publishing gate:

- Page publish staging evidence exists
- scheduler duplicate-dispatch tests pass
- failure states visible in UI/runbook

Instagram beta gate:

- media URL fetch proof exists
- container lifecycle tests pass
- App Review evidence exists
- retry/expiry states visible in UI/runbook

Production gate:

- all eval suites pass or exceptions are documented
- runbooks and evidence are complete
- Raj/Mira and stream owners sign off
