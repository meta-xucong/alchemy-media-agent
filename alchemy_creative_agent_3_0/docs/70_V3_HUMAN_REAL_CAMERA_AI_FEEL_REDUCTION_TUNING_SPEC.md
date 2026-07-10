# 70 V3 Human Real-Camera AI Feel Reduction Tuning Spec

Doc94 correction note:

```text
Doc70's real-camera and anti-filter principles remain active. Named ethnicity,
season, or beauty-style examples are validation fixtures, not runtime routing
conditions. The current implementation uses universal texture, specularity,
asymmetry, age-fidelity, and camera-response variables.
```

Status: accepted micro-tuning document after Doc69.

This document is a narrow quality pass. It does not add a new architecture
module. It tunes the existing V3 Visual Capability Cluster so photoreal human
outputs look less like polished AI beauty portraits and more like commercial
images captured by a real camera.

## 1. Why This Pass Exists

Doc69 completed prompt atom absorption, provider prompt rendering, and local
generated-mark review. Real portrait validation improved, but the remaining
portrait gap is:

```text
same person consistency: acceptable
role separation: acceptable
artifact cleanliness: improved
AI feel: still too polished, beauty-filtered, and template-smiling
```

The next optimization must therefore target:

```text
skin realism over poreless beauty
real lens imperfection over render sharpness
candid micro-expression over template smile
slightly messy hair/fabric over synthetic neatness
natural asymmetry over idol photocard symmetry
real facial individuality over beautified AI geometry
```

## 2. Compatibility

Doc70 must remain fully compatible with Docs50-69:

```text
Project Mode unchanged.
CentralCreativeBrain unchanged.
Scenario Pack contracts unchanged.
Provider routing unchanged.
Visual Capability Cluster remains the owner.
Doc69 prompt atom layer remains the implementation home.
No V1/V2 runtime dependency.
No runtime web case search.
No duplicate human realism module.
```

If Doc70 conflicts with Doc69 on portrait AI-feel wording, Doc70 wins. If it
conflicts on architecture ownership, Docs50 and 67 win.

## 3. Case Lessons To Absorb

The reference cases repeatedly show these useful non-sexual patterns:

```text
real camera medium:
  35mm film, CCD, mobile phone, eye-level, intimate medium shot, handheld feel

natural imperfections:
  fine grain, slight overexposure, mild halation, soft edge falloff,
  slight motion softness, imperfect framing

human texture:
  visible micro pores, uneven tonal transitions, under-eye texture,
  natural catchlights, realistic eyelids, fine hair strands, loose hair,
  fabric wrinkles and drape

anti-AI beauty:
  no plastic skin, no digital oversharpening, no airbrushing,
  no template smile, no perfect idol photocard face

polish reinterpretation:
  if upstream brain or user wording says polished, refined, premium,
  commercial, or beauty, human portrait generation must interpret this as
  camera-ready real-person photography, not beauty-app smoothing,
  face slimming, enlarged eyes, V-shaped chin, or idol-card retouch

series variation:
  same person can remain recognizable while expression, gaze, head angle,
  camera distance, and body posture vary naturally
```

Doc70 must use these as distilled rules, not copied prompts.

## 4. Implementation Targets

Update only existing files:

```text
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/casebook_recipes.py
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/human_photorealism.py
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/vision_inspector.py
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/vision_provider.py
```

Tests may be added in:

```text
alchemy_creative_agent_3_0/tests/test_v3_doc70_human_ai_feel_reduction.py
```

## 5. Prompt Tuning Rules

### 5.1 Positive Real-Camera Rules

Photoreal human prompts should add compact pressure for:

```text
soft 35mm or CCD-inspired real-camera imperfection
fine film grain or sensor grain where style permits
subtle halation or highlight bloom, not glossy AI shine
slight edge softness, not digital oversharpening
minor handheld/candid framing imperfections
under-eye texture, smile-line hints, skin-tone variation
loose hair strands, wind-displaced hair, real fabric wrinkles
```

### 5.2 Anti-AI Negative Rules

Photoreal human prompts should reject:

```text
beauty-app face
idol photocard polish
skin-blur retouching
flawless porcelain mask
overly symmetrical V-line jaw
same perfect smile repeated
oversized anime-like eyes in a realistic request
hyper-clean fashion render
auto face-slimming
enlarged beauty-filter eyes
perfect V-shaped chin
liquified face proportions
algorithmically pretty generic face
too-clean stock-photo model face
```

### 5.3 Role Rules

For delivery suites:

```text
cover_hero:
  commercially usable but not a default perfect smile.
  Must feel like one real frame from the shoot.

subject_focus:
  closer detail should show skin, hair, fabric, and imperfect expression.

angle/context roles:
  use non-identical gaze, head angle, body turn, and camera distance.
```

For selection candidates:

```text
Keep alternatives close, but vary micro-expression, eye focus, mouth tension,
hair movement, or crop so options are not cloned beauty stills.
```

## 6. Review And Retry

Add or verify issue codes:

```text
beauty_app_face
idol_photocard_polish
skin_blur_retouching
over_uniform_skin_tone
over_sharp_ai_detail
perfect_smile_repetition
face_slimming_filter
beautified_facial_geometry
generic_ai_beauty_identity
```

These must create retry patches that add:

```text
real-camera imperfection
skin tonal variation
under-eye and eyelid detail
loose hair/fabric detail
candid micro-expression
less beauty-filter polish
natural jaw contour, real eyelid folds, lip texture, and individual facial character
```

Doc53 retry budget still limits loops.

## 7. Tests

Required focused tests:

```text
Doc70 code remains V3-owned and has no V1/V2 runtime import.
Human photorealism guidance includes real-camera imperfection and anti-beauty-app rules.
Portrait role recipes include candid expression and non-photocard anti-polish rules.
Provider prompt renders Doc70 camera/texture/negative atoms.
New issue codes create retry patches.
Human portrait provider prompt reinterprets polished/premium/beauty wording as camera-ready realism.
Chinese style signals such as premium/portrait/beauty are not broken by mojibake and do not force polished AI-beauty finish.
Stylized/anime requests remain exempt from human photorealism.
```

## 8. Real Validation Loop

After implementation:

```text
1. Run focused tests.
2. Run relevant regression tests.
3. Run real portrait generation with the same East Asian summer portrait prompt.
4. Inspect contact sheet.
5. If the output still looks too AI-polished, tune again inside the same files.
6. Stop only when the current version is materially better or provider limits
   make further local prompt tuning unlikely to help.
```

## 9. Acceptance Criteria

Doc70 is acceptable when:

```text
prompt rules are stronger but not bloated;
General non-human/stylized outputs are not damaged;
provider prompt contains real-camera, texture, and anti-beauty-app guidance;
tests pass;
real output has less AI beauty polish than Doc69;
remaining limitations are clearly assessed.
```
