# 87 V3 Portrait Reference Identity And Style Separation Spec

## 1. Purpose

Doc87 is the refined authority for V3 portrait image-to-image generation after
the real VPS portrait validation that followed Doc86.

Doc86 correctly established:

```text
same person under changed styling, not a similar-looking new model
```

However, real outputs exposed a finer failure:

```text
The uploaded portrait reference was sometimes treated as a whole-image visual
template. V3 inherited too much source lighting, warmth, scene feeling, and
beauty-camera bias, while still sometimes allowing the face to drift into a
generic styled beauty archetype.
```

Doc87 replaces the old coarse standard with this sharper product rule:

```text
For portrait reference generation, the reference image is identity truth by
default, not style truth.

Preserve bone structure and facial-feature relationships.
Allow makeup and styling changes.
Allow hairstyle changes only when the user asks for them or the target style
requires a clear hair arrangement change.
Let the user's prompt control lighting, color grade, scene, mood, camera, and
art direction unless the user explicitly marks the reference as style guidance.
```

Short product rule:

```text
Identity comes from the reference. Direction comes from the prompt.
```

This is a foundation-quality document. It is not a scene-specific rule, not a
photography-template package, and not an e-commerce template. It applies to all
portrait/person image generation paths that use an identity reference.

Doc88 update:

```text
Doc87 remains the identity/style separation baseline, but Doc88 is the latest
authority for balancing uploaded identity truth, user-approved visual direction,
and current prompt mood. Do not harden identity guidance so much that the
prompt's color, lighting, scene, mood, or aesthetic intent is damaged.
```

## 2. Compatibility And Authority

Doc87 extends and supersedes parts of:

```text
Doc76  Foundation vs specialized-template governance
Doc77  Real visual review and aesthetic stability
Doc78  Long-term identity and beautiful realism
Doc83  Retry delivery layer and reference identity closure
Doc84  Structured appearance identity and prompt purity
Doc85  Image-to-image identity transfer and reference truth closure
Doc86  Portrait bone-structure identity lock
```

Doc86 remains the implementation baseline for:

```text
PortraitBoneStructureLock
StylingDeltaPolicy
PortraitIdentitySimilarityReview
BoneStructureRetryPatch
portrait identity issue codes
```

Doc87 is the latest authority for:

```text
which parts of a portrait reference should be inherited
which parts should be controlled by the prompt
how to score identity vs style separately
how retry should fix artifacts without replacing the face
when hairstyle / hair color may or may not change
```

Doc88 is the latest authority for:

```text
how to preserve prompt mood while repairing identity drift
how selected approved outputs can act as positive tone / style anchors
how to prevent scenario-specific examples from becoming universal negative
prompt rules
```

If Doc86 or earlier documents imply that lighting, color grade, mood, scene,
hair, or full-image style should be inherited from the portrait reference by
default, Doc87 wins.

If Doc86 or earlier documents imply that a visually beautiful output can pass
when it is only the same beauty type but not the same person, Doc87 wins.

If Doc87 language is interpreted as "always add stronger identity negatives
until likeness improves", Doc88 wins. Identity repair must preserve the user's
requested atmosphere and any user-approved positive visual direction.

## 3. Core Inheritance Model

Every portrait reference must be decomposed into separate reference channels.

### 3.1 Identity Truth Channel

Default strength:

```text
hard
```

Always inherit:

```text
face width/length ratio
forehead-to-midface-to-lower-face proportion
cheek volume and cheekbone direction
jaw width, jawline slope, and chin scale
eye spacing and base eye shape
eyelid direction and brow-eye relationship
eyebrow base shape / thickness family / visual temperament
nose bridge / nose tip / nose wing relationship
nose-mouth relationship
philtrum / mouth width / lip contour / lip fullness family
age impression
natural face temperament
body identity direction when visible
```

Forbidden drift:

```text
same type but different person
generic styled beauty replacement
beauty-app face slimming
V-shaped jaw replacement
eye enlargement that changes identity
new nose-mouth relationship
new lip contour family
new age band
ethnicity or face-family drift
```

