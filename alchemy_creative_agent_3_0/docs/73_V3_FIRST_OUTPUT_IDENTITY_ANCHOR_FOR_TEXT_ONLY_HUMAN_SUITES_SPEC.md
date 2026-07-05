# 73 V3 First Output Identity Anchor For Text-Only Human Suites Spec

## 1. Purpose

Doc73 fixes a real-output gap found after Doc72:

```text
Two images in the same text-only human portrait suite could share style,
wardrobe, hair color, and scene, but still look like two similar models instead
of the same person.
```

The accepted behavior is:

```text
If the user manually selected or uploaded one or more reference images, use the
user-selected references first.

Only when no user reference exists, and the job is a multi-image photoreal human
suite, V3 may use the first generated output in the same job as a temporary
strong identity anchor for subsequent outputs.
```

## 2. Architecture Boundary

Doc73 is not a new framework.

It lives in the existing V3 generation loop and provider reference path:

```text
CentralCreativeBrain.run_generation_loop
  -> per-asset GenerationRequest metadata
  -> ProductionImageGenerationProvider reference_assets
  -> image-edit/reference provider path
```

It must not:

```text
replace Project Mode selected-output references
override user-selected project references
change Brand Memory
add V1/V2 runtime calls
add a new central-brain provider
apply to E-Commerce/product suites by default
```

## 3. Priority Rule

Reference priority is fixed:

```text
1. User-selected project output references
2. User-uploaded references
3. Explicit reference_assets passed by Project Mode or API
4. Auto first-output identity anchor
5. Text-only prompt consistency
```

The auto anchor is disabled when any explicit user reference exists.

## 4. Auto Anchor Behavior

When enabled:

```text
first output:
  generated from the text prompt and role recipe

second and later outputs:
  receive the first output file as a hard identity reference
```

The generated reference payload must include:

```text
source_type = generated_first_output
use_policy = identity
role = identity_anchor
strength = hard
provider_input_required = true
lock_targets:
  broad face shape
  eye shape and spacing
  nose-mouth relationship
  jawline direction
  age impression
  body type and proportions
  hair color and broad length range
  wardrobe category
  lighting language
```

Allowed changes remain:

```text
expression
pose
head angle
camera angle
crop
hand placement
hair movement
scene depth
```

Forbidden drift:

```text
different face identity
different age impression
different jaw/eye/nose-mouth relationship
different body type
cloned exact still
same frozen expression
```

## 5. Applicability

Enable only when all are true:

```text
real image generation is active
requested image count / actual suite asset count is at least 2
the suite is human / portrait / real-person led
the request is not stylized anime/cartoon/illustration
the scenario is not E-Commerce
no explicit user-selected or uploaded reference exists
```

## 6. Provider Wording

Identity reference wording should be explicit enough for GPT image 2:

```text
preserve broad face shape, eye shape and spacing, nose-mouth relationship,
jawline direction, age impression, body type, broad hair color/length, wardrobe
category, and lighting language
```

This wording is stronger than generic "same person direction" and should also
help manual user-selected references.

## 7. Tests

Focused tests must verify:

```text
No user reference:
  first request has no auto reference
  second request receives the first output as a hard identity reference

User reference exists:
  auto anchor is disabled
  second request keeps only the user's selected reference
```

Regression must include Doc72, Doc71, Doc70, mode-role, provider, and General
Template cleanliness tests.

## 8. Acceptance Criteria

Doc73 is complete when:

```text
1. Text-only human suites use first-output identity anchor for later images.
2. User-selected or uploaded references always win over auto anchor.
3. The anchor is passed as a real reference image, not only prompt text.
4. Provider prompt preserves specific identity traits while allowing role-level
   pose/expression/camera changes.
5. Product/E-Commerce suites are not affected by default.
6. Focused and regression tests pass.
7. A real GPT image 2 portrait suite is generated and visually compared.
```
