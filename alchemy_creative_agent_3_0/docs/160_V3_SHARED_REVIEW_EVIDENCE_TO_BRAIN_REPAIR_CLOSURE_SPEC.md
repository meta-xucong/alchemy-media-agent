# Doc160 — V3 Shared Review Evidence to Brain Repair Closure

## Status

Implementation specification for the shared Human Realism retry boundary. It
does not add a child, apparel, E-Commerce, Photography, Professional, or
provider-specific capability. It does not reopen the accepted Human Realism
semantic contract, the Vision quality gate, or the bounded retry budget.

## Finding

The local M5 front-stage evidence proved that the real Provider and shared
Vision path were functioning, but every candidate remained retryable. The
reviewer returned useful visual observations, while the retry handoff retained
only broad normalized dimensions such as `human_skin_or_retouch` and
`human_rendering_artifact`. The next Brain pass therefore received ownership
and quality obligations, but not the short explanation of what the reviewer
actually saw.

This is a feedback-fidelity gap, not permission to construct a local repair
prompt. A broad issue dimension remains necessary for routing and accounting;
it is not sufficient as the only creative evidence for a whole-direction
rewrite.

## Decision

The shared review package may carry a small, bounded set of provider-neutral
observations from a retryable Vision result to the next Remote Brain final
sign-off. The observations are evidence only:

```text
generated pixels
  -> Vision/hybrid review
  -> normalized issue dimensions + bounded visual observations
  -> Remote Brain interprets the evidence
  -> Remote Brain authors one complete replacement direction
  -> existing Provider / Local MCP parity path
```

The runtime may trim, deduplicate, bind, hash, and audit these observations.
It must not classify their wording, turn them into positive or negative
prompt fragments, choose a face/expression/skin treatment, or apply a local
repair. The Brain remains the only author of the final renderer prompt.

## Contract

For each retryable candidate, the shared signal may retain at most four short
observations, each at most 240 characters after whitespace/control-character
normalization. The retry provenance may forward at most eight deduplicated
observations for the whole next Brain call. Candidate IDs, file paths, raw
Vision responses, credentials, hidden reasoning, and complete prompts are not
forwarded as creative evidence.

The finalization context labels the field `observed_review_evidence` and
explicitly marks it as untrusted visual evidence. The Brain must interpret it
against the frozen user intent, reference truth, capability contract and
review evidence, then author or retain the complete canonical prompt. The
field is absent when no retry is active or no observation was supplied.

## Boundaries

- The Vision provider still decides pixel findings and certification.
- The existing generic issue dimensions still decide retry ownership.
- The existing one bounded retry and append-only history remain unchanged.
- A missing, malformed, metadata-only or unverified review remains
  non-certifying.
- No local expression, complexion, skin, age, camera, pose, or style wording
  is added.
- General, E-Commerce, Photography and Professional use the same shared
  evidence transport and retain their existing isolation and ownership rules.
- Local MCP receives the exact Brain-signed prompt/reference result; it does
  not reinterpret this evidence or replan.

## Required regression

1. Vision observations are bounded and retained only on retryable candidate
   signals.
2. Enforced Brain-signed retries forward observations as evidence and never as
   local prompt/negative/retry fragments.
3. The canonical finalizer receives the evidence and remains the sole prompt
   author; product-only and non-retry paths remain unchanged.
4. Observation text cannot carry paths, credentials, raw responses or hidden
   provider metadata through the public delivery surface.
5. General, E-Commerce, Photography and Professional isolation, canonical
   prompt parity, review withholding and existing retry contracts remain green.

## Acceptance state

Doc160 is code-accepted only after focused shared-review/Brain tests, complete
V3 regression, static checks and a local controlled comparison demonstrate that
the retry path can consume the evidence without relaxing the pixel gate or
creating a second creative-authoring path. A visual quality pass is not
claimed merely because the transport contract passes.