### 3.2 Makeup And Surface Styling Channel

Default strength:

```text
prompt-controlled
```

May change:

```text
makeup color and intensity
eyeliner / eyeshadow / lip color
skin finish, if it does not destroy natural texture or face geometry
costume / wardrobe / accessory style
surface polish and requested retouching level
```

Rule:

```text
Makeup may change the look, but not the face.
```

Fail examples:

```text
makeup makes the eyes a different base shape
styling narrows or reshapes the face
beauty polish changes the nose-mouth relationship
retouching makes the person look like another model
```

These are universal identity failures. They are not tied to any one scene,
wardrobe, era, culture, or photography style.

### 3.3 Hair Channel

Default strength:

```text
medium preserve
```

Preserve by default:

```text
broad hair length direction
major hair color family
recognizable distinctive hair marks when not contradicted by the prompt
hair volume family
```

May change when:

```text
the user explicitly asks for a hairstyle change
the selected template requires a role-specific hair arrangement
the target style naturally requires styling, such as tied hair, pinned hair,
formal updo, wind movement, or accessory placement
```

Must not:

```text
use hair alone as identity substitute
force source-image hair lighting/color into an unrelated prompt style
erase distinctive hair marks when the prompt does not ask to remove them
change face geometry because hair is restyled
```

### 3.4 Appearance / Wardrobe Structure Channel

Default strength:

```text
prompt-controlled unless the uploaded reference is explicitly an outfit,
product, costume, or structured appearance reference
```

For ordinary portrait identity references:

```text
do not inherit source clothing by default
do not inherit source environment by default
do not inherit source shoot concept by default
```

For explicit structured appearance references:

```text
preserve silhouette
preserve layer order
preserve collar / neckline / sleeve / cuff logic
preserve material behavior
preserve pattern / embroidery / trim placement family
```

Doc84 remains the structured appearance authority. Doc87 clarifies that
structured appearance is not automatically active for every face reference.

### 3.5 Lighting / Color / Scene / Camera Channel

Default strength:

```text
prompt-owned
```

The uploaded portrait reference must not automatically impose:

```text
source lighting direction
source color temperature
source warmth/coolness
source exposure level
source background or location
source camera focal style
source seasonal atmosphere
source lifestyle mood
```

These should follow the user's current prompt, selected mode, or specialized
template direction.

Example:

```text
If the uploaded reference has one color/light/scene direction and the current
prompt asks for a clearly different direction, V3 must keep the face identity
while following the current prompt's requested mood, lighting, and scene.
```

Fail condition:

```text
The output keeps the source image's original lighting, exposure, and atmosphere
when the prompt asked for a different art direction.
```

## 4. Reference Influence Budget

V3 must create an explicit influence budget whenever a portrait reference is
used.

Recommended contract:

```python
class PortraitReferenceInfluencePolicy(V3BaseModel):
    policy_id: str
    applies: bool = False
    identity_truth_strength: str = "hard"
    makeup_style_strength: str = "prompt_controlled"
    hair_strength: str = "medium_preserve"
    wardrobe_structure_strength: str = "prompt_controlled"
    lighting_color_scene_strength: str = "prompt_owned"
    camera_composition_strength: str = "prompt_owned"
    inherited_reference_channels: list[str] = []
    blocked_reference_channels: list[str] = []
    prompt_owned_channels: list[str] = []
    metadata: dict[str, Any] = {}
```

Required default values for a normal uploaded face reference:

```text
inherited_reference_channels:
  identity_truth
  broad hair direction
  distinctive hair marks unless contradicted

prompt_owned_channels:
  makeup
  wardrobe
  lighting
  color grade
  scene
  mood
  camera
  composition

blocked_reference_channels:
  source scene
  source lighting
  source color temperature
  source lifestyle concept
  source clothing
  source beauty archetype
```

## 5. Prompt Layering Requirements

Provider prompts for portrait image-to-image must follow Doc88's three-source
balance order:

