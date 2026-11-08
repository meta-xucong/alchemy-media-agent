# V3 output-bound review and selective retry

This is shared foundation work. General and specialized deliverable maps are unchanged.

## Observed incident and correction model

The 2026-11-08 V3 job `job_26e34aacc4` finished in 969 seconds. Two original outputs
were followed by two retry outputs. Original A was only a warning. Original B's
review described polished, usable imagery and a warning, but its
`weak_aesthetic_finish` label was normalized to `fail_retryable`.

B's persisted provider direction requested a shoulder-up view with one visible
hand. Review instead penalized it against the starting thigh-length/two-hand
composition. Thus the earlier interpretation that this retry was necessarily
justified by its issue code is superseded by the exact output/review evidence.

Three boundaries needed correction:

1. Review receives the exact resolved output record's `final_provider_prompt`,
   bound by output, asset and job identity. It evaluates approved output-specific
   crop, camera, visibility and rendering style while preserving global hard
   requirements, identity/product truth and exclusions. Job-level Brain metadata
   is insufficient because it may describe an earlier attempt after merging.
2. A provider pass/warning with only generic composition/aesthetic advice stays
   a warning. Explicit aesthetic rejection and specific hard defects retain
   their existing failure gates. Confidence, manual review, required attestations
   and Doc118 final-delivery eligibility are unchanged. This narrows Doc354's
   advice normalization; it does not remove aesthetic review.
3. A genuine canonical pixel failure targets only the exact affected asset.
   Target identity is separate from Brain-owned creative wording. The complete
   plan, canonical signoff, requested count and original indexes are retained;
   only execution and packaging are scoped. Unresolved canonical target identity
   blocks that retry. Existing set-level/legacy retry behavior remains unchanged.

New outputs receive ordinary review and append-only history. Existing Doc95
winner selection composes old/new results with their own receipts. Set-level
review evaluates that composed delivery, never the sparse retry or all history.
An unchanged original is not rendered or pixel-reviewed again. Existing Doc73
continuity receipts remain authoritative, including a retry of output two.

## Response-stream findings

All four native image calls used HTTP Responses. The fourth received HTTP 200
headers, then no complete parsed SSE event for 300.029 seconds. The existing
text-stream retry recovered; exactly one image tool invocation followed.
Pre-tool times were 26.797, 23.562, 29.172 and 322.891 seconds. Native image-tool
durations were 103.735, 97.906, 45.187 and 42.641 seconds.

Pinned Codex 0.163 source streams successful response bytes directly. Its SSE
idle timer measures parsed event progress, not proof of zero TCP bytes or model
reasoning. The host uses its existing local CONNECT proxy; current unauthenticated
route probing succeeds through that proxy and fails direct. This does not identify
whether the historical stall originated upstream or during stream delivery.

Keep 300000 ms tolerance, HTTP transport, context trimming and timing telemetry.
No transport/proxy/reasoning change is justified by this evidence. Removing
unnecessary image requests reduces work and exposure to stalls; it cannot promise
a fixed duration or claim the upstream stall itself is repaired.

## Acceptance evidence

Before implementation, nine focused review assertions failed at the actual
direction/normalization seams. The subset regression failed because the runtime
did not accept execution scope. After correction, the deterministic full service
flow demonstrates two calls for usable advisory results, or three calls when
only output two genuinely fails (the prior whole-set path used four).

Focused coverage includes exact per-output/retry review direction, hard defects,
manual/confidence gates, complete two-output public delivery, append-only three
output history, mixed winner receipts, weaker retry preservation, full-plan
signoff/indexes and original continuity anchor reuse. The transport is unchanged.
Live frontend generation remains the post-deployment acceptance step; offline
results do not establish current upstream latency or image aesthetics.
