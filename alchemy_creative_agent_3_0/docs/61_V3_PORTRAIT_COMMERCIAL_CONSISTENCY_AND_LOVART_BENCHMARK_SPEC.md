# 61 V3 Portrait Commercial Consistency And Lovart Benchmark Spec

## 1. Status And Authority

This document is the portrait validation authority after documents 56-60.

Authority chain:

```text
Doc50:
  Reusable visual enhancement belongs in the V3 native Visual Capability
  Cluster.

Doc54:
  Owns the four user-facing generation modes.

Doc56:
  Owns human identity consistency with natural pose/expression variation.

Doc58:
  Owns selected-output identity anchors and strong reference continuation.

Doc59:
  Owns mode-aware role differentiation and suite separation.

Doc60:
  Owns E-Commerce product-suite slot fidelity and label/logo QA.

Doc61:
  Owns portrait commercial consistency validation, real portrait test protocol,
  and Lovart-grade quality comparison criteria.

Doc62:
  Extends Doc61 with stronger General Template portrait-suite art direction:
  role-specific expression, gaze, pose, crop, subject scale, and scene-depth
  lanes for delivery-suite portraits.
```

If Doc61 conflicts with Doc56 or Doc58 on portrait consistency, Doc61 only wins
for validation and acceptance wording. It must not weaken the existing identity
anchor, strong reference, project context, or natural variation contracts.

Doc61 does not change E-Commerce behavior. Doc60 remains the authority for
product suites.

Doc62 wins only for portrait delivery-suite role-separation implementation
details. Doc61 remains the validation and benchmark protocol.

## 2. Goal

Beginner-facing goal:

```text
The user can make a portrait project, pick one image they like, and continue
generating the same person direction as a polished commercial photo set.
The face, body type, hair direction, wardrobe direction, lighting language, and
visual tone should stay consistent.
Expression, pose, head angle, camera distance, and scene framing should vary
naturally so the set does not look like cloned frames.
```

Commercial target:

```text
V3 portrait outputs should feel like a directed photo shoot:
cover hero
closer subject frame
side or three-quarter angle
wider scene/context frame
```

The user should not need to know prompts, model settings, seed, ControlNet, or
engineering controls.

## 3. Compatibility Rules

Doc61 is a validation layer and small regression-harness layer, not a new
runtime architecture.

Allowed:

```text
add portrait validation scripts under .codex-longrun
add documentation for real portrait validation and Lovart comparison
add tests if a missing regression is found
run real generation through Project Mode and existing providers
record visual evidence and comparison notes
```

Not allowed:

```text
call V1/V2 runtime code
replace Project Mode
replace ScenarioRuntime or Product API
add portrait-only framework logic into Central Brain
change Doc60 E-Commerce slot contracts
raise Doc53 retry budgets
auto-write Brand Memory
```

## 4. Required Runtime Path

The portrait validation must use the same V3 project chain the frontend uses:

```text
create Project with General Template
create first Job
generate first portrait
select one generated image
Project Context converts selected image into strong identity reference
create continuation Job inside the same Project
generate a portrait suite using the selected image as hard reference
inspect outputs
compare commercial consistency and role separation
```

The validation is incomplete if it only runs an isolated non-project job.

## 5. Portrait Consistency Contract

### 5.1 Must Stay Consistent

```text
same recognizable person direction
same broad face identity direction
same body type and proportions
same broad hair color/length direction
same wardrobe category or styling family
same lighting language
same color palette and finish
same commercial/editorial world
```

### 5.2 Must Be Allowed To Vary

```text
expression
gaze
head angle
body pose
hand placement
camera distance
crop
scene depth
minor hair styling
minor outfit detail within the same wardrobe family
```

The model must not create exact cloned stills unless the selected mode is
`selection_candidates` and the user explicitly wants close alternatives.

## 6. Mode Expectations

### 6.1 Similar Candidates

Purpose:

```text
help the user choose one favorite frame
```

Expected variation:

```text
small expression, gaze, pose, crop, and hand placement differences
```

Not acceptable:

```text
different person
different hair identity
different wardrobe category
large scene drift
```

### 6.2 Delivery Suite

Purpose:

```text
make a useful commercial portrait set under the selected direction
```

