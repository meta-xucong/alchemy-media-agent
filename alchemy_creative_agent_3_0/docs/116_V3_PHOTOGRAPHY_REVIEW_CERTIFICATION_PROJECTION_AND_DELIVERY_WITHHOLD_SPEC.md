# Doc116: Photography Review Certification Projection And Delivery Withhold

## Purpose

Doc115 requires shared `vision_model` or `hybrid` final-pixel review for every
active Photography delivery.  This document closes the reporting and recovery
gap: a Job and its Project history must reveal the certification outcome
without exposing provider internals, and non-certifying pixels must never
appear as an ordinary final delivery after a page refresh or project recovery.

This is a shared Product API / Project Mode / browser projection.  It creates
no Photography-owned Provider, reviewer, retry loop, or result selector.

## Public Certification Contract

Photography Job metadata may expose only this safe object:

```json
{
  "schema_version": "v3_review_certification_v1",
  "scenario_id": "photography",
  "state": "certified | manual_confirmation_required | blocked",
  "automatic_delivery_certified": true,
  "manual_confirmation_required": false,
  "final_delivery_withheld": false,
  "roles": [
    {
      "role_key": "session_hero",
      "state": "certified | manual_confirmation_required | blocked",
      "review_mode": "vision_model | hybrid | metadata_only | local_image_heuristic | null",
      "review_status": "pass | warning | manual_review | fail_retryable | fail_final | null",
      "verification_state": "verified | unverified | unavailable | locally_checked | null"
    }
  ]
}
```

It must not expose candidate IDs, asset IDs, output URLs, provider names,
provider errors, image paths, prompt text, or internal review evidence.

## Certification Rules

- `certified` requires every frozen role to have a shared `vision_model` or
  `hybrid` inspection whose terminal review status is `pass` or `warning`.
- `manual_confirmation_required` means real pixel review ran but its result is
  inconclusive.  It is visible to the operator, but is not an automatic pass
  and cannot count toward P10 or a production gate.
- `blocked` covers `metadata_only`, local-only, unavailable, missing, failed,
  or otherwise non-certifying review.  Pixels remain append-only diagnostic
  history only.
- `final_delivery_withheld=true` prevents the result from entering the normal
  current-result panel, Project output board, selected-result flow, and
  recovery-created `JOB_GENERATED` timeline events.

## Lifecycle And Compatibility

The Product API computes the certification from the frozen specialized role
execution plus the shared post-generation review package.  Project Mode copies
the same safe object into its review/blocked timeline events and treats every
withheld specialized execution as unsettled for ordinary delivery purposes.

For jobs written before Doc116, a read-only adapter may project recorded role
review mode/status into this object.  It may withhold an old result, but it
must never certify pixels retroactively or recreate a legacy execution path.
Jobs with no usable historical review evidence stay non-certifying until a new
shared generation/review run exists.

## Browser Contract

The result panel and recent Project timeline show the certification state and
review mode in non-provider-specific language:

- certified real-pixel review;
- manual confirmation required; or
- real-pixel review not automatically certified.

When delivery is withheld, the browser must show the reason rather than an
image card with select/download/delete controls.

## Acceptance

Regression coverage must prove that:

1. `metadata_only` Photography pixels are blocked, have a safe public
   certification object, and never reach Project outputs;
2. a `vision_model`/`hybrid` manual result is visible as manual confirmation
   required yet never counts as an automatic delivery or P10 pass;
3. a complete certified role set remains deliverable;
4. role-failure append-only history remains withheld rather than collapsing
   into a single delivered image;
5. General and E-Commerce receive neither the Photography certification object
   nor Photography role semantics.

## Gate Status

This contract makes the P10-T2I review outcome auditable.  It does not convert
the earlier frontend result into a P10 real-pixel pass: that run lacked a
visible structured certification record.  A fresh controlled-instance run
must report its mode, certification state, and final verdict before the P10
quality matrix continues.  The Photography production deployment gate remains
off until that matrix and the real Central Brain, GPT Image 2, and vision
Provider acceptance evidence are complete.