```text
1. Current prompt's user goal and mood / art direction
2. Same-person identity truth from uploaded reference
3. User-approved positive visual anchor, if present
4. Reference influence budget
5. Explicit "do not inherit source lighting/style unless requested" rule
6. Makeup / hair / wardrobe change rules
7. Beauty-realism and anti-AI-face rules
8. Compact negative identity and artifact rules
```

Required provider semantics:

```text
Use the reference image only as the person's identity truth unless explicitly
asked otherwise.
Preserve the same underlying face and facial-feature relationships.
Do not copy the reference image's original lighting, color temperature, scene,
wardrobe, or shoot mood unless the prompt asks for that.
Follow the current prompt for lighting, color grade, scene, camera, and mood.
Makeup and styling may change; face geometry must not.
Hair may be restyled when requested, but face identity must remain the same.
```

Prompt phrases to avoid or scope:

```text
generic stylized template face
over-idealized beauty-template face
V-shaped face
large watery eyes
high nose bridge
idol-card beauty
plastic smooth skin
Korean glass skin
```

They may be transformed into:

```text
target styling, costume, makeup, and atmosphere while preserving reference face
delicate mood without changing facial geometry
clear skin texture with natural pores and real light response
refined portrait polish without face slimming or feature enlargement
```

Scene-specific words, industry-specific words, seasonal words, genre words, or
photography-setup words may appear in examples only when the user prompt
contains them. They must not be hardcoded into universal foundation negative
rules.

## 6. Review Scoring

Doc87 separates identity pass from style pass. A result must not pass merely
because it is beautiful.

### 6.1 Required Score Families

```text
identity_bone_structure_score
identity_feature_relationship_score
same_person_readability_score
prompt_style_obedience_score
lighting_color_scene_obedience_score
beauty_realism_score
anti_ai_face_score
reference_overinheritance_penalty
```

### 6.2 Identity Pass

Identity pass requires:

```text
identity_bone_structure_score >= 85
identity_feature_relationship_score >= 85
same_person_readability_score >= 85
```

Automatic identity failure:

```text
eyes become a different base shape
eye spacing changes visibly
face becomes significantly narrower / longer / sharper
jaw or chin is redesigned
nose-mouth relationship changes
lip contour family changes
age impression shifts
the output reads as the same archetype but not the same person
```

### 6.3 Style Pass

Style pass requires:

```text
prompt_style_obedience_score >= 80
lighting_color_scene_obedience_score >= 80
beauty_realism_score >= 80
anti_ai_face_score >= 80
```

Automatic style failure:

```text
the reference image's original lighting overrides the prompt
the reference image's original color temperature overrides the prompt
the reference image's source scene or lifestyle mood leaks into the output
the target style becomes a generic template instead of the user's prompt
```

### 6.4 Overall Pass

Recommended pass rule:

```text
identity pass is mandatory
style pass is mandatory
beauty score cannot compensate for identity failure
identity score cannot compensate for prompt-style failure
```

Scoring interpretation:

```text
90-100:
  Lovart-level for foundation/general portrait identity transfer

85-89:
  acceptable commercial pass

75-84:
  usable only with manual/user acceptance; not strong identity closure

65-74:
  similar person family; retry if budget allows

< 65:
  identity failure
```

## 7. Issue Codes

Doc87 keeps Doc86 issue codes and adds reference-overinheritance codes.

Identity drift:

```text
same_type_not_same_person
identity_reference_underweighted
bone_structure_drift
face_shape_drift
cheek_jaw_chin_drift
eye_shape_or_spacing_identity_drift
eyebrow_eye_relationship_drift
nose_mouth_relationship_identity_drift
lip_contour_identity_drift
age_impression_drift
archetype_overrode_reference_identity
```

Style / reference boundary drift:

```text
source_lighting_overinherited
source_color_temperature_overinherited
source_scene_overinherited
source_wardrobe_overinherited
source_camera_mood_overinherited
reference_used_as_style_when_identity_only
prompt_style_underweighted
makeup_changed_face_geometry
hair_change_replaced_identity
retry_repaired_artifact_but_changed_identity
```

## 8. Retry Rules

### 8.1 Identity Drift Retry

