# Native frozen cloud continuation correction

The Bridge marker intentionally blocks ordinary Generate. Removing it would
bypass the original frozen intent and development delivery gate. The owning
layer is a narrow authenticated gateway plus native service continuation, not
Brain replanning or global provider routing.

The continuation uses the configured ProductionImageGenerationProvider and its
existing retries, with a deterministic output checkpoint and frozen prompt,
ordered references and rendering-option checks. Gateway and coordinator latch
execution before calling the provider. An unknown result is queried, never
regenerated. A persisted output can resume native projection and shared review.
The guarantee is one continuation invocation, not one upstream request: existing
provider retry policy remains authoritative and upstream charges may occur even
though V3's internal zero-credit adapter does not charge credits.

Owner, current target, reference admission, scenario/capability and existing
balance checks remain authoritative. Routing policy separately requires cloud
cost and reference-egress authorization. Default Generate stays blocked for
Bridge plans. Both routes are development review-only; no selection, export,
formal delivery or memory promotion is granted by cloud fallback.

Validation uses mocked transport and review only, never real credentials or paid
providers. Real local integration and provider billing acceptance remain separate.

## Implemented seam and boundaries

`NativeRenderBridgeGateway.cloud_admission` performs read-only preflight;
`cloud_execute` persists its independent per-target execution latch before the
configured provider call; `cloud_status` never renders. An absent native latch
reports `not_started`; an existing latch without pixels reports `cloud_unknown`
and is not retry-safe. Coordinator authorization and its own durable route latch
must precede execution. Receipt import and cloud continuation share a target lock
and reject a competing journal. After cancellation, only an already projected
checkpoint can be reported; no new projection or review is performed.

Native service admission retains the current scenario/capability and balance
checks and rejects unverified non-stub billing adapters. This does not certify
external provider affordability or grant material-egress permission. The
coordinator must bind explicit user cost/material consent to the request.

The provider adapter compares the actual configured request against the frozen
Brain prompt, all image options and ordered reference identities/bytes. The
provider retry implementation remains inherited. Checkpoint recovery rebuilds
only the native candidate projection from stored pixels and uses existing
review-only finalization. Ordinary Generate remains blocked on the original
Bridge marker, and public final-delivery projection withholds cloud development
outputs just as it withholds local Bridge development results.
