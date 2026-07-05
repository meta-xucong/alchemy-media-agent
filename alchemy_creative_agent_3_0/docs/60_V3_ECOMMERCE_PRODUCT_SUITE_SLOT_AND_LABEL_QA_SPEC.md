# 60 V3 E-Commerce Product Suite Slot And Label QA Spec

## 1. Status And Authority

This document is the implementation authority for closing the product-image
gap found in the real Aqua Tea validation after documents 56-59.

Authority chain:

```text
Doc50:
  Reusable visual enhancement belongs in the V3 native Visual Capability
  Cluster.

Doc53:
  Owns safe automatic retry execution.

Doc55:
  Owns post-generation image inspection signals.

Doc57:
  Owns E-Commerce lifestyle realism and watermark/commercial cleanliness QA.

Doc59:
  Owns mode-aware role differentiation.

Doc60:
  Owns E-Commerce product-suite slot fidelity, product label/logo preservation
  QA, and Lovart-grade product-suite acceptance criteria.
```

If documents conflict about E-Commerce suite role order, product slot fidelity,
or product label/logo preservation, Doc60 wins. Doc60 does not replace Project
Mode, ScenarioRuntime, Product API, provider routing, Doc53 retry budgets, or
the V3 native Visual Capability Cluster.

## 2. Trigger Evidence

Real validation:

```text
Project: project_af690c4707
Job: job_27b076708c
Reference product: Aqua Tea lime mint can
Requested slots: main_image, feature_image_1, scenario_image
Generated roles: main_image, scenario_image, detail_image
```

Observed strengths:

```text
product color and shape stayed consistent
main label stayed mostly readable
summer lime/mint identity stayed consistent
OpenAI/C2PA provenance signal was present
no third-party AIGC metadata was detected
visual quality was commercially usable
```

Observed gaps:

```text
requested feature slot was replaced by a generic detail slot
small product label text could become dark or partially suppressed
post-generation local review passed images that still need product-label review
the set was attractive but not yet fully Lovart-grade in explicit selling-role
coverage
```

## 3. Product Goal

Beginner-facing goal:

```text
The user uploads a product image and asks for a set.
V3 decides the image jobs, but it must honor the chosen/requested product
slots.
Every generated image keeps the real product identity.
If label/logo/product identity or slot role is wrong, V3 should catch it and
make a safer retry when the issue is clear.
```

Commercial target:

```text
V3 product suites should feel like a directed listing/ad set:
main image
benefit or feature image
detail proof
lifestyle scene
trust/comparison/format support when requested
```

The system must not collapse these into visually similar studio variants unless
the user explicitly asks for close alternatives.

## 4. Compatibility Rules

Doc60 is an extension under the existing architecture:

```text
Project wraps Job.
Template wraps Scenario Pack.
E-Commerce Template uses the E-Commerce Scenario Pack.
Visual enhancements stay inside the V3 native Visual Capability Cluster.
Doc53 remains the retry executor.
Doc55/57 remain the post-generation review signal owners.
```

Do not:

```text
call V1/V2 runtime code
add a second template system
move product-suite policy into the central brain as hard-coded framework logic
replace ScenarioRuntime
replace the provider layer
raise retry budgets beyond Doc53
auto-write Brand Memory
```

Allowed implementation:

```text
add product-suite helpers inside ModeAwareRoleDirector
let CentralCreativeBrain reconcile role plans from actual E-Commerce asset
recipes
add product-label issue codes to VisionOutputInspector and Product API retry
patch mapping
add prompt constraints to preserve existing product labels/logos while
forbidding new generated text
add tests proving requested E-Commerce slots survive through generated
candidates
```

## 5. Slot Fidelity Contract

### 5.1 Source Of Truth

For E-Commerce Template jobs, the source of truth for image roles is:

```text
EcommerceScenarioPackPlanner
  -> marketplace selected image slots
  -> SellingPointToImagePlanner recipes
  -> EcommerceAgentFamily.refine_series_plan asset metadata
```

ModeAwareRoleDirector may enrich these roles, but must not replace them with
generic product delivery roles.

### 5.2 Required Mapping

Each generated asset with `metadata.ecommerce_recipe` must receive a
`mode_role_recipe` derived from the same recipe.

Required invariant:

```text
asset.metadata.ecommerce_slot == asset.metadata.mode_role_recipe.role_key
candidate.metadata.mode_role_recipe.role_key == candidate.metadata.ecommerce_slot
role_specific_generation_plan.role_recipes[i].role_key ==
  series_plan.assets[i].metadata.ecommerce_slot
```

If requested slots are:

```text
main_image, feature_image_1, scenario_image
```

then generated role keys must remain:

```text
main_image, feature_image_1, scenario_image
```

The role director may add shot family, camera distance, crop, scene rule,
prompt pressure, negative pressure, and review checks.

### 5.3 Count Rule

Doc59 General Template mode roles are normally capped around the four public
creative modes. E-Commerce product suites are different: the number of roles
must follow the Scenario Pack listing recipes and the user's requested
`requested_image_count` / `suite_slot_request`.

Implementation rule:

