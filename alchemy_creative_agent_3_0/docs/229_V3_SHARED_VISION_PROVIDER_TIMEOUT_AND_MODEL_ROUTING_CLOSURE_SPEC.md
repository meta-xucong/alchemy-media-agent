# Doc229 — V3 Shared Vision Provider Timeout and Model Routing Closure

Date: 2026-07-24

## Scope

This document closes the Post-Doc228 `expression.laugh` review-only hard-stop
root cause audit. The fix belongs to the shared V3 Visual Capability Cluster,
not to Character Card, MCP materialization, prompt wording, retry budgets, or
slot activation.

## Observed mismatch

The official Character Card `expression.laugh` output already had a durable MCP
checkpoint:

- handoff: `mcp_handoff_c418461157`
- job: `job_fa644ec244`
- candidate: `candidate_442c84d60b`
- output: `v3_output_a27b83988d28f9010cd1`
- generation result: `generation_result_515f3488bd`

Doc228 review-only resume correctly rechecked the same job/output/candidate and
did not generate a new image. It also repaired the stale job-side MCP projection
from `pending` to durable `job_checkpointed`.

The run still stopped because shared Vision produced
`manual_review/unverified` with `provider_timeout`. Therefore the
`expression.laugh` slot remained empty with no `shared_runtime_receipt`, no
winner, and no activation.

## Root cause evidence

Read-only diagnostics on the same output showed:

1. Provider configuration was present. This was not a missing API key or missing
   base URL.
2. The request was `hybrid` and correctly required real Vision review.
3. The default shared Vision route selected the general OpenAI LLM model
   (`openai_llm_model`) instead of the configured V3-owned Lab Vision model.
4. With the default general LLM route, the same payload returned an empty-output
   provider error after roughly 84 seconds or hit the 90-second watchdog.
5. With the configured Lab Vision route
   (`lab_doubao_vision_model=doubao-seed-2-0-lite-260428`), the same output and
   same review metadata returned valid structured JSON in roughly 22 seconds.
6. OpenCV DNN warnings came from local identity metric fusion and are unrelated
   to the OpenAI-compatible Vision provider timeout. The stored evidence shows
   the identity metric completed successfully.

## Authoritative behavior

The shared Vision provider must choose a V3-owned vision route before falling
back to a general Brain/LLM route:

1. Explicit constructor arguments still win.
2. `V3_VISION_INSPECTION_*` environment values still win over app settings.
3. If a run already requires real Vision review and Lab Vision is enabled, use
   the Lab Vision API key/base/model for that forced shared Vision inspection.
4. Fall back to generic OpenAI/default LLM settings only when no dedicated
   Vision route is configured.

This keeps review routing in the foundation layer and avoids any Character Card
private review path. A Vision timeout or provider error still fails closed; the
fix does not convert a timeout into a pass, does not adjust thresholds, does not
add generation attempts, and does not write slot winners.

## Regression requirement

Focused tests must prove that a configured Lab Vision route makes forced real
Vision review available without relying on the general LLM route, and that the
actual OpenAI-compatible request uses the Lab Vision API key/base/model rather
than `openai_llm_model`. Ordinary non-forced review discovery remains governed
by `V3_VISION_INSPECTION_ENABLED` so tests and low-risk local checks do not
silently call external reviewers.
