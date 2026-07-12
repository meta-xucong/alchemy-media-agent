# 105 V3 E-Commerce Slot Continuation And Text Pixel Delivery Contract

Status: accepted mainline contract. It freezes the shared interface and
acceptance boundary; no slot-continuation route or final-text renderer is
implemented by this document.

## 1. Purpose And Ownership

E-Commerce owns suite roles, platform profiles, copy planning, and the
professional delivery map. The V3 foundation owns Project Mode lineage,
CapabilityActivationPlan governance, provider routing, deterministic delivery
postprocess, review, retry, and final-result presentation.

This contract applies only to `ecommerce_template`. It does not add an
E-Commerce action, slot, platform, or continuation concept to General
Template.

## 2. Slot Continuation Public Contract

The future Project Mode action is namespaced and separate from selection,
deletion, and internal retry:

```text
POST /api/v3/creative-agent/projects/{project_id}/jobs/{parent_job_id}
     /ecommerce-slots/{slot_id}/continuations
```

Request shape:

```json
{
  "correction_note": "optional user-directed correction",
  "new_evidence_asset_ids": ["optional uploaded or selected evidence IDs"],
  "metadata": { "source": "ecommerce_workspace" }
}
```

The endpoint creates a planned child continuation job. Generation then uses
the existing, ordinary project-job generation endpoint for that child. The
endpoint must never synchronously replace a parent output or invoke a private
provider/retry API.

Validation rules:

- the parent belongs to `ecommerce_template` and its project;
- `slot_id` is a declared role in the parent's frozen E-Commerce suite;
- the parent has a frozen capability plan and readable lineage metadata;
- correction text is prompt direction, not evidence of a new capability;
- new evidence must already be an authorized project asset or selected output;
- a General, legacy, missing-lineage, or unknown-slot job returns the explicit
  `slot_continuation_not_supported` result and remains readable.

Before the endpoint and its tests exist, the E-Commerce UI must not render a
clickable, disabled, cosmetic, or optimistic “redo this slot” control.

## 3. Immutable Lineage And Delivery Semantics

Creating a continuation appends a child job with at least:

```text
root_job_id
parent_job_id
parent_slot_id
continuation_kind = ecommerce_slot
continuation_correction_note
capability_activation_plan_id
plan_amendment_id | null
```

The parent job, its candidates, its review reports, and its output records are
never mutated. Existing automatic visual retries remain internal attempts of
their own job; they are not a user slot continuation and must not be exposed
as one.

Delivery resolution is keyed by `(root_job_id, slot_id)`:

1. a successful child becomes the current final delivery for that slot;
2. the parent and earlier children remain append-only folded history;
3. a failed or blocked child never removes the earlier current final delivery;
4. user-facing delivery panels show one current final result per requested
   slot, while workflow/history can reveal all attempts.

This preserves the V3 rule that retry-superseded and user-superseded outputs
are retained internally but do not inflate the beginner-facing delivery count.

## 4. Frozen Plan And Bounded Amendment Rules

The child inherits the exact parent `CapabilityActivationPlan` by default,
including its plan ID, catalog version, active capability IDs, provider
contribution, review vocabulary, and retry ownership.

Only new, explicit evidence may request an amendment. A correction note,
preference change, or dissatisfaction alone cannot activate a capability.

An amendment is valid only when all conditions hold:

- the new evidence is recorded in the child lineage and differs from parent
  evidence;
- the activation planner validates template policy, dependencies, conflicts,
  and evidence for the proposed change;
- the record links the parent plan, new plan, reason codes, evidence IDs, and
  activated/deactivated capability IDs;
- there is at most one amendment in a root-job/slot continuation lineage;
- provider, review, and retry all consume the amended plan after it is frozen.

The requester never submits capability IDs directly. An invalid or exhausted
amendment request fails as a structured continuation validation result; it
must not silently fall back to an unfrozen recomputation.

## 5. Shared Execution Path

Every child job follows the existing governed path:

```text
Project Mode child job
-> Scenario Runtime and frozen plan
-> shared generation provider path
-> shared visual review
-> bounded shared retry
-> append-only output resolver
```

E-Commerce UI and Scenario Pack code must not call a provider, issue an
unreviewed replacement image, or create a local retry loop for a slot.

## 6. Text Planning Is Not Pixel Delivery

The integrated E-Commerce module may plan locale, short copy, copy policy,
claim-review status, and slot-safe copy. That metadata is not a promise that
the model has rendered correct text pixels.

Current rules remain:

- a platform profile declares text-forbidden slots, including the marketplace
  main image where applicable;
- text-bearing slots may carry a reviewable semantic copy plan;
- `en-US`, `zh-CN`, and `ru-RU` planning is locale ownership, not a
  translation, OCR, spelling, or final typography guarantee;
- unsupported claims remain review warnings and are never converted into a
  compliance promise.

Until the capability below is implemented, final copy must not be represented
as delivered merely because a recipe contains `overlay_text`.

## 7. Future Shared Typography And OCR Capability

The future foundation capability consumes a scenario-neutral
`CopyRenderPlan`, rather than marketplace-specific UI fields:

```text
expected_copy
locale
text_policy = forbidden | optional | required
normalized_safe_area
layout_priority
claim_review_state
```

E-Commerce profiles and recipes supply the slot-safe-area and copy intent.
The shared runtime owns deterministic layout, licensed-font selection,
rasterization, output metadata, and review. General Template receives no
E-Commerce profile or slot data; it may use this shared capability only when a
future General request explicitly asks for supported text delivery.

Required shared checks after deterministic composition:

- OCR reads the intended locale and expected copy;
- text remains inside the normalized safe area and does not overflow or clip;
- spelling, legibility, contrast, and required/forbidden-text policy pass;
- copy claims retain their E-Commerce review state and are not upgraded to a
  legal or platform-approval guarantee.

Bounded recovery is ordered as follows:

1. one deterministic layout repair may adjust type size, line break, or safe
   placement without regenerating the image;
2. only a background/readability failure eligible under the frozen review
   contract may use the existing bounded generation retry;
3. wrong, unsupported, or unverified copy is non-retryable and requires a
   user or approved copy-plan correction.

All repair and retry attempts are append-only and must retain the same frozen
plan or a recorded amendment from Section 4.

## 8. Gate C And Gate D Acceptance Matrix

Doc104 Gate C cannot pass merely because copy planning or unit tests pass. It
requires real provider evidence for at least:

| Case | Required evidence |
| --- | --- |
| Product-reference suite | Product identity, review, retry, and delivery lineage for real product pixels. |
| Text-forbidden main image | No final overlay copy, no text artifact, and correct platform policy. |
| Text-bearing slot | Deterministic safe area, OCR, overflow/spelling/claim review, and bounded repair evidence. |
| Locale matrix | One approved text-bearing fixture for `en-US`, `zh-CN`, and `ru-RU`; unsupported glyph/font cases block activation. |
| Provider failure | Structured blocked state, no false delivery, bounded retry, and retained diagnostics. |

Doc104 Gate D remains a General-only browser acceptance. It must prove project
selection, continuation, new-reference upload, negative feedback, restoration,
and resumed generation without displaying E-Commerce slot, platform, or
continuation controls.

The E-Commerce template remains non-production-active until Doc104 Gates A-D,
this contract's tests, and its own template activation gate all pass.

## 9. Compatibility And Implementation Checklist

- Historical jobs and exports remain readable without migration.
- Legacy jobs with no lineage remain non-regenerable per slot.
- Existing select/delete endpoints retain their meanings and must not proxy a
  slot continuation.
- Internal retry endpoints remain private implementation details.
- The implementation adds route, schema, lifecycle, resolver, capability, and
  browser tests before revealing the UI control.
- E-Commerce documentation E04 and E09 must cross-reference this contract
  when the E-Commerce worktree implements its side of the interface.