```text
General Template:
  role count follows the four-mode director contract

E-Commerce Template:
  role count follows actual ecommerce recipes, up to the listing suite limit
  used by the E-Commerce Scenario Pack
```

Therefore a seven-image marketplace recipe must not be truncated to four role
recipes, and a three-slot request must not be expanded or replaced by generic
roles.

## 6. Product Label And Logo Protection

E-Commerce prompts must distinguish between:

```text
new generated text: forbidden
existing product label/logo visible in the supplied reference: preserve exactly
```

Provider prompt rules:

```text
do not invent text, icons, badges, seals, feature strips, claims, or labels
preserve existing product label/logo text if visible on the supplied product
keep label/logo placement, contrast, and readability when it remains in frame
do not translate, rewrite, enlarge, crop away, blur, darken, or cover existing
product label text
use composition and props to communicate selling points instead of rendered
copy
```

For small reference labels, the model should prefer:

```text
front or three-quarter product angle
enough product scale
clean glare control
no condensation/shadow over critical label text unless the slot is explicitly
a close texture/detail shot and the label remains acceptable
```

## 7. New Issue Codes

Doc60 adds these retryable issue codes:

```text
product_label_drift
product_label_unreadable
product_logo_or_label_obscured
ecommerce_slot_mismatch
ecommerce_suite_role_mismatch
```

Meaning:

```text
product_label_drift:
  visible supplied product label/logo was rewritten, translated, misspelled, or
  materially changed

product_label_unreadable:
  product label/logo should be readable for the slot but became too blurred,
  dark, tiny, or low contrast

product_logo_or_label_obscured:
  label/logo is blocked by props, condensation, crop, glare, hand, shadow, or
  scene clutter

ecommerce_slot_mismatch:
  generated role metadata or prompt role does not match the requested/planned
  E-Commerce slot

ecommerce_suite_role_mismatch:
  the suite repeats the same job or misses a required E-Commerce selling role
```

These are visual/product QA issues, not provider errors. They may trigger Doc53
retry only when:

```text
issue is high-confidence enough
retry patch is non-empty
Doc53 retry budget allows it
same issue has not repeated
```

## 8. Retry Patch Contract

For label/logo issues:

```json
{
  "prompt_additions": [
    "Preserve the supplied product label/logo exactly as visible on the reference product.",
    "Keep the product label readable, high-contrast, and not covered by props, glare, crop, or condensation."
  ],
  "negative_additions": [
    "rewritten product label",
    "misspelled product label",
    "translated label",
    "blurred logo",
    "covered product label",
    "fake product text",
    "invented packaging copy"
  ],
  "product_reinforcement": [
    "use the uploaded product image as the identity source for label placement, logo shape, color, material, and proportions"
  ],
  "artifact_repair": [
    "clean glare, shadow, condensation, crop, or props away from the critical label/logo area"
  ]
}
```

For slot mismatch:

```json
{
  "prompt_additions": [
    "Regenerate the failed output for its exact planned E-Commerce slot.",
    "Do not replace a feature image with a detail image or a lifestyle image."
  ],
  "composition_repair": [
    "follow the planned slot camera distance, scene duty, selling point, and crop"
  ],
  "negative_additions": [
    "wrong ecommerce slot",
    "generic product variant",
    "same image duty repeated"
  ]
}
```

## 9. Acceptance Tests

Deterministic tests must prove:

```text
explicit E-Commerce slots survive through role_specific_generation_plan
generated candidates keep the same slot role keys
feature_image_1 is not silently replaced by detail_image
provider prompt includes existing label/logo preservation rules
product label issue codes are retryable
slot mismatch issue codes are retryable
retry patches contain label repair and slot repair guidance
General Template behavior remains unchanged
```

Real validation should compare:

```text
old Aqua Tea run:
  main_image, scenario_image, detail_image

new Aqua Tea run:
  main_image, feature_image_1, scenario_image
```

Qualitative target:

```text
product identity remains consistent
existing label/logo stays more legible
suite role duties are clearer
no third-party AIGC metadata
no visible watermark or AI badge
post-generation review metadata records pass/warning/retry decisions
```

## 10. Implementation Phases

### Phase 1: Documentation

Add Doc60 and compatibility notes to Doc53/55/57/59.

### Phase 2: Slot-faithful role planning

Add an E-Commerce recipe-to-mode-role mapper inside the V3 visual cluster.
CentralCreativeBrain must reconcile mode roles from actual E-Commerce series
assets when those assets carry `ecommerce_recipe`.

### Phase 3: Product label/logo prompt and QA taxonomy

Strengthen prompt/provider constraints and add retryable issue codes and patches
for product label/logo drift, unreadability, and obstruction.

### Phase 4: Tests

Add focused tests for role fidelity and label retry patches, then run broader
regression.

### Phase 5: Real comparison

Run a new product-suite generation with the same Aqua Tea task and compare slot
roles, provenance, visual quality, and label readability against the prior run.

## 11. Done Criteria

Doc60 is complete when:

```text
docs compile as a compatible authority chain
requested E-Commerce slots drive mode roles and candidates
product label issue codes are retryable and produce non-empty patches
focused tests pass
full regression passes or any unrelated failure is documented
real product-suite comparison is recorded when provider is available
```
