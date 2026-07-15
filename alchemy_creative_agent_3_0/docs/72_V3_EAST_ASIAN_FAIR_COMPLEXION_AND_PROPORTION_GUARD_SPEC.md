# 72 V3 East Asian Fair Complexion And Proportion Guard Spec

> Historical/compatibility notice (Doc128): retain this document only as a
> regression observation. It must not select a shared runtime branch, add a
> demographic prompt fragment, or become a Provider/retry default for new V3
> jobs.

Doc94 supersession note:

```text
Doc72 remains a historical regression record. Its proportion, flattering-light,
and unintended-color-cast lessons are retained through Doc94's universal
human-rendering variables. East Asian, summer, and fair-complexion wording no
longer defines a shared runtime branch or unconditional provider default.
```

## 1. Purpose

Doc72 is a narrow compatibility pass after Doc71.

Doc70 reduced polished AI-face feel. Doc71 restored fresh attractive realism.
The latest real-output review exposed a remaining failure mode:

```text
Some East Asian summer portrait outputs became too dark, gray, or plain in the
name of realism, and close crops could make the head, neck, shoulders, or upper
body proportions feel less flattering.
```

Doc72 fixes that without changing the V3 architecture.

The rule is:

```text
For East Asian fresh / beauty / summer portrait requests, when the user does
not explicitly ask for tan, dark, bronze, outdoor-tanned, or documentary grit,
V3 should preserve a clean fair luminous complexion created by light and color
balance. This is not skin whitening, not poreless beauty smoothing, and not
identity replacement.
```

## 2. Architecture Boundary

Doc72 stays inside the existing V3 Visual Capability Cluster:

```text
visual_cluster.casebook_recipes
visual_cluster.human_photorealism
visual_cluster.vision_inspector
visual_cluster.vision_provider
generation_router.providers provider-prompt rendering
```

It must not:

```text
add a new central brain path
call V1/V2 runtime code
create a duplicate human beauty module
change Project Mode, Job, Scenario Runtime, provider selection, or frontend flow
```

Doc72 is a tuning authority under the current human visual chain:

```text
Doc65 human photorealism
  -> Doc68 casebook recipes
  -> Doc69 prompt atoms
  -> Doc70 anti AI-face real-camera tuning
  -> Doc71 attractive realism balance
  -> Doc72 East Asian fair complexion and proportion guard
```

## 3. What Doc72 Adds

### 3.1 Fair Complexion Guard

For applicable human portrait prompts, V3 should add positive guidance:

```text
clean fair luminous complexion when the brief is East Asian, fresh, summer, or
beauty oriented and no tan/dark/bronze instruction exists
bright translucent facial color from high-key daylight and soft bounce light
do not darken or tan East Asian skin by default
preserve natural East Asian identity and real skin texture
```

V3 should add negative guidance:

```text
suppressed fair complexion
unnecessarily darkened skin
forced tan or bronze cast unless requested
gray-brown skin cast
dull yellow or green facial cast
fake whitening mask
bleached beauty-filter skin
```

The distinction is important:

```text
Allowed:
  fair, clean, luminous complexion from lighting, exposure, color balance, and
  commercial portrait craft

Rejected:
  artificial whitening filter, face replacement, over-smoothing, poreless glow,
  identity change, and skin tone flattening
```

### 3.2 Attractive Face Guard

Doc72 should preserve the Doc70 anti-beauty-app rules, but it must not push
portraits into unattractive plainness.

Positive guidance:

```text
harmonious natural facial features
awake eyes and relaxed facial muscles
flattering but realistic face angle
natural facial character without generic AI beauty geometry
```

Negative guidance:

```text
unflattering face drift
flattened facial attractiveness
tired or dull face caused by over-documentary realism
face made less attractive by shadow, color cast, or bad crop
```

### 3.3 Head / Body / Shoulder Proportion Guard

Close portrait crops must stay natural and flattering.

Positive guidance:

```text
natural head-to-body proportion
balanced neck and shoulder line
upper-body crop that preserves real body scale
flattering shoulder angle and non-compressed torso
```

Negative guidance:

```text
oversized head
enlarged face scale
short compressed neck
compressed shoulders
warped upper body
pinched torso
bad head-to-body ratio
awkward shoulder crop
```

For subject-focus roles, the rule is stricter:

```text
Closer crop may increase facial detail, but it must not make the head too large
or collapse the neck/shoulder/upper-body relationship.
```

## 4. Review And Retry Issue Codes

Doc72 adds retryable issue codes:

```text
suppressed_fair_complexion
forced_tan_or_bronze_cast
gray_brown_skin_cast
head_body_proportion_distortion
oversized_head
compressed_neck_shoulders
unflattering_face_drift
```

Retry patch requirements:

```text
restore clean fair luminous complexion through exposure, bounce light, and color
balance, not through whitening filter
avoid darkening or tanning East Asian skin unless explicitly requested
preserve natural head-to-body, neck, shoulder, and upper-body proportions
use a flattering real-camera crop with balanced face scale
```

## 5. Provider Prompt Rendering

When human photorealism applies, the provider prompt should include a compact
Doc72 contract:

```text
East Asian portrait aesthetic guard: for East Asian fresh / beauty / summer
portrait requests with no explicit tan, dark, or bronze instruction, keep a
clean fair luminous complexion from high-key daylight, soft bounce light, and
color balance; do not darken or tan the skin by default; avoid fake whitening
mask; preserve natural head-to-body, neck, shoulder, and upper-body proportions.
```

Provider prompt text must remain product-language clean for General Template.

## 6. Tests

Add a focused Doc72 test file that proves:

```text
Doc72 is V3-owned and has no V1/V2 runtime dependency
HumanPhotorealismLayer emits fair-complexion and proportion guidance
Negative guidance rejects suppressed fair skin, forced tan, gray-brown cast,
oversized head, and compressed neck/shoulders
Provider prompts render the Doc72 compact contract
VisionOutputInspector turns Doc72 issue codes into bounded retry patches
Stylized/anime requests remain exempt
```

Regression tests must include Doc70, Doc71, provider output production, General
Template prompt cleanliness, and mode-aware role director tests.

## 7. Acceptance Criteria

Doc72 is acceptable when:

```text
1. No architecture layer is added outside the Visual Capability Cluster.
2. The latest docs mark Doc72 as the current human portrait tuning authority.
3. Realistic human texture and anti-AI-face rules remain intact.
4. East Asian summer portraits no longer get unnecessary dark/tan/gray skin.
5. The prompt clearly separates fair luminous complexion from fake whitening.
6. Close crops preserve natural head/neck/shoulder/upper-body proportions.
7. Review/retry can explicitly repair complexion and proportion failures.
8. Focused, regression, compile, and diff checks pass.
9. A real same-prompt portrait generation is attempted and compared to Doc71.
```
