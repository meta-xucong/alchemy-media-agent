# 68 V3 Casebook-Guided Photographic Recipe Tuning Spec

> Historical/compatibility notice (Docs94, 111, and 113): casebook recipes are
> no longer a forward runtime mechanism. Do not recreate local recipe helpers,
> camera/light/pose blocks, or case-derived prompt stacks from this document.
> Preserve only neutral empirical observations as regression fixtures; remote
> Brain creative direction and shared factual constraints now govern new work.

Doc93 compatibility note:

```text
Casebook recipes may improve craft and realism but cannot expand reference
inheritance. Recipe identity, hair, wardrobe, light, and scene examples must be
filtered through the resolved channel policy before provider compilation.
```

Status: historical optimization record; not forward implementation authority.

This document formerly proposed reusable photographic recipes after document
67. Its observations remain useful only when restated as neutral test evidence;
it is not an implementation authority and must not create a parallel visual
framework.

Document 69 is the accepted authority after this document for prompt atom
realism and reference absorption. Doc69 keeps this architecture and only makes
the camera, light, texture, reference, product-truth, negative, review, and
retry atom stacks more explicit.

## 1. Authority And Compatibility

Doc68 extends:

```text
Doc50: Visual Capability Cluster ownership
Doc54: four General Template modes
Doc56: human identity consistency with natural variation
Doc59: mode-aware role director
Doc60: ecommerce slot and product truth
Doc61: portrait Lovart benchmark validation
Doc62: portrait suite role separation
Doc64: commercial quality closure
Doc65: human photorealism and anti-AI-face layer
Doc66: strong-reference closure and real-review signal package
Doc67: boundary cleanup and quality reinforcement
```

If any older document conflicts with Doc68 on prompt recipe tuning, use Doc68.
If Doc68 and Doc69 conflict on prompt atom details, use Doc69.
If any older document conflicts on architecture ownership, keep Doc50/Doc67:
reusable visual intelligence belongs in the V3 Visual Capability Cluster.

## 2. Problem Statement

V3 already has the correct architecture and a working quality loop:

```text
Project Mode
  -> Scenario Runtime
  -> V3 Brain checkpoints
  -> Visual Capability Cluster
  -> Provider prompt consumer
  -> Post-generation review and bounded retry
```

The remaining quality gap is not a missing framework. The gap is the granularity
of the photographic knowledge inside existing modules:

```text
portrait outputs can still feel slightly AI-like
same-person sets can over-repeat the same face angle/expression
delivery-suite roles can be technically distinct but not directed enough
product lifestyle outputs can remain too studio-safe
real-review prompts do not yet carry enough casebook-informed acceptance detail
```

## 3. Non-Negotiable Boundary Rules

Doc68 must not:

```text
call V1/V2 runtime code
import V2 services at runtime
create a second Visual Capability Cluster
create a second mode director
create a second human realism module
create a second product-suite director
move reusable visual rules into CentralCreativeBrain
move visual retry issue semantics into provider routing
show engineering fields to normal frontend users
```

Doc68 may:

```text
add a V3-owned recipe helper inside visual_cluster
extend existing visual_cluster child modules
add data-driven prompt atoms and review targets
extend provider prompt consumption of existing cluster metadata
add focused tests and validation scripts
add auxiliary reference docs for future developers
```

## 4. Product Goal

Beginner-facing goal:

```text
The user writes one simple request and receives images that feel like a
professional photographer or art director made a small commercial set.
```

Internal quality goal:

```text
Use casebook-informed visual atoms to make V3 better at:
  realistic human skin and expression
  same identity without cloned stills
  purposeful four-mode image differences
  product truth plus stronger lifestyle context
  image-specific review and retry language
```

## 5. V2 Experience To Absorb

V2 should be treated as historical evidence, not a runtime dependency.

High-value V2 patterns:

