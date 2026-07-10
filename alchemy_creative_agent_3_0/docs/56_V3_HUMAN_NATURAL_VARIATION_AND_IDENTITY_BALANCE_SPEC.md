# 56 V3 Human Natural Variation And Identity Balance Spec

Doc93 compatibility note:

```text
Natural variation remains required. Any earlier `identity and style anchor`
wording is narrowed by Doc93: an ordinary portrait upload provides identity
truth, while style channels remain prompt owned unless explicitly assigned.
Selected outputs may support approved style direction but cannot override the
current explicit prompt or uploaded identity truth.
```

## 1. Status And Authority

This document is the next optimization authority after documents `51`, `54`,
and `55` for portrait, model, spokesperson, character, and human-led commercial
image series.

Authority chain:

```text
Doc50:
  Owns the rule that reusable visual enhancement belongs in the V3 native
  Visual Capability Cluster.

Doc51:
  Owns strong selected-image references, identity/product/brand locks, and
  project-scoped consistency contracts.

Doc54:
  Owns General Template variation modes:
  selection candidates, delivery suite, creative exploration, and
  format/layout adaptation.

Doc55:
  Owns real post-generation image inspection and review merge behavior.

Doc56:
  Owns the balance between human identity consistency and natural commercial
  variation. It prevents V3 from interpreting consistency as copying the exact
  same face expression, head angle, pose, hair styling, and camera angle across
  every generated image.

Doc58:
  Extends Doc56 with the next implementation phase: selected outputs become
  project-scoped Identity Anchors, continuation jobs use those anchors as strong
  references, and batch-level review checks both identity drift and over-cloned
  repetition. Doc56 owns the principle; Doc58 owns the stronger project-loop
  execution plan.

Doc61:
  Adds the real portrait validation and Lovart benchmark acceptance layer.
  It does not replace Doc56's principle; it checks whether the implemented
  system actually balances same-person consistency with natural commercial
  variation in generated portrait suites.

Doc62:
  Extends the implementation side of Doc56 for General Template portrait
  delivery suites by assigning expression, gaze, pose, crop, scale, and scene
  duties to each role. Doc56 still owns the principle; Doc62 owns the stronger
  role-level prompt pressure.
```

If documents conflict about human portrait consistency, Doc56 wins over older
wording that says to lock face, hair, outfit, camera, or style without
distinguishing stable identity anchors from natural presentation variation.

Doc56 does not:

```text
rewrite Project Mode
replace ScenarioRuntime
replace Product API
replace the Visual Capability Cluster
unfreeze E-Commerce Template
call V1/V2 runtime code
add engineering controls to the beginner UI
```

## 2. Problem Statement

The current V3 can preserve a recognizable person across multiple images, but
it may over-lock the reference:

```text
same face expression
same head angle
same pose
same gaze direction
same camera distance
same hair silhouette
```

This is not commercial photography quality. A real campaign keeps the model
recognizable while allowing natural variation:

```text
same person
same body type
same broad age and appearance direction
same styling family
same visual world

but different expression, action, head angle, gaze, pose, crop, lens distance,
hair movement, and small styling details
```

The target principle:

```text
Same person, not the same frozen frame.
```

## 3. Product Goal

V3 should produce human-led image sets where:

```text
identity is coherent
body shape and proportions remain plausible
the person still feels like the same model
style, lighting, palette, and campaign world remain coherent
each image has natural commercial variation
the set does not look like duplicated stills
```

Beginner-facing result:

```text
V3 kept the person recognizable, then changed expression, pose, angle, and
framing naturally across the set.
```

Advanced/internal result:

```text
identity anchors are locked
presentation variables are allowed to vary
batch-level diversity is reviewed
over-cloned batches can trigger a safe retry patch
```

## 4. Architecture Decision

### 4.1 Add a child module inside Visual Capability Cluster

Do not create a new top-level framework module.

Add the capability under:

```text
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/
  human_variation.py
```

Suggested child contracts may live in:

```text
visual_cluster/contracts.py
```

or a focused file if the existing contracts file becomes too large:

```text
visual_cluster/human_variation_contracts.py
```

The module is dispatched by the existing Visual Capability Cluster
orchestrator. CentralCreativeBrain and LLM Brain consume its output; they do
not own the logic.

### 4.2 Module responsibilities

`HumanNaturalVariationPolicy` owns:

```text
detect whether the job is human-led
read selected/uploaded human reference assets
read variation_mode from Doc54
build identity anchors
build allowed natural-variation budget
emit prompt guidance
emit negative guidance against over-cloning
emit batch-level diversity expectations
review generated batch diversity after output exists
create retry patch hints for over-cloned batches
```

### 4.3 Inputs

