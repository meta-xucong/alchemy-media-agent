---
name: alchemy-local-run
description: Plan an explicitly selected Codex Native ImageGen request through local Alchemy MCP without changing Web Mode.
---

# Alchemy Codex Native ImageGen

Use this skill only after the user explicitly selects Alchemy Local Mode / Codex
Native ImageGen Mode.  Never use it because a Web Mode, Central Brain, gateway,
or Provider request failed.

1. Call `prepare_native_imagegen_plan` exactly once with only the user's input,
   explicit template, requested count/size, and declarations about references
   attached in this Codex conversation.
2. If the plan is blocked, show the public-safe reason and stop.  Do not switch
   to another template, a web renderer, a provider, or a local workaround.
3. For every returned output, use `creative_direction_brief` to author exactly
   one self-contained, natural-language whole-image direction in this Codex
   conversation. The brief is not an image prompt and must not be copied as a
   structured keyword stack. Preserve its user truth, guardrails, text policy,
   and reference instructions, but do not add a static role, suite, shot
   family, camera distance, angle, crop rule, or local recipe. Then make
   exactly one Codex built-in image-generation call for that authored direction.
   When an instruction requires a conversation attachment, use that exact
   attachment; never substitute a path or another image.
4. If the built-in image tool is unavailable, stop with
   `codex_native_imagegen_tool_unavailable`.  Do not call an external renderer
   and do not try to recover an image file from Codex internals.
5. Tell the user the resulting image is conversation-only and non-certified.
   Do not create an Alchemy artifact, candidate, review, retry, final delivery,
   continuation, or production-gate claim.

The required provenance is `execution_channel=codex_native_imagegen`,
`renderer=codex_builtin_imagegen`, and
`delivery_state=conversation_only_not_certified`.
