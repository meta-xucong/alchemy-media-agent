# Doc119 V3 Provider Failure Provenance: Structured 4xx Precedence Correction

Status: corrective shared-provider authority discovered during the Doc118
controlled General reference acceptance. This document changes neither
generation routing nor any template, child, apparel, product, prompt, or
review recipe.

## 0. Observed defect

Two controlled General `image_edit` requests using the authorized blue-dress
reference reached GPT Image 2 and received a terminal upstream HTTP 400 before
pixels existed. The private adapter detail correctly retained `status_code: 400`,
but the public-safe `provider_execution` projection incorrectly reported
`provider_timeout`.

The cause was textual classification: diagnostic fields such as
`operation_timeout_seconds` contain the word `timeout`, even when they merely
describe the configured deadline and `operation_timeout_exhausted` is false.
That configuration text must not override a structured upstream 4xx.

## 1. Corrected shared invariant

For terminal provider failures, classify in this order:

1. explicit structured reference-admission failure;
2. explicit structured policy signal;
3. explicit reference-rejection evidence;
4. a concrete structured 4xx other than 408/429;
5. actual timeout evidence; then
6. transport/unavailability or the existing conservative fallback.

Step 4 maps to the existing operation-scoped safe code:

```text
reference-backed image edit -> image_edit_invalid_request_unattributed
text-only image generate    -> image_generation_invalid_request_unattributed
```

It does not assert that a 400 was caused by a child, policy, prompt, parameter,
or reference. It only reports the evidence available: the image operation was
rejected before pixels were received. `provider_timeout` remains reserved for
a timeout exception or actual timeout evidence, not a timeout configuration
field embedded in diagnostics.

## 2. Boundaries

- Preserve gateway-owned retry behaviour; V3 must not add an SDK/HTTP retry.
- Preserve the Doc117 safe public schema and redaction boundary.
- Do not infer policy from an opaque 400 or from subject matter.
- Do not use this correction to reclassify a no-pixel request as reviewable,
  manually confirmable, generated, or visually failed.

## 3. Required regression

The production-provider regression must construct a wrapped terminal 400 that
contains `operation_timeout_seconds` and
`operation_timeout_exhausted: false`. It must still produce the appropriate
operation-scoped `*_invalid_request_unattributed` code, with exactly one
gateway-owned upstream request.

## 4. Acceptance and current evidence

The two real Doc118 General reference attempts had remote Brain without
fallback and one `image_edit` operation each, but no returned pixels. They
therefore remain Provider/no-pixel blocked, not an image-quality conclusion.
After this correction, subsequent equivalent failures receive an accurate safe
public class without exposing raw provider detail. The already-recorded
attempts remain append-only historical evidence. A later real rerun requires
newly available Provider support; it must not substitute another model or adult
subject merely to make the test pass.