```text
user_input
template_id
scenario_id
variation_mode / effective_variation_mode
requested_image_count
requested_image_size
ProjectContextPackage
selected_visual_references
strong_reference_bindings
identity_lock_profiles
visual_grammar_snapshot
uploaded_assets
post-generation output resolutions
vision inspection reports when available
```

### 4.4 Outputs

```python
class HumanIdentityAnchorProfile(V3BaseModel):
    applies: bool = False
    confidence: str = "low"  # low | medium | high
    anchor_source: str | None = None  # selected_output | uploaded_reference | prompt_only
    stable_identity_traits: list[str] = []
    stable_body_traits: list[str] = []
    stable_style_traits: list[str] = []
    locked_traits: list[str] = []
    flexible_traits: list[str] = []
    forbidden_drift: list[str] = []
    metadata: dict[str, Any] = {}


class HumanNaturalVariationPlan(V3BaseModel):
    applies: bool = False
    variation_mode: str = "delivery_suite"
    identity_strength: str = "medium"  # loose | medium | strong
    diversity_strength: str = "medium"  # subtle | medium | broad
    per_image_variation_axes: list[str] = []
    prompt_additions: list[str] = []
    negative_additions: list[str] = []
    batch_review_rules: list[str] = []
    user_visible_summary: list[str] = []
    metadata: dict[str, Any] = {}


class HumanBatchDiversityReview(V3BaseModel):
    applies: bool = False
    status: str = "not_applicable"  # pass | warning | fail_retryable | manual_review
    issue_codes: list[str] = []
    observed_repetition: list[str] = []
    preserved_identity_notes: list[str] = []
    retry_patch: dict[str, Any] = {}
    user_visible_summary: list[str] = []
    metadata: dict[str, Any] = {}
```

## 5. Lock Vs Allow Rules

### 5.1 Stable identity anchors

Lock these when a selected/uploaded human reference exists:

```text
recognizable facial identity direction
face shape and facial feature relationships
approximate age band
skin tone direction
ethnicity/person identity direction
body type and body proportions
overall model presence
major styling category when relevant
commercial visual world
```

Prompt language should avoid claiming biometric certainty. Use wording such as:

```text
same recognizable person
consistent facial identity direction
consistent body type and proportions
```

Do not use wording that implies face verification or real-person identification
outside the generation context.

### 5.2 Flexible natural variables

Allow these by default in a multi-image human set:

```text
expression
gaze direction
head angle
face angle
pose
hand placement
body turn
camera distance
crop
lens height
small hair movement
hair parting / looseness / tied-or-loose styling when plausible
subtle makeup variation
small wardrobe styling changes inside the same category
background position
light direction inside the same lighting language
```

Important hair rule:

```text
Hair must not be locked as a pixel-level duplicate.

Default behavior should preserve hair family, color direction, length range,
and overall styling category, while allowing natural commercial variation such
as movement, parting, volume, tied/loose treatment, and shoot-day styling.

Major changes such as long hair to short hair, black hair to blonde hair, or a
new fantasy hairstyle require either user instruction or creative exploration
mode with low identity risk.
```

### 5.3 Forbidden drift

Forbid these unless explicitly requested:

```text
face swap
age drift
ethnicity/person identity drift
large body type change
major hair color or length change
unrelated wardrobe category replacement
unrelated product or prop insertion
random visible text
watermark/signature
duplicate stills across the batch
identical expression + identical head angle + identical pose repeated in most images
```

## 6. Variation Budget By General Mode

### 6.1 `selection_candidates`

Goal:

```text
Give close alternatives for picking the best one.
```

Identity:

```text
strong
```

Diversity:

```text
subtle to medium
```

Must vary at least two axes across a batch of 2+ images:

```text
expression
head angle
gaze direction
pose
hand placement
crop
camera distance
```

Should not vary:

```text
core identity
body type
major hair color/length
major wardrobe category
overall style world
```

Prompt intent:

```text
Create close alternatives of the same recognizable person, with natural
variation in expression, pose, head angle, gaze, and framing. Do not repeat the
same frozen face angle or pose across the whole batch.
```

### 6.2 `delivery_suite`

Goal:

```text
Create a useful set under the same visual direction.
```

Identity:

```text
strong when reference exists, medium when prompt-only
```

Diversity:

```text
medium
```

Use different commercial roles:

```text
hero portrait
environmental portrait
action / lifestyle moment
close or crop variation
layout-safe frame
```

### 6.3 `creative_exploration`

Goal:

```text
Explore different creative directions without losing the subject.
```

Identity:

```text
medium to strong
```

Diversity:

```text
broad
```

Allowed:

```text
bigger scene variation
different mood
different styling idea
different camera language
```

Still forbid:

```text
person replacement
age/ethnicity drift
unwanted product/prop insertion
```

