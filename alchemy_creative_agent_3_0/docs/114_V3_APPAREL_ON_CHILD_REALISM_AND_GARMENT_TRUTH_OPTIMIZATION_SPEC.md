# Doc114 V3 Apparel-on-Child Realism and Garment Truth Optimization

> **Doc135 refinement:** apparel and age-appropriate realism are shared,
> evidence-driven constraints. They must never become a child-specific local
> prompt recipe or a keyword-derived renderer decision.

Status: post-Doc113 capability specification; implementation is explicitly out
of scope for the Doc113 correction task.

The separate Doc114 implementation candidate `a2f2594` may be audited/rebased
only after the shared execution and Provider-closure contracts below are
integrated. Until then this document is a gated specification, not proof that
the apparel/child acceptance gate is passed.

Current gate reconciliation (Doc117): `job_3863e5d5f2` did **not** produce
pixels. Its generic Provider 400 is currently
`image_generation_invalid_request_unattributed`, not a confirmed policy block
and not a child-visual-quality result. Candidate `e458d23` closes the shared
real-visible-person activation omission but still awaits mainline integration.
Doc117 owns reference-input admission and no-pixel Provider failure closure;
this document begins only after candidate pixels exist. Neither document
authorizes a child/kidswear route, classifier, prompt recipe, age inference, or
demographic workaround.

This is the mainline-numbered import of the audit authority formerly prepared
as `105_V3_APPAREL_ON_CHILD_REALISM_AND_GARMENT_TRUTH_OPTIMIZATION_SPEC.md`.
References to the former audit runtime-correction/apparel documents mean
**Doc113/Doc114** here. It does not replace the existing mainline documents
numbered 104 and 105.

## 1. Preconditions and boundary

No Doc114 implementation starts until all Doc113 Phase 0--5 gates are green:

```text
one enforced execution envelope through retry
one E-Commerce template-owned, Brain-bound deliverable plan
no shared suite director or E-Commerce delivery map
Provider/Review/Retry consume envelope and resolved ledger only
metadata-only inspection cannot approve a pixel-dependent contract
```

Doc113 closure is necessary but not sufficient for a Doc114 mainline merge.
The implementation branch may proceed, but the agent must independently run
and record all of the following acceptance gates before requesting merge:

```text
1. E-Commerce real-chain acceptance: real product reference, remote Brain,
   Provider, and shared review/retry all complete one reliable delivery path.
2. Photography P10: cross-domain person/reference/three-role acceptance is
   complete and recorded as regression evidence.
3. Browser Gate D: selected-result delivery, continuation, refresh recovery,
   and failure presentation are trustworthy in the user path.
```

These are merge/release gates, not a requirement for an additional user-side
pre-approval before development begins. If a gate cannot be executed because a
required external service or browser environment is unavailable, record that
fact as a release blocker; do not claim the corresponding behavior is proven.

This is not a request for a kidswear module. The architecture remains:

```text
E-Commerce Template / Scenario Pack -> requested count and delivery intent
Product Identity / reference policy -> garment truth
shared Human Realism -> product-on-person, explicit-age and camera realism
shared Review/Retry -> pixel verification and owner-local repair
```

Forbidden: a child/kidswear module, Scenario Pack, template, plugin, provider
route, shared prompt recipe, static E-Commerce package, inferred young subject,
or a default high-key/sweet-studio visual treatment.

## 2. Evidence and ownership

Human Realism activates only from reusable normalized evidence:

```text
visible_person
product_on_person_detected
explicit_age_direction
wearable_apparel_evidence
reference_channel_assignment
```

`product_on_person_detected` is the canonical emitted field from Doc113. The
former `product_on_person` spelling is read-only compatibility for historical
records and must not be emitted into a new plan, ledger, prompt, review, or
retry.

Age direction is a user/request/review constraint, not a stored biometric
inference. A small garment is never evidence that a subject must be young.

| Decision | Owner | Boundary |
| --- | --- | --- |
| Count, Brain image intents, platform composition | E-Commerce Template | No static local role/scene/camera recipe |
| Silhouette, pattern, construction, material | Product Identity | Source-proportionate evidence only |
| Product-on-person, explicit age, anatomy/skin realism | shared Human Realism | Removes artifacts without owning template roles |
| Scene, styling, light, mood, pose/expression | user intent | Human Realism preserves rather than replaces it |
| Pixel verification and candidate choice | shared review + template contract | Retry only repairs the failed channel |