```text
PromptCase
  structured case entity with raw prompt, prompt_atoms, visual_features,
  style_tags, use_case_tags, risk_tags, and quality_score

prompt_atoms
  subject, scene, composition, lighting, color_palette, material_texture,
  camera_lens, mood, typography, post_processing, constraints

visual_signal_brief
  short reusable visual DNA that helps the brain and composer reuse structure
  without copying protected content

visual_grammar_lock
  locked elements such as composition, hierarchy, lighting, layout rhythm,
  background density, mood, and information treatment

replaceable semantic content
  actual person, product, logo, text, props, business meaning, and scene facts

hard reference roles
  face, subject, logo, product, and background references must not silently
  degrade to prompt-only text when provider reference images are available
```

Doc68 adapts these ideas into V3-owned recipe data and helper functions.

## 6. GPT-Image-2 Prompt Pattern Experience To Absorb

The referenced GPT-Image-2 case repository is useful as prompt-design evidence.
Do not copy large prompt blocks. Distill recurring atoms:

```text
camera position and lens language
pose, gaze, expression, hand placement, body turn
wardrobe fabric and styling family
skin, hairline, eye, and light interaction details
scene depth, foreground/background layering, atmosphere
role-specific framing and crop
product material, label, surface, edge, shadow, and lived-in context
negative constraints for watermark, random text, collage, and AI marks
```

The distilled form must live in V3 as small reusable recipe fragments, not as
verbatim external prompt copies.

## 7. Implementation Location

Add a helper module:

```text
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/casebook_recipes.py
```

This helper is a V3-owned recipe library used by existing modules:

```text
human_photorealism.py
  consumes portrait realism fragments and anti-AI-face review targets

mode_role_director.py
  consumes four-mode role overlays for portrait, product, and generic subjects

vertical_agents/ecommerce_pack.py
  keeps ecommerce pack ownership, but must reuse the same casebook overlay for
  product slot recipes so product paths do not bypass visual_cluster recipes

doc66_closure.py
  consumes strong-reference variation and do-not-inherit guidance where useful

providers.py
  consumes casebook metadata already exported through role recipes and human
  realism guidance; provider does not create or select recipes

vision_provider.py / vision_inspector.py
  may receive stricter review issue language and prompt targets, but review
  ownership stays in visual_cluster
```

The helper must not become a standalone capability runtime unless a later doc
requires it. For this phase, it is a data/helper layer.

## 8. Recipe Types

### 8.1 Human Photorealism Recipe

Adds concise fragments for:

```text
real photographed skin texture
subtle pores and tonal variation
small natural asymmetry
believable under-eye and cheek detail
realistic hairline, flyaway hair, and non-perfect strands
specific micro-expression instead of template smile
real camera perspective and photographed facial planes
non-plastic makeup highlights
natural eye moisture and catchlight behavior
```

Negative fragments:

```text
AI influencer face
beauty-filter mask
wax skin highlights
over-smoothed face
identical face angle across set
same expression copied across set
synthetic glassy eyes
over-symmetric face
```

### 8.2 Portrait Role Recipe

Strengthens delivery-suite portrait roles:

```text
cover hero
  confident near-camera moment, cover-safe crop, clean shoulders

closer subject frame
  softer expression, hair/skin detail, shallow depth

side or three-quarter angle
  different face plane, body turn, gaze away or toward scene

wide lifestyle context
  full or three-quarter body, environmental interaction, scene depth
```

The same identity is preserved through broad face/age/body/hair/wardrobe
direction, not by repeating one still.

### 8.3 Product Lifestyle Recipe

Strengthens product suites:

```text
hero object
  clear silhouette, premium light, inspectable product truth

context scene
  real table, hand/use context, outdoor or lived-in surface where requested

detail/material closeup
  texture, material edge, condensation, label area, functional detail

layout-safe cover
  clean negative space and strong commercial crop
```

The recipe must preserve visible product truth and label/logo readability when
reference images are available.

### 8.4 Four-Mode Recipe Overlay

Each mode receives a different visual distance budget:

```text
selection_candidates
  close alternatives; small visible expression/pose/crop/detail differences

delivery_suite
  purposeful commercial set; each image has a different publishing duty

creative_exploration
  broader mood/scene/styling/lens concepts while preserving core subject truth

format_layout_adaptation
  same idea; crop, safe area, aspect ratio, and layout affordance change
```