### 6.4 `format_layout_adaptation`

Goal:

```text
Adapt the same direction into useful formats and layouts.
```

Identity:

```text
strong
```

Diversity:

```text
subtle to medium
```

Primary variation axes:

```text
crop
negative space
subject scale
camera distance
composition balance
layout-safe framing
```

Expression and pose may vary naturally, but the main reason for variation is
format usefulness.

## 7. Prompt And Brain Behavior

### 7.1 Brain checkpoint changes

The LLM Brain and deterministic fallback must include a human-variation
checkpoint when the job is human-led and `requested_image_count >= 2`.

Checkpoint:

```text
human_identity_balance
```

It must answer:

```text
What identity traits should remain stable?
What presentation traits should vary?
Which variation mode is active?
What should not be over-locked?
```

### 7.2 Prompt additions

For human-led multi-image sets, prompt guidance should include:

```text
Keep the same recognizable person and body type across the set.
Allow natural variation in expression, gaze, pose, head angle, camera angle,
crop, and small hair styling details.
Each image should feel like a different frame from the same professional shoot,
not a duplicate of the same still.
```

For selected/uploaded references:

```text
Use the reference as an identity and style anchor, not as an instruction to
copy the exact same expression, pose, head angle, or crop unless the user
explicitly asks for an exact recreation.
```

### 7.3 Negative additions

```text
avoid repeating the exact same expression across all images
avoid repeating the exact same head angle across all images
avoid repeating the exact same pose across all images
avoid cloned stills
avoid mannequin-like repeated face
avoid identity drift
avoid major body-shape drift
avoid major hair color or length drift unless requested
```

### 7.4 User explicit override

If the user explicitly asks for:

```text
same pose
same expression
same angle
exact copy
完全一样
一模一样
只改背景
只改尺寸
```

then natural variation should be reduced. The system should still avoid
unintended identity drift and should not force variation against the user's
clear instruction.

## 8. Post-Generation Review And Retry

### 8.1 Batch-level review

Doc55 candidate-level inspection is not enough for this problem. Doc56 adds a
batch-level human diversity review.

Run when:

```text
template is General Template or another human-capable template
requested_image_count >= 2
job is human-led
at least two generated outputs are available
user did not ask for exact duplicate pose/expression/angle
```

Review questions:

```text
Do outputs preserve the same person direction?
Do outputs vary expression or gaze?
Do outputs vary pose or body angle?
Do outputs vary head/face angle?
Do outputs vary crop/camera distance when useful?
Does the set look like duplicate stills?
```

### 8.2 New issue codes

Add these Doc56 issue codes to the Visual Capability Cluster review taxonomy:

```text
overlocked_expression_pose
duplicate_head_angle_batch
duplicate_pose_batch
flat_human_variation_batch
identity_anchor_too_rigid
human_batch_looks_cloned
```

These are different from identity drift:

```text
identity_drift:
  the person changed too much

overlocked_expression_pose:
  the person stayed consistent but the batch lacks natural variation
```

### 8.3 Retry classification

Retryable if all are true:

```text
there are 2+ outputs
the issue is over-locking / duplicate stills
the identity is not severely broken
retry budget is available under Doc53
the retry patch is non-empty
the user did not request exact duplicates
```

Non-retryable if:

```text
single image request
explicit exact-copy request
provider/account/network error
low confidence review
severe face/body artifact requiring manual review
identity is unrecoverably replaced
retry would likely waste credits
```

### 8.4 Retry patch

Suggested retry patch:

```json
{
  "prompt_additions": [
    "Keep the same recognizable person and body type, but create natural commercial variation across the batch.",
    "Vary expression, gaze, pose, head angle, camera angle, and crop between outputs.",
    "Each image should feel like a different frame from the same professional shoot, not a duplicate still."
  ],
  "negative_additions": [
    "do not repeat the exact same expression in every image",
    "do not repeat the exact same head angle in every image",
    "do not repeat the exact same pose in every image",
    "avoid cloned stills"
  ],
  "identity_reinforcement": [
    "same recognizable person",
    "same body type and proportions",
    "preserve hair color direction and broad hair length range while allowing natural styling variation"
  ],
  "user_visible_reason": "这组图人物一致，但表情和角度过于重复，V3 补做一组更自然的变化。"
}
```

Retry must remain append-only under Doc53. It must not overwrite original
images.

## 9. Project Context And Long-Term Consistency

When the user selects a preferred human image:

```text
selected image becomes a strong identity/style anchor
HumanIdentityAnchorProfile is stored in ProjectContextPackage
HumanNaturalVariationPlan is rebuilt for future jobs
selected output does not force exact expression/pose duplication
```

Project context should store:

```text
identity_anchor_strength
stable_identity_traits
stable_body_traits
flexible_presentation_traits
preferred_variation_axes
negative_drift_rules
```

