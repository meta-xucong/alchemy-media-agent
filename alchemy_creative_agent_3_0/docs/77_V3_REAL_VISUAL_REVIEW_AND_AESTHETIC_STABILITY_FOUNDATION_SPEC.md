# 77 V3 Real Visual Review And Aesthetic Stability Foundation

## 1. Purpose

Doc77 is a foundation-quality pass.

It responds to the current gap:

```text
automatic curation is constrained by unstable upstream image generation,
but real visual review and aesthetic stability can still be strengthened.
```

The goal is not to add another scenario module. The goal is to make every
generated image pass a stronger baseline:

```text
1. The image should be clean enough for direct use.
2. The image should look visually intentional, not generic or unstable.
3. Human/photo outputs should avoid obvious AI finish.
4. Retry advice should be concrete and bounded when the issue is fixable.
```

## 2. Compatibility

Doc77 extends:

```text
Doc53 retry guardrails
Doc55 post-generation vision inspection
Doc65 human photorealism layer
Doc67 visual boundary cleanup
Doc70-72 human realism and complexion tuning
Doc74 complex prompt fidelity
Doc75 identity hero / strict visual review closure
Doc76 foundation vs specialized-template governance
```

Doc77 does not replace:

```text
Project Mode
ScenarioRuntime
Scenario Packs
CentralCreativeBrain
LLM Brain adapter
General Template four-mode selector
E-Commerce / Photography / Brand specialized template ownership
```

## 3. Boundary Rule

Doc77 belongs to the V3 foundation because it improves almost every image.

Allowed implementation locations:

```text
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/
alchemy_creative_agent_3_0/app/generation_router/
alchemy_creative_agent_3_0/app/product_api/ review and retry paths
```

Forbidden changes:

```text
do not add ecommerce listing slots to General Template
do not add photographer-session package roles to General Template
do not put Doc77 child logic inside CentralCreativeBrain
do not bypass the Visual Capability Cluster
do not raise retry budgets beyond Doc53 rules
```

Doc76 remains the placement authority. Doc77 only tunes foundation review and
quality thresholds.

## 4. Real Visual Review Gap

Current review can catch many known artifacts, but it is still too permissive
for weak but technically valid images.

Doc77 adds foundation-level issue classes:

```text
weak_aesthetic_finish
generic_stock_photo_finish
flat_low_contrast_finish
overexposed_washout
underexposed_muddy_frame
unbalanced_color_grade
weak_subject_readability
weak_depth_and_material_separation
unstable_composition_balance
overprocessed_hdr_finish
uncanny_micro_detail
low_resolution_output
```

These are not vertical deliverable roles. They are base visual quality failures.

## 5. Aesthetic Stability Gap

The system must avoid "technically generated but aesthetically weak" outputs.

Foundation aesthetic stability means:

```text
clear subject readability
intentional framing
balanced exposure
stable color grade
natural contrast
believable depth
material and skin texture that match the request
no generic stock-photo finish when a more photographic scene is requested
no overprocessed HDR, waxy detail, or synthetic micro-sharpness
```

For human photo tasks, Doc77 also reinforces:

```text
attractive but natural face
real skin texture
fair East Asian complexion when appropriate and not contradicted
no muddy/dark cast unless requested
no cloned AI expression or beauty-app geometry
```

## 6. Implementation Requirements

### 6.1 Vision Inspector

The post-generation inspector must understand Doc77 issue codes.

It must:

```text
add retryable issue codes for aesthetic stability failures
return concrete retry patches for those codes
keep user-facing summaries simple
keep low-confidence or provider-error cases manual, not retryable
use local image heuristics only for objective file-level problems
```

Local heuristics may detect:

```text
missing/unreadable files
low resolution
extreme washout
extreme underexposure
extremely flat low-contrast image
```

Local heuristics must not pretend to judge identity, beauty, or product truth.
Those remain provider-review or metadata-review signals.

### 6.2 Vision Provider Prompt

The visual inspection prompt must explicitly ask the provider to judge:

```text
subject readability
composition balance
exposure stability
color-grade stability
depth/material separation
generic stock-photo finish
overprocessed HDR or synthetic detail
overall direct-use visual polish
```

For General Template, summaries must avoid ecommerce language.

### 6.3 Strict Review Policy

The Visual Capability Cluster must expose Doc77 as an extension of the existing
strict visual review policy.

It must add:

```text
new retryable Doc77 issue codes
pass conditions for foundation aesthetic stability
prompt additions for intentional real-camera finish
negative additions for generic/unstable/overprocessed output
```

This is an extension of `strict_visual_review_policy`, not a new top-level
runtime framework.

### 6.4 Provider Prompt Consumption

The image provider prompt must consume Doc77 rules through existing visual
cluster metadata.

It must:

```text
include compact foundation aesthetic rules
avoid bloated prompt walls
keep product-specific truth rules only when product language is allowed
keep human realism rules only for human/photo tasks
```

### 6.5 Auto Retry

Doc77 issue codes may trigger bounded retry only when:

```text
the issue is retryable
the retry patch has actionable guidance
the issue did not already repeat in the same job retry loop
the retry budget remains available
```

Do not retry:

```text
provider errors
timeouts
low-confidence review
policy/safety blocks
purely subjective preference without a concrete issue code
```

## 7. Acceptance Tests

Required focused tests:

```text
1. Doc77 issue codes are accepted by VisionOutputInspector as retryable.
2. Doc77 retry patches include prompt and negative guidance.
3. StrictVisualReviewPolicy exposes Doc77 pass conditions and retryable codes.
4. Provider prompt consumes Doc77 strict review rules.
5. Product API retry whitelist includes Doc77 retryable codes.
6. Local image heuristic can flag objective low-resolution / exposure issues.
7. Boundary test confirms Doc77 does not add new General Template vertical roles.
```

Required regression tests:

```text
Doc75 strict review tests still pass.
Doc70-72 human realism tests still pass.
Doc55 post-generation review tests still pass.
Visual auto retry tests still pass.
Provider production prompt tests still pass.
```

## 8. Current Status

```text
DOC77 IS THE CURRENT FOUNDATION QUALITY AUTHORITY FOR:
real visual review strictness
aesthetic stability issue codes
foundation retry patch wording
```

It does not supersede Doc76 placement governance.

