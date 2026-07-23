# Doc211 — Character Card blocked-stage review receipt projection

## Scope

Doc211 closes the review-evidence gap exposed after Doc209 consumed `mcp_handoff_595beb495a`.

The generated official output had a real shared Vision review package with laugh-expression dimensions, but the stage
then paused on a later MCP operation ambiguity. The blocked Character Card state did not preserve the already-reviewed
candidate receipt, making a reviewed pixel look indistinguishable from an unreviewed or missing-review failure.

## Intended behavior

When a Character Card stage blocks after one or more candidates have already reached shared review:

1. the stage remains blocked unless a winner is formally selected;
2. reviewed candidate evidence must be preserved as sanitized shared runtime failure evidence;
3. the evidence must include shared owner, prompt/reference parity, reviewed attempt count, and public review receipt
   dimensions;
4. it must not include prompt text, provider paths, raw responses, local files, or private MCP artifacts;
5. the public Character Card state must expose this sanitized failure receipt so the UI and resume logic can distinguish
   a reviewed candidate from an unreviewed transport failure.

## Authoritative rule

`post_generation_review_package.inspections` is the pixel-review authority. Prompt preflight approval is not enough.

For `expression.laugh`, the preserved public receipt must prove the shared affective-expression review contract was
present. At minimum it should preserve the receipt dimensions for mouth-eye coherence, periocular/gaze affect,
cheek-jaw coupling, age coherence, identity preservation, and face.front framing deltas when those dimensions were part
of the shared receipt.

## Interaction with Doc210

Doc210's early confirmed retry for `mcp_materialization_operation_ambiguous` is only allowed after this blocked-stage
receipt has been persisted. A retry must not hide whether previous pixels were reviewed.

## Non-goals

- Do not mark a blocked-stage reviewed candidate as winner.
- Do not bypass candidate comparison or shared winner selection.
- Do not relax shared Vision, expression, identity, or framing gates.
- Do not store raw prompts, file paths, provider responses, or private handoff payloads in public state.

## Regression requirement

Tests must prove:

- a blocked expression stage preserves a reviewed laugh receipt in `shared_runtime_failure`;
- the public Character Card projection exposes the sanitized receipt;
- ambiguous MCP retry is rejected if the persisted shared runtime failure receipt is absent.