When the result is beautiful but not the same person:

```text
retry with stronger identity truth
increase identity crop priority
reduce archetype/style pressure
explicitly state that style cannot redesign the face
preserve source face geometry but not source lighting/scene
```

Required retry patch:

```text
The previous result looked like a similar styled model, not the reference
person. Regenerate using the reference only as identity truth: preserve face
width/length ratio, cheek/jaw/chin direction, eye spacing/base shape,
eyebrow-eye relationship, nose-mouth relationship, lip contour, and age
impression. Do not copy the reference's original lighting, background, clothing,
or color temperature unless requested. Follow the current prompt for style,
light, scene, mood, and camera.
```

### 8.2 Artifact Retry

When retry is triggered for text/watermark/artifact:

```text
artifact repair must not weaken identity lock
carry the same identity truth contract into the retry
do not let the artifact-repair prompt become the dominant instruction
use the best identity-preserving previous output as an auxiliary reference only
when it does not conflict with uploaded truth
```

Hard rule:

```text
Retrying to remove a watermark must not produce a cleaner but less recognizable
person.
```

### 8.3 Reference Overinheritance Retry

When the face is correct but lighting/style is polluted by the source image:

```text
keep identity truth from the reference
explicitly block source lighting/color/scene inheritance
raise prompt art-direction priority
do not reduce identity strength
```

Required retry patch:

```text
Keep the same person from the reference, but do not copy the reference image's
original lighting, color temperature, atmosphere, clothing, or source scene.
Follow the current prompt's lighting, color grade, background, and camera style.
```

## 9. Runtime Implementation Plan

### Phase 1 - Contracts

Extend visual cluster contracts:

```text
PortraitReferenceInfluencePolicy
ReferenceChannelBudget
PortraitIdentityStyleSeparationReview
ReferenceOverinheritanceRetryPatch
```

These may be standalone models or added as fields to the existing Doc86 models.
Do not create a separate non-V3 pipeline.

### Phase 2 - Reference Classification

Update reference preparation:

```text
ordinary face upload -> identity truth, not style truth
explicit style reference -> style truth allowed
explicit outfit/costume/product reference -> structured appearance truth allowed
selected generated output with uploaded truth present -> style/composition support only
selected generated output without uploaded truth -> identity source allowed
```

Add metadata:

```text
reference_inheritance_policy
identity_truth_source_ids
style_truth_source_ids
blocked_reference_channels
prompt_owned_channels
```

### Phase 3 - Prompt Compiler / Provider Prompt

Update provider prompt generation:

```text
identity contract before style contract
reference influence budget before user prompt
explicit source-lighting/source-scene block
prompt art direction must be preserved
artifact retry must keep identity contract
```

### Phase 4 - Visual Review

Upgrade review to judge:

```text
identity was inherited correctly
prompt style was followed correctly
reference image did not over-control lighting/scene/color
retry did not clean artifacts by replacing the face
```

Local fake review may only simulate these issue codes in tests. Real scoring
requires live vision review or explicit test metadata.

### Phase 5 - Auto Retry

Update retry creation:

```text
identity drift -> strengthen identity crop and reduce archetype pressure
style overinheritance -> block source lighting/scene and raise prompt style
artifact retry -> preserve identity lock exactly while removing artifact
```

Retry budget remains governed by Doc53/Doc81.

### Phase 6 - Frontend UX

No new beginner-facing controls are required.

Optional advanced folded summary:

```text
V3 kept: same person / same face structure.
V3 changed: styling, lighting, scene, mood, and camera according to your prompt.
```

Do not expose engineering fields such as:

```text
reference_inheritance_policy
identity_truth_source_ids
issue_codes
retry_patch
provider_input_plan
```

## 10. Tests

Add or update tests:

```text
test_v3_doc87_portrait_reference_identity_style_separation.py
test_v3_doc86_portrait_bone_identity_lock.py
test_v3_doc85_image_to_image_reference_truth.py
test_v3_doc78_long_term_identity_beautiful_realism.py
test_v3_doc77_real_review_aesthetic_stability.py
test_v3_visual_auto_retry.py
```

