# Regional AI Content Agents — Backlog / Next Tasks

The core feature shipped in PR #395 (merged to `main`, commit `735b3584`), default-off.
This is the running backlog of what's left and what's next. Nothing here blocks the
merged build; it's all forward work.

---

## A. Finish & validate (deferred from PR #395)

1. **Live provider smoke test** — the whole feature has only ever run against mocked
   HTTP. In a gated/staging env, follow `docs/runbooks/content-operations-ai-generation.md`:
   set a real key, flip one provider on, generate one caption + one image, confirm an
   `AIUsageRecord` row. This is what turns "should work" into "confirmed working".
2. **Frontend: surface async image-job failures** — `RegionalAgentsPage` shows "queued"
   and never reports if the job later fails (provider not configured, error, quarantined).
   Poll `GET /generation-jobs/{id}/` (or list) and show failed/quarantined outcomes.
3. **Image → publish E2E test** — generate image → attach `MediaAsset` to a draft version
   → run publish preflight to `ready` (with `CONTENT_OPS_PUBLIC_MEDIA_BASE_URL` set), without
   hand-injecting renditions. This is the integration gap the per-phase tests miss.
4. **Docs** — add the `docs/ops/doc-index.md` and `docs/ops/agent-activity-log.md` entries
   for the new endpoints (were blocked at merge time by unrelated uncommitted WIP on those
   files; the api-contract-changelog entry already landed).
5. **Content-plan export** — filter out quarantined / non-`available` assets so exports don't
   list unpublishable media as usable.
6. **Wire the regional-agent dropdown into the existing caption form** in `ContentOpsPage`
   (the backend already accepts `regional_agent_profile_id`; only `RegionalAgentsPage` uses it).

## B. Spend / ops hardening

7. **Monthly image spend cap** — the token cap covers text only; images are bounded by
   per-job count + job-rate quotas but have no monthly ceiling. Add one (mirror the token cap).
8. **Enterprise per-tenant BYO provider key** — `providers/factory._tenant_override` and
   `image_factory._tenant_override` are stubs returning `None`. Implement an encrypted
   per-tenant key (mirror `integrations.PlatformCredential` AES-GCM) so enterprise tenants
   bring their own key; platform key stays the metered default.

## C. Provider capability

9. **Video generation adapter** — slots into the existing `ImageGenerationProvider`
   interface (the storage layer already allows `video/*` mime + quarantine).

---

> **D and E are now fully specced** in
> [graphic-composition-spec.md](graphic-composition-spec.md) — a build-ready prompt with the
> step-by-step pipeline, the composer system prompt, the deterministic brand-overlay design,
> reference-image (image-to-image) mechanics, the safe-area contract, a full evals plan
> (deterministic-first + LLM/vision judge + live), and a 6-slice phased build order. Summaries below.

## D. NEW — Reference images sent to the image API (image-to-image)

**Goal:** let users upload reference images (and/or pick from the approved-reference library)
and send them to the image model as visual references, not just a text prompt.

- Reuse the existing `MediaAsset` library: approved references already exist
  (`is_approved_reference`, region/locale tags); add per-job uploaded references.
- Extend the image provider interface + OpenAI adapter to send reference image bytes
  (OpenAI `gpt-image-1` supports image inputs via the `/images/edits` endpoint / multipart;
  the adapter currently only does text-to-image `/images/generations`).
- Thread selected reference assets into the image generation job payload → provider sends them.
- Keep redaction/quarantine guarantees; references are bytes we already store safely.

## E. NEW — Structured prompt composition (footers, logos, client/post-type presets)

**Goal:** assemble structured sections into **one coherent image prompt** that the model
composes, then apply the literal footer text + logo deterministically.

**The sections (inputs):**
- **Base idea** — the specific creative request for this graphic.
- **Footer preset** — reusable, with fields: website URL, contact info, social handles,
  tagline, etc. Scoped/saveable so they're picked, not retyped.
- **Logo** — a logo asset + placement (`top-left | top-right | bottom-left | bottom-right | center`).
- **Client / post-type preset ("overall settings")** — standing instructions per client or
  per post type: brand colors/style, tone, do/don'ts, required disclaimers. (Conceptually an
  extension of the existing `RegionalAgentProfile.brand_voice`.)
- **Reference images** — from feature D.

**The pipeline:**
1. Structured sections → **text LLM "prompt composer"** (reuse the existing text provider) →
   ONE coherent image-generation prompt.
2. Composed prompt (+ reference images) → image provider → base image.
3. Deterministic overlay applies the exact footer text + logo (see insight below).

**⚠ Key design insight — do NOT rely on the model for literal text/logos.** Image models
render text (website URLs, phone numbers) and place logos **unreliably** — they garble text
and ignore exact positions. So build it as a hybrid:
- The **model** composes the *creative scene* and is instructed to **leave space** (e.g. a clean
  bottom band for the footer, a clear top-right area for the logo).
- The **exact footer text + the logo** are composited on afterward **deterministically**
  (e.g. Pillow overlay at the chosen position), not generated by the model.
- This gives legible, on-brand footers/logos + AI imagery. The "model makes one prompt" handles
  the creative part; the overlay handles the literal part.

**New models/config (rough):** `FooterPreset` (fields + render rules), `GraphicPreset` /
client-or-post-type standing-instructions, logo placement enum, and a `compose_image_prompt()`
service that runs the sections through the text provider. Then an overlay/compositing step in
the image pipeline.

**Open questions to settle at build time:** preset scoping (client vs post-type vs workspace);
whether footer text is always overlaid (recommended) or sometimes prompt-only; logo source
(MediaAsset) and sizing rules per placement.
