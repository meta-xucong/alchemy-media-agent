---
name: alchemy-local-run
description: Run an explicitly selected Alchemy Codex Local Mode development job through the local MCP adapter without changing Web Mode.
---

# Alchemy Local Mode Run

Use this skill only when the user explicitly selects Alchemy Codex Local Mode.
It is not a Web Mode fallback and must never be invoked because a provider,
Central Brain, or gateway call failed.

1. Call `create_local_job`, then inspect `get_render_contract`.  Preserve the
   frozen intent, role count, reference ownership, capability envelope, and
   constraint ledger.
2. Record one natural-language whole-image creative direction for each frozen
   role with `record_creative_direction`.  Do not write slot recipes, crop
   coordinates, `CopyRenderPlan`, fonts, OCR, safe areas, canvas overlays, or
   fixed photography camera/pose/lighting recipes.
3. For Phase B2, call `render_platform_candidate` only after the user has
   explicitly chosen Local Mode and supplied `live_platform_opt_in=true`.  The
   adapter uses a dedicated key file configured by
   `ALCHEMY_CODEX_LOCAL_IMAGE_API_KEY_FILE`; never read or forward Codex
   sessions, root `.env`, Web Provider keys, browser cookies, or UI caches.
4. The adapter always calls the fixed official endpoint
   `https://api.openai.com/v1/images/generations` with `gpt-image-2`.  Do not
   supply a base URL, request Aiself, use a Web Provider fallback, or invoke a
   Codex CLI subprocess.  It makes one API request per frozen role.
5. Do not call an artifact-import tool with a local path.  Only the adapter's
   just-materialized official API response may be imported and bound to a job
   role.  A preview, cache, session object, or arbitrary system file is not a
   valid artifact.
6. This Phase A--B2 adapter cannot certify, review, retry, or deliver an image.
   Treat `shared_runtime_integration_pending`, `metadata_only`, `manual`, and
   `blocked` as non-delivery states.  Do not claim a Provider Gate, Gate D,
   Photography P10, or E-Commerce Gate C/D result.

The required B2 provenance is immutable: `execution_channel=codex_local`,
`creative_direction_owner=codex_local_agent`,
`renderer=platform_openai_gpt_image_2`, and `renderer_model=gpt-image-2`.
It proves a dedicated Platform API request, not a Codex/ChatGPT login-state
export and not any existing production Gate result.