Required assertions:

```text
ordinary uploaded portrait reference creates identity-only influence policy
provider prompt says not to inherit source lighting/scene/color by default
provider prompt keeps identity contract before prompt art direction
explicit style reference can opt into style inheritance
selected generated output cannot override uploaded identity truth
identity drift issue triggers retry that preserves face and blocks archetype
artifact retry keeps identity lock instead of replacing face
source lighting overinheritance creates style-boundary retry patch
same-type-not-same-person fails even if beauty score is high
```

## 11. Real Validation Protocol

Use three real validations when provider availability allows.

### Test A - Strong Style Change With Same Identity

Input:

```text
Upload a modern portrait reference.
Ask for a very different portrait style, lighting, scene, and mood.
```

Pass:

```text
same person remains readable
target prompt lighting and scene are followed
source image lighting/scene does not leak
face remains attractive and natural
```

### Test B - Artifact Retry Without Identity Loss

Input:

```text
Use an output with a faint watermark/text/mark issue.
Trigger retry.
```

Pass:

```text
artifact is removed
identity score does not drop
retry output does not become a new beauty archetype
```

### Test C - Prompt Style vs Reference Style Conflict

Input:

```text
Reference has warm daylight or casual lifestyle mood.
Prompt asks for a clearly different color, light, scene, camera, or emotional
atmosphere.
```

Pass:

```text
output keeps reference identity
output follows prompt lighting/color/scene
source lighting does not dominate
identity repair does not flatten or damage the prompt's intended atmosphere
```

## 12. Acceptance Criteria

Doc87 is implemented only when all are true:

1. V3 distinguishes identity truth from style/lighting/scene truth.
2. Ordinary uploaded portrait references default to identity-only inheritance.
3. Provider prompt blocks source lighting/color/scene inheritance unless asked.
4. Identity scoring and prompt-style scoring are separated.
5. Same-type-not-same-person fails regardless of beauty.
6. Source-lighting overinheritance can be detected or simulated in review.
7. Artifact retry cannot replace the face.
8. Retry patches preserve identity while correcting only the failing channel.
9. General Template remains scenario-neutral and beginner-friendly.
10. Doc88 balance rules are respected: identity repair must not break prompt
    tone, mood, atmosphere, or selected positive visual direction.
11. Doc77/78/85/86/88 focused regressions continue to pass.

Minimum real quality target:

```text
identity_bone_structure_score >= 85
identity_feature_relationship_score >= 85
same_person_readability_score >= 85
prompt_style_obedience_score >= 85
lighting_color_scene_obedience_score >= 85
beauty_realism_score >= 85
```

## 13. Implementation Handoff Prompt

Use this prompt when coding begins:

```text
Implement Doc87.

Do not rewrite V3 and do not create a new portrait pipeline. Extend the existing
V3 visual capability cluster, provider prompt generation, reference preparation,
visual review, retry patching, and output metadata.

Upgrade portrait reference handling so an ordinary uploaded face reference is
identity truth by default, not style truth. Preserve bone structure and
facial-feature relationships. Makeup, wardrobe, expression, pose, scene, camera,
lighting, and color grade follow the current prompt unless the user explicitly
marks the reference as style guidance. Hair may change only when the prompt or
template asks for it; otherwise preserve broad hair direction and distinctive
marks without letting hair become the only identity cue.

Provider prompts must say that the reference supplies the person's identity but
not the source lighting, color temperature, scene, clothing, or original shoot
mood by default. Review must separately score identity inheritance and prompt
style obedience. A beautiful output that is only the same type of person must
fail identity review. An output that keeps the face but inherits the wrong
source lighting/style must fail style-boundary review. Under Doc88, retry
patches must also preserve the current prompt's intended tone, atmosphere, and
any user-approved positive visual direction; do not solve identity drift by
making the output flatter, colder, warmer, less atmospheric, or less faithful to
the user's prompt. Retry patches must fix only the failing channel and must not
replace the face while removing artifacts.

Add focused Doc87 tests and run Doc77/78/85/86/88 regressions.
```
