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
3. Before image-tool invocation, disclose the exact permitted references when
   the current Codex surface can do so.  Never read or forward Codex session
   files, auth tokens, browser cookies, provider keys, or UI caches.
4. Use the interactive Codex image tool only when it exposes a durable,
   materialized local image file readable by the adapter.  A preview-only
   result, data URL, copied cache reference, or undocumented session object is
   not a valid handoff; record the limitation and stop.
5. Import a single artifact with `import_generated_candidate`, declaring the
   exact job and frozen role.  Do not reuse an artifact across jobs or roles.
6. This Phase A--B adapter cannot certify, review, retry, or deliver an image.
   Treat `shared_runtime_integration_pending`, `metadata_only`, `manual`, and
   `blocked` as non-delivery states.  Do not claim a Provider Gate, Gate D,
   Photography P10, or E-Commerce Gate C/D result.

The required provenance is immutable: `execution_channel=codex_local`,
`creative_direction_owner=codex_local_agent`, and `renderer=codex_imagegen`.
Never call the renderer a direct `gpt-image-2` API invocation unless a future
supported surface provides verifiable provenance for that claim.
