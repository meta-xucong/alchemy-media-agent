---
name: alchemy-local-run
description: Plan an explicitly selected Codex Native ImageGen request through local Alchemy MCP without changing Web Mode.
---

# Alchemy Codex Native ImageGen

Use this skill only after the user explicitly selects Alchemy Local Mode / Codex
Native ImageGen Mode.  Never use it because a Web Mode, Central Brain, gateway,
or Provider request failed.

1. For `general_template`, call `prepare_native_imagegen_plan` exactly once.
   For explicit `ecommerce_template` or `photographer_template`, call
   `prepare_frozen_specialized_native_imagegen_plan` exactly once instead. The
   Professional entry point is separate: for an explicitly selected
   Professional Mode job with server-owned People Asset selectors, call
   `prepare_frozen_professional_native_imagegen_plan` exactly once; never
   downgrade that request to General or a specialist fallback.
   specialist tool requires its documented factual/platform or structural
   profile/mode fields; never call the General tool to downgrade a specialist.
   For each image-to-image input, provide its user-authorized readable local
   `file_path` and channel. A conversation upload is equivalent only when its
   host supplies that local path; otherwise stop with the planner's public-safe
   block rather than probing a Codex cache/session or substituting an image.
2. If the plan is blocked, show the public-safe reason and stop.  Do not switch
   to another template, a web renderer, a provider, or a local workaround.
3. For every returned output, make exactly one Codex built-in image-generation
   call using that output's `imagegen_prompt` verbatim and exactly its returned
   `reference_image_paths`. Do not append, remove, summarize, translate,
   normalize, replace, re-order, or add any text or reference image. Do not add
   a static role, suite, shot family, camera distance, angle, crop rule, or
   local recipe. For E-Commerce, an opaque internal output binding is not a
   user-visible role and must not be expanded into a suite/slot/recipe. The
   Professional serial anchor-pack relay may return an existing shared root
   identity derivative plus reviewed generated-winner derivatives; treat that
   bounded reference list as authoritative and do not reconstruct or expand
   it in Codex. The
   accompanying `provider_prompt_sha256` is a parity receipt:
   it identifies the same UTF-8 final prompt that V3 Web Provider materializes
   for GPT Image 2 from the same frozen plan.
4. If the built-in image tool is unavailable, stop with
   `codex_native_imagegen_tool_unavailable`.  Do not call an external renderer
   and do not try to recover an image file from Codex internals.
5. Tell the user the resulting image is conversation-only and non-certified.
   Do not create an Alchemy artifact, candidate, review, retry, final delivery,
   continuation, or production-gate claim.

The required provenance is `execution_channel=codex_native_imagegen`,
`renderer=codex_builtin_imagegen`, and
`delivery_state=conversation_only_not_certified`.
