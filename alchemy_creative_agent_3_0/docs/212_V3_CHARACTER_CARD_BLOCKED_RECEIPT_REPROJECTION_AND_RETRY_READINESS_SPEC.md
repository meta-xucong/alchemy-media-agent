# Doc212 — Character Card blocked receipt re-projection before confirmed retry

## Scope

Doc212 closes the compatibility gap left by real validation runs that generated and reviewed a Character Card candidate
before Doc211 started persisting blocked-stage shared review receipts on the card itself.

It applies only to blocked Character Card stages whose official job/output/review records already exist. It does not
create images, call Brain, materialize MCP handoffs, change prompts, loosen review thresholds, or select winners.

## Root cause

The official Product API job can contain:

- a generated output;
- a verified shared Vision review package;
- structured laugh-expression score dimensions and framing deltas.

But an older blocked card checkpoint may still have `last_shared_runtime_failure = null` because the stage then paused on
a later MCP operation ambiguity before Doc211's persistence rule existed.

That made a reviewed pixel look the same as an unreviewed transport failure. Doc210 correctly refuses an early confirmed
ambiguity retry without the shared failure receipt, so the missing projection must be repaired through a formal
reconciliation step instead of by generating more images.

## Intended behavior

Before `retry_failed_slot=true` starts a new confirmed retry round:

1. the lifecycle asks the production shared-runtime host to re-project any missing blocked-stage receipt;
2. the host scans existing official job records for the failed asset/module/slot/candidate/round;
3. each recovered candidate must still pass canonical prompt/reference parity and shared review binding;
4. recovered review receipts are projected through the same `CharacterCardSharedRuntimeFailureReceipt` schema used by a
   fresh blocked stage;
5. if no reviewed candidate can be recovered, the card remains unchanged and Doc210 continues to fail closed;
6. if a receipt is recovered, the retry round may proceed only with explicit user confirmation and no pending handoff.

## Authority

The official job record and `post_generation_review_package.inspections` remain the pixel-review authority.

The card's `last_shared_runtime_failure` is a projection of that authority, not a separate reviewer result. Re-projection
must preserve the same public shared review receipt fields and must not expose prompt text, local paths, private handoff
payloads, provider responses, or raw image bytes.

## Non-goals

- Do not promote recovered candidates to winners.
- Do not bypass three-candidate comparison or shared winner selection.
- Do not consume or materialize pending MCP handoffs.
- Do not treat prompt preflight approval as pixel-level review evidence.
- Do not retry automatically.

## Regression requirements

Tests must prove:

- a blocked card with missing `last_shared_runtime_failure` can re-project an existing reviewed laugh candidate into a
  sanitized failure receipt;
- lifecycle retry calls this recovery before `begin_failed_slot_retry`;
- the retry guard still rejects ambiguity when no reviewed receipt can be recovered;
- Provider and MCP continue to use the same shared receipt path after candidate readback.