## 9. Provider Prompt Consumption

Provider code must not decide visual strategy. It may only render the final
cluster contract into prompt text.

Provider prompt additions may include:

```text
casebook camera recipe
casebook realism recipe
casebook product recipe
casebook role difference rule
casebook review target summary
```

Rules:

```text
keep prompt compact
dedupe repeated guidance
avoid contradictory pressure
avoid ecommerce/product terms in pure General Template unless product language
is explicitly allowed
preserve selected-reference closure over generic recipe suggestions
```

## 10. Quality Review And Retry

Doc68 extends issue-specific retry language but does not add a new retry loop.

Retry emphasis:

```text
over-smoothed face
same expression repetition
same head angle repetition
same camera distance repetition
AI-generated badge or watermark
product lifestyle too studio-safe
role collapse in delivery-suite mode
creative exploration too similar
format adaptation changed identity instead of layout
```

Retry patches must be specific:

```text
add natural skin and micro-expression guidance for AI-face issues
add role-specific pose/camera/crop duties for over-cloning
add lived-in context, hand/use, outdoor surface, or environment depth for
product lifestyle issues
add exact slot/role guidance when product suite roles collapse
```

## 11. UI Principle

No new beginner UI is required for Doc68. If surfaced later, it must stay plain:

```text
V3 used your chosen direction as the reference.
V3 planned different image jobs for this set.
V3 checked for repeated faces, random text, and obvious visual problems.
```

Forbidden in default UI:

```text
casebook module id
prompt atoms
provider metadata
raw recipe json
scores
debug issue payloads
```

## 12. Development Plan

### Phase 1: Documentation

Create:

```text
68_V3_CASEBOOK_GUIDED_PHOTOGRAPHIC_RECIPE_TUNING_SPEC.md
68A_V3_CASEBOOK_DISTILLATION_REFERENCE.md
68B_V3_FOUR_MODE_RECIPE_MATRIX.md
68C_V3_DOC68_VALIDATION_AND_ACCEPTANCE_MATRIX.md
```

Update:

```text
README.md
13_STEP_BY_STEP_DELIVERY_PLAN.md
29_V3_DEVELOPMENT_DOCUMENT_EXECUTION_AUDIT.md
67_V3_VISUAL_BOUNDARY_AND_QUALITY_REINFORCEMENT_SPEC.md
```

### Phase 2: Recipe Helper

Add:

```text
app/shared_capabilities/visual_cluster/casebook_recipes.py
```

Minimum functions:

```text
human_photorealism_casebook(...)
apply_role_recipe_casebook_overlay(...)
strong_reference_casebook_rules(...)
provider_casebook_prompt_lines(...)
```

### Phase 3: Existing Module Extensions

Extend, do not duplicate:

```text
human_photorealism.py
mode_role_director.py
vertical_agents/ecommerce_pack.py
doc66_closure.py
providers.py
vision_provider.py if useful
```

### Phase 4: Tests

Add focused tests:

```text
test_v3_doc68_casebook_guided_quality.py
```

Required assertions:

```text
Doc68 helper is V3-owned and has no V2 runtime imports
human photorealism includes casebook skin/expression/camera guidance
four modes receive distinct role overlays
portrait delivery suite uses identity-with-variation rules
product delivery suite includes stronger lived-in context guidance
ecommerce vertical pack preserves ownership while reusing casebook overlays
provider prompt exposes casebook lines only as consumed metadata
General Template prompt stays product-language clean
```

### Phase 5: Regression And Real Validation

Run:

```text
focused Doc68 tests
existing Doc67 boundary tests
human photorealism tests
mode-aware director tests
provider prompt tests
project mode tests if touched behavior affects project context
compile audit
diff check
real portrait validation
real product validation
```

## 13. Completion Criteria

Doc68 is complete when:

```text
documents are present and linked
no duplicate visual module is created
casebook helper lives under visual_cluster
existing modules consume casebook recipes
focused and relevant regression tests pass
real portrait generation is attempted and assessed
real product generation is attempted and assessed
remaining Lovart gap is honestly stated
no V1/V2 runtime dependency is introduced
```
