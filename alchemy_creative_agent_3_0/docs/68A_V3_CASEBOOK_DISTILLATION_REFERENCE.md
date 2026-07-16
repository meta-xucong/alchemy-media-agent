# 68A V3 Casebook Distillation Reference

> **Doc135 forward-path note:** casebook material is retrospective evidence
> only. It must not be revived as a keyword router, case-derived prompt stack
> or static renderer recipe for a new V3 Job.

Doc93 compatibility note:

```text
This casebook remains advisory evidence. Any broad face/body/hair/wardrobe
recipe is conditional guidance, not a default identity lock. Doc93 reference
role and channel policy decide what reaches generation.
```

Status: auxiliary reference for Doc68.

This document explains how to turn V2 case experience and GPT-Image-2 prompt
examples into V3-owned recipe fragments without copying runtime code or long
external prompts.

## 1. Source Boundaries

Allowed sources:

```text
V2 documentation as product and architecture evidence
V2 code as pattern evidence only
V2 seed case structures as schema inspiration
public GPT-Image-2 case repositories as prompt-pattern evidence
V3 real validation outputs and contact sheets
```

Not allowed:

```text
runtime imports from V2
calling V2 APIs
reading V2 storage during V3 jobs
copying long public prompt blocks verbatim into provider prompts
using third-party characters, brands, faces, or protected identities
```

## 2. Distillation Method

For every useful case, extract only reusable atoms:

```text
subject class
scene class
composition skeleton
camera distance
camera angle
pose/action axis
lighting logic
palette rhythm
material/skin/product texture
background density
negative constraints
review target
```

Do not preserve:

```text
specific named person
specific brand or logo
protected character
long sentence structure
third-party source metadata inside final prompts
```

## 3. V2 Patterns To Preserve

### 3.1 PromptCase Thinking

V3 should reuse the idea of prompt atoms:

```text
subject
scene
composition
lighting
color_palette
material_texture
camera_lens
mood
post_processing
constraints
```

In Doc68 these atoms become static V3 recipe fragments, not a new case-search
runtime.

### 3.2 Visual Signal Brief

V2's visual signal brief is useful because it shortens a case into visual DNA:

```text
composition discipline
lighting logic
accent color rhythm
material behavior
background density
commercial finish
```

Doc68 should use this style for provider-facing fragments.

### 3.3 Visual Grammar Lock

Keep the V2 distinction:

```text
locked visual grammar:
  composition, hierarchy, lighting, rhythm, background density, mood

replaceable semantics:
  person, product, logo, campaign copy, specific props, business facts
```

Doc68 strengthens the quality of the locked visual grammar; it does not change
who owns selected-reference continuation.

## 4. GPT-Image-2 Prompt Patterns To Preserve

Useful patterns from GPT-Image-2 prompt examples:

```text
structured camera and pose options
foreground subject block
technical finish block
global visual settings
role-specific composition
reference-person logic separated from scene logic
material and light interaction detail
multi-image character sheet thinking for identity variation
```

Use them as recipe shape, not as prompt copy.

## 5. Portrait Distillation Rules

Extract:

```text
face direction:
  broad face shape, age band, feature relationship, expression range

body direction:
  body type, posture family, shoulder line, height/build impression

hair direction:
  broad color, length range, movement, parting, texture

wardrobe direction:
  styling family, fabric, color family, seasonal cue

camera direction:
  lens feel, crop, distance, angle, depth of field

scene direction:
  primary environment, light source, background depth, atmosphere
```

Keep fixed:

```text
recognizable person direction
age/body/hair/wardrobe family
lighting and color world
```

Allow varied:

```text
expression
gaze
head angle
body turn
pose
hand placement
camera distance
crop
minor hair movement
scene depth
```

## 6. Product Distillation Rules

Extract:

```text
silhouette
material
label/logo placement
packaging proportions
edge/shadow/reflection behavior
surface and use context
lifestyle environment
commercial role
```

Keep fixed:

```text
product shape
material/color truth
label/logo readability when visible
proportions and package silhouette
```

Allow varied:

```text
surface
camera angle
environment
props
lighting nuance
crop/layout
usage scene
```

## 7. Resulting V3 Artifacts

Doc68 code should produce these artifacts inside existing contracts:

```text
human_photorealism_guidance.positive_prompt_fragments
human_photorealism_guidance.negative_prompt_fragments
human_photorealism_guidance.reference_preserve_rules
human_photorealism_guidance.review_targets
role_specific_generation_plan.role_recipes[*].metadata
mode_quality_profile.prompt_guidance
strong_reference_closure_package.provider_prompt_rules
provider final prompt lines
post-generation review issue language
```