Expected roles:

```text
cover hero
closer subject/detail frame
side or three-quarter angle
wider environmental/context frame
```

Not acceptable:

```text
four near-identical headshots
same exact face angle in every image
loss of selected identity
weak commercial finish
```

### 6.3 Creative Exploration

Purpose:

```text
explore broader visual directions before locking one
```

Expected variation:

```text
different mood, palette, scene, styling lane, or photographic concept
```

Identity can be looser than delivery suite, but the subject direction must
remain recognizable unless the user asks for concept-only exploration.

### 6.4 Format/Layout Adaptation

Purpose:

```text
adapt the same selected idea to vertical, square, horizontal, or tighter crops
```

Expected variation:

```text
crop and layout differences, not identity or styling changes
```

## 7. Lovart Benchmark Criteria

Doc61 should evaluate portrait outputs against these dimensions:

```text
project continuity:
  does the continuation clearly use the selected output as its anchor?

identity consistency:
  same person direction without obvious identity drift

natural variation:
  not cloned face/expression/angle across all images

role separation:
  each image has a useful photo-shoot duty

commercial finish:
  lighting, skin, wardrobe, composition, background, and crop feel usable

artifact cleanliness:
  no watermark, random text, extra limbs, severe hand/face artifacts

frontend usefulness:
  outputs can be shown as a project set with clear image cards
```

Lovart-grade does not mean identical to Lovart's internal implementation. It
means the user receives a coherent commercial design chain with high image
quality and low manual effort.

## 8. Real Validation Prompt

Use a stable portrait prompt so future runs can compare apples to apples:

```text
Create a summer cool East Asian beauty portrait set for a social cover campaign.
The same young woman has subtle green-highlighted dark hair, clean white summer
styling, fresh seaside light, bright blue-green color mood, refined commercial
photography finish, no visible text, no product, no packaging.
```

Continuation prompt:

```text
Continue this selected woman as a commercial portrait suite with cover hero,
closer upper-body frame, three-quarter side angle, and wider seaside lifestyle
context. Keep the same person direction, green-highlight hair direction, clean
white summer styling, bright blue-green daylight mood, and high-end editorial
finish. Allow natural expression, pose, gaze, head angle, crop, and scene-depth
variation.
```

## 9. Acceptance Checks

Automated metadata checks:

```text
first job creates real outputs
selected output enters Project selected_output_refs
selected output becomes strong identity reference
continuation job metadata includes strong reference bindings
continuation provider metadata reports reference_asset_count >= 1
continuation role plan contains portrait delivery roles
post-generation review package exists
visual auto retry summary exists
```

Prompt checks:

```text
final provider prompt contains same-person / identity preservation rules
final provider prompt allows expression, pose, head angle, angle, crop variation
final provider prompt forbids visible text, watermark, random labels
no product/ecommerce wording appears in General Template portrait prompt
```

Visual checks:

```text
selected anchor and continuation outputs read as the same person direction
hair direction and wardrobe family remain consistent
lighting and color mood stay coherent
poses/crops/angles vary enough for a commercial set
no obvious text, watermark, severe face/hand/body artifact
```

## 10. Test Plan

Focused tests:

```text
test_v3_project_mode.py
test_v3_mode_aware_role_director.py
test_v3_llm_brain_adapter.py
test_v3_general_prompt_deproductization.py
test_v3_post_generation_vision_review.py
```

Broad tests:

```text
python -m pytest alchemy_creative_agent_3_0/tests tests -q --tb=short
python -m compileall -q alchemy_creative_agent_3_0/app alchemy_creative_agent_3_0/tests tests src_skeleton/app
node --check src_skeleton/app/static/app.js
git diff --check
```

Real validation:

```text
run .codex-longrun/doc61_real_portrait_validation.py
inspect contact sheet
compare against Doc58 portrait validation and Lovart benchmark criteria
```

## 11. Completion Criteria

Doc61 is complete when:

```text
documentation exists and does not conflict with Docs 50, 54, 56, 58, 59, 60
focused tests pass
full regression passes or any failure is documented as unrelated
real portrait suite is generated when provider is available
contact sheet and result JSON are saved
commercial comparison notes are recorded
ServerChan review notification is sent
```