## 3. Typed apparel construction truth

Extend existing Product Identity/reference-policy output with a typed,
source-proportionate apparel construction record rather than another module.
Applicable fields include:

```text
silhouette_and_proportion
print_or_pattern_registration and scale
layer_order and transparency/mesh topology
seam, hem, edge, trim, fastening, accessory placement
material weight and surface response
fold tension, gravity, and drape
evidence quality/source and allowed variation boundary
```

Visible distinctive facts are hard truth; visible material behavior is strong
controlled truth; hidden/ambiguous facts remain soft preference. These resolve
through independent ledger channels:

```text
product_silhouette
product_pattern_registration
product_layer_topology
product_construction_detail
product_material_response
product_drape_behavior
```

Garment truth never locks person identity, pose, scene, lighting, styling, or
whole-image aesthetics. A turn can change folds but cannot erase known pattern
placement or layer order.

## 4. Generic Human Realism target

Use existing universal variables, conditionally activated by evidence:

```text
age_fidelity
skin_texture and skin_specularity
complexion preservation
facial-feature relationship
micro-expression / gaze / head-angle / pose naturalness
hand and anatomy plausibility
exposure key, contact shadow, depth, material separation
anti-synthetic / anti-plastic negative
```

Bright, soft, and luminous requests retain their character while avoiding
airbrushed skin and flat material response. Moody/cinematic requests retain
their mood with controlled highlights and texture; Human Realism must not add
bright commercial wording. Adult fashion, adult portraits, and non-person
products remain valid cross-domain checks.

## 5. Template-owned apparel-on-model diversity

Only after Doc113, the E-Commerce Scenario Pack may provide an
`apparel_on_model` *evidence profile* to the remote Brain/final deliverable
plan. It may select no more than the user-requested count and cannot create a
fixed suite. Each multi-output plan declares distinct evidence dimensions such
as product view, movement, construction proof, context, camera/crop, and (when
visible) expression/pose variation. The shared layer reads the final contract
only; it does not choose or reorder roles.

One requested output remains one product-first intent. Seven supported outputs
need materially different evidence purposes, not seven repeated centered poses.

## 6. Provider, review, and bounded repair

Provider materializes only the Doc113 ledger and the remote Brain's complete
natural-language image direction: final role contract, garment facts with
strengths, generic Human Realism quality concern, user-owned art direction,
text policy, resolved format, and review IDs. No independent child, beauty,
listing-role, studio recipe, or structured prompt supplement may be appended.

For a multi-output E-Commerce request, the per-output review ID is frozen
before generation by the internal `asset_id -> requested output index ->
ledger deliverable_id` mapping. Pixel review must resolve that ID back against
the ledger; it must not infer a Brain evidence assignment from candidate,
provider, or shared `mode_role_recipe` metadata.

Hard garment truth, explicit-age direction, visible anatomy, and role-difference
contracts require real/hybrid pixel review. Ownership is local and bounded:

| Failure | Repair owner |
| --- | --- |
| Plastic/adultified face, implausible hands, frozen expression | shared Human Realism |
| Print/layer/seam/hem/trim/drape loss | Product Identity/reference policy |
| Wrong/repeated delivery evidence | E-Commerce Template |
| Text, size/aspect, renderer defect | provider/universal quality |

Retries retain valid channels and append history. Candidate selection compares
compliant outputs rather than assuming the latest retry is best.

## 7. Future acceptance matrix

Before production promotion, retain evidence for:

1. explicit-age apparel-on-person with distinctive garment reference;
2. adult apparel-on-person with product reference;
3. same-person portrait with prompt-owned hair/light/scene;
4. non-person product/object;
5. bright/high-key and soft commercial variants; and
6. moody/cinematic person variant.

Review pass/warning/fail notes must cover product fidelity, applicable age
fidelity, human naturalness, camera/material plausibility, role/count fidelity,
prompt-channel preservation, retry discipline, and selected-result rationale.
No persistent biometric vector, face database, or age classifier record is
permitted.

## 8. Definition of done for the later task

The later Doc114 task is complete only when typed apparel facts are resolved
independently of person realism and roles; explicit-age product-on-person uses
generic evidence; E-Commerce alone owns count-bounded diversity; pixel review
verifies human/product/role contracts; retry is owner-local and bounded; the
cross-domain matrix passes; and General/shared foundation contain no E-Commerce
delivery package or child-specific runtime.