Do not store:

```text
exact face embedding or biometric identity data in this phase
provider-specific identity vectors
V1/V2 runtime objects
```

## 10. Beginner UX

Do not add a complex new control to the default UI.

Keep the existing Doc54 mode selector:

```text
智能选择
相似备选模式
套图扩展模式
创意探索模式
尺寸/版式适配模式
```

The user should not need to understand identity locks.

Folded workflow wording may show:

```text
已保持人物相貌和身材一致
已让表情、动作、角度自然变化
已避免整组图片像重复复制
```

If retry runs:

```text
V3 发现这组图太像同一张定格，已补做一组更自然的变化。
```

Do not show:

```text
embedding
face vector
identity model
provider internals
ControlNet / IP-Adapter wording
```

## 11. Implementation Plan

### Phase 1: Contracts and policy module

Add:

```text
visual_cluster/human_variation.py
HumanIdentityAnchorProfile
HumanNaturalVariationPlan
HumanBatchDiversityReview
```

Register it under the Visual Capability Cluster orchestrator.

### Phase 2: Brain and prompt integration

Update:

```text
llm_brain/fallback.py
llm_brain/adapter.py
creative_core prompt assembly path
```

Requirements:

```text
variation_mode is read
human-led batch is detected
prompt additions and negative additions are appended
strong selected reference is treated as identity/style anchor, not pose clone
```

### Phase 3: Project context persistence

Update ProjectContextPackage metadata with:

```text
human_identity_anchor_profile
human_natural_variation_plan
```

Only store structured descriptive constraints, not biometric vectors.

### Phase 4: Batch-level post-generation review

Extend Doc55 review merge with:

```text
HumanBatchDiversityReview
batch-level issue codes
retry patch for over-locked human batches
```

The first implementation may use conservative heuristics and metadata until a
strong vision model is available, but it must not pretend low-confidence review
is certain.

### Phase 5: Safe retry bridge

Extend Doc53 retryable taxonomy to include Doc56 issue codes:

```text
overlocked_expression_pose
duplicate_head_angle_batch
duplicate_pose_batch
flat_human_variation_batch
identity_anchor_too_rigid
human_batch_looks_cloned
```

Retry remains:

```text
append-only
budget-limited
no provider-error retry
no exact-copy override retry
```

### Phase 6: Frontend workflow display

No new default controls.

Add folded workflow/result text only:

```text
人物保持一致
表情动作自然变化
已检查是否过度重复
```

## 12. Tests

### 12.1 Unit tests

```text
human-led prompt with count 3 builds HumanNaturalVariationPlan
selection_candidates locks identity but varies expression/pose/head angle
delivery_suite creates role-level variation
creative_exploration allows broader styling without identity replacement
format_layout_adaptation prioritizes crop/layout variation
exact-copy user instruction disables natural variation retry
```

### 12.2 Prompt tests

For a prompt like:

```text
同一个东方夏日美女，生成三张清爽高级写真
```

The final provider prompt must include:

```text
same recognizable person
consistent body type
natural variation in expression, pose, head angle, gaze, framing
not duplicate stills
```

It must not include:

```text
same exact expression
same exact head angle
same exact pose
copy the reference exactly
```

unless the user explicitly asks for exact copy.

### 12.3 Review/retry tests

```text
batch duplicate issue creates HumanBatchDiversityReview fail_retryable
retry patch contains variation guidance
retry output is appended, not overwritten
single-image job does not trigger batch diversity retry
provider error does not become human variation retry
exact-copy instruction does not trigger variation retry
```

### 12.4 Frontend tests

```text
no new engineering fields are displayed
workflow may show simple folded summary
Doc54 mode selector remains the only user-facing mode control
```

## 13. Acceptance Criteria

A V3 General Template test with:

```text
same East Asian summer model
clean bright premium portrait set
3 outputs
selection_candidates or delivery_suite mode
```

passes when:

```text
all images look like the same person or same designed model direction
body type and broad styling remain coherent
at least two outputs differ in expression or gaze
at least two outputs differ in pose or body/head angle
at least two outputs differ in crop, camera distance, or framing
hair keeps broad identity direction but has natural styling/movement variation
no image introduces unrelated products, random text, watermark, or identity swap
```

fails or warns when:

```text
all outputs repeat the same expression, same head angle, and same pose
identity drifts into different people
body type changes drastically
hair color/length changes drastically without instruction
outputs look like duplicated stills
```

## 14. Developer Notes

This document is intentionally a balance correction.

Do not weaken consistency into random variation.

Do not strengthen consistency into frozen duplication.

The correct V3 behavior is:

```text
identity anchors stay stable
presentation variables move naturally
the batch feels like one professional shoot
```
