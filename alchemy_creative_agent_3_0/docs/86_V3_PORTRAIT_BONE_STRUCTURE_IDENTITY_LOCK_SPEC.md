# 86 V3 Portrait Bone-Structure Identity Lock Spec

## 1. Purpose

Doc86 upgrades V3 portrait image-to-image identity quality after Doc85.

Doc85 proved that V3 can route uploaded portrait references into true
reference-image generation and can split reference truth into provider-facing
layers.

The remaining gap is more precise:

```text
V3 may preserve the same beauty family, mood, hair direction, and commercial
style, but still change the person's underlying face identity.
```

Doc86 makes the portrait identity standard explicit:

```text
Makeup, wardrobe, styling, lighting, pose, expression, and scene may change.
Bone structure and facial-feature relationships must not change.
```

Doc87 is the current identity/style separation baseline for portrait reference
inheritance boundaries. Doc86 remains the implementation baseline for
bone-structure locks, identity issue codes, and identity-drift retry patches,
but Doc87 wins whenever there is a conflict about what an uploaded portrait
reference should influence.

Doc88 is the current superseding standard for portrait reference balance. Doc86
must not be implemented as "make identity rules harder every retry." The
bone-structure lock must coexist with the current prompt's color, light, scene,
mood, and any user-approved positive visual direction.

Doc87 clarification:

```text
An ordinary uploaded portrait reference is identity truth by default, not style
truth.

Inherit bone structure and facial-feature relationships.
Do not inherit source lighting, color temperature, scene, camera, wardrobe, or
shoot mood by default.
Let the current prompt control lighting, color grade, scene, mood, camera, and
art direction unless the user explicitly marks the reference as style guidance.
Hair is medium-preserve: keep broad direction and distinctive marks unless the
prompt or template asks for a change.
```

Short product rule:

```text
Same person under different styling, not a similar-looking new model.
```

This document is a foundation-quality document. It is not a photography
template, not an e-commerce template, and not a new Central Brain framework.

## 2. Compatibility

Doc86 extends:

```text
Doc50  V3-native Visual Capability Cluster
Doc56  Human natural variation and identity balance
Doc58  Identity anchor and strong-reference continuation
Doc65  Human photorealism and anti-AI-face layer
Doc76  Foundation vs specialized-template governance
Doc77  Real visual review and aesthetic stability
Doc78  Long-term identity and beautiful realism
Doc83  Retry delivery layer and reference identity closure
Doc84  Structured appearance identity and prompt purity
Doc85  Image-to-image identity transfer and reference truth closure
```

Doc86 does not replace:

```text
Project Mode
ScenarioRuntime
Scenario Packs
General Template four-mode selector
E-Commerce Template ownership
Photography Template future ownership
LLM Brain Adapter
provider-reference compression
bounded retry guardrails
```

Doc86 remains the implementation baseline for:

```text
portrait identity scoring when an uploaded or selected face reference exists
bone-structure preservation rules
makeup/styling transformation budget
identity-drift retry patches for human image-to-image generation
```

If earlier documents imply that "similar vibe", "same beauty family", or
"same archetype" is enough for a referenced portrait, Doc86 wins.

If Doc86 or earlier documents imply that a portrait reference should control
source lighting, source color temperature, source scene, source camera, source
wardrobe, or whole-image style by default, Doc87 wins.

If Doc86 or earlier documents imply that retry may remove artifacts by replacing
the face with a cleaner but less recognizable face, Doc87 wins.

If Doc86 language is interpreted as a reason to add long, scenario-specific
negative prompts that damage the user's requested atmosphere or selected visual
direction, Doc88 wins.

## 3. Product Standard

### 3.1 Allowed Difference

The user may ask for major styling changes, such as:

```text
one scene or wardrobe direction -> another scene or wardrobe direction
natural makeup -> stronger requested makeup
loose hair -> styled hair
daylight scene -> cinematic night scene
casual outfit -> formal wardrobe
smiling frame -> quiet melancholic frame
```

These changes are allowed as styling or shoot direction.

### 3.2 Forbidden Difference

These must remain recognizably stable:

```text
face width / length ratio
forehead-to-midface-to-lower-face proportion
cheekbone volume and cheek contour direction
jaw width, jawline slope, and chin scale
eye spacing, eye shape base, eyelid direction
eyebrow base shape, thickness family, brow-eye relationship
nose bridge / nose tip / nose wing relationship
philtrum, mouth width, lip contour, and lip fullness family
midface temperament
age impression
overall facial bone-structure family
```

Forbidden output:

```text
same mood but different bone structure
same hairstyle but different face
same costume but different person
generic AI beauty replacement
V-shaped face slimming
eye enlargement that changes identity
nose/mouth remodeling caused by beauty archetype words
target-style makeup that rewrites facial geometry
```

## 4. Scoring Standard

Portrait image-to-image review must score the result as:

```text
same person under changed styling
```

not:

```text
same type of attractive person
same aesthetic direction
same hair and skin tone
same commercial mood
```

### 4.1 Required Score Families

Add or expose these review families:

```text
bone_structure_identity_score
facial_feature_relationship_score
styling_delta_correctness_score
beauty_realism_score
same_person_readability_score
```

### 4.2 Composite Rule

Recommended identity pass formula:

```text
bone_structure_identity_score:      40%
facial_feature_relationship_score:  30%
same_person_readability_score:      20%
styling_delta_correctness_score:    10%
```

Beauty / realism remains a separate quality score. A beautiful image with low
bone-structure identity is still an identity failure.

### 4.3 Thresholds

```text
>= 85:
  commercial pass, Lovart-like same-person continuity

75-84:
  usable only with user/manual acceptance; do not claim strong identity closure

65-74:
  similar person family, not strong identity; retry if budget allows

< 65:
  identity failure; retry or mark as failed review
```

Hard fail even if the composite is moderate:

```text
face shape clearly changed
eye spacing / eye base shape clearly changed
nose-mouth relationship clearly changed
jaw/chin clearly remodeled
age impression changed into another person
```

## 5. Architecture Boundary

Doc86 must stay inside the V3-native modular foundation.

Allowed implementation locations:

```text
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/
alchemy_creative_agent_3_0/app/llm_brain/
alchemy_creative_agent_3_0/app/prompt_compiler/
alchemy_creative_agent_3_0/app/generation_router/
alchemy_creative_agent_3_0/app/product_api/
alchemy_creative_agent_3_0/app/project_mode/
```

Preferred files to extend:

```text
shared_capabilities/visual_cluster/contracts.py
shared_capabilities/visual_cluster/identity_anchor.py
shared_capabilities/visual_cluster/strong_reference_loop.py
shared_capabilities/visual_cluster/human_variation.py
shared_capabilities/visual_cluster/human_photorealism.py
shared_capabilities/visual_cluster/quality_review.py
shared_capabilities/visual_cluster/vision_inspector.py
llm_brain/prompts.py
llm_brain/fallback.py
prompt_compiler/provider_notes.py
prompt_compiler/compiler.py
generation_router/providers.py
product_api/service.py
project_mode/service.py
```

Forbidden implementation:

```text
do not put this as special-case logic inside CentralCreativeBrain
do not create a separate non-V3 portrait pipeline
do not call V1/V2 runtime code
do not hard-code one ethnicity, one costume, or one beauty template
do not make General Template own photography-package deliverables
do not use raw engineering terms in beginner UI
```

## 6. New Contracts

The implementation may use Pydantic/dataclass models matching existing local
style. Names may be adjusted to fit the codebase, but the semantics must remain.

### 6.1 PortraitBoneStructureLock

```python
class PortraitBoneStructureLock(V3BaseModel):
    lock_id: str
    source_reference_id: str | None = None
    source_asset_id: str | None = None
    source_output_id: str | None = None
    priority: str = "hard"  # hard | medium | advisory
    stable_bone_traits: list[str] = []
    stable_feature_relationships: list[str] = []
    forbidden_geometry_drift: list[str] = []
    allowed_surface_changes: list[str] = []
    prompt_rules: list[str] = []
    review_checks: list[str] = []
    metadata: dict[str, Any] = {}
```

Required `stable_bone_traits` examples:

```text
face width/length ratio
cheek volume and cheekbone direction
jawline and chin scale
forehead/midface/lower-face proportion
age impression
```

Required `stable_feature_relationships` examples:

```text
eye spacing and base eye shape
eyebrow-eye relationship
nose bridge/tip/wing relationship
nose-mouth relationship
mouth width and lip contour family
```

### 6.2 StylingDeltaPolicy

```python
class StylingDeltaPolicy(V3BaseModel):
    policy_id: str
    applies: bool = False
    allowed_changes: list[str] = []
    disallowed_identity_changes: list[str] = []
    style_prompt_scope: str = "surface_only"
    metadata: dict[str, Any] = {}
```

Required allowed changes:

```text
makeup color/intensity
hair styling and accessory placement
wardrobe and costume
lighting and color grade
expression, gaze, pose, head angle
scene and camera treatment
```

Required disallowed identity changes:

```text
face slimming
eye enlargement
nose reshaping
lip reshaping
jaw/chin remodeling
age-band shift
generic beauty-face replacement
```

### 6.3 PortraitIdentitySimilarityReview

```python
class PortraitIdentitySimilarityReview(V3BaseModel):
    review_id: str
    project_id: str | None = None
    job_id: str | None = None
    output_id: str | None = None
    reference_asset_id: str | None = None
    status: str = "not_applicable"  # pass | warning | fail_retryable | manual_review
    bone_structure_identity_score: int | None = None
    facial_feature_relationship_score: int | None = None
    styling_delta_correctness_score: int | None = None
    same_person_readability_score: int | None = None
    beauty_realism_score: int | None = None
    issue_codes: list[str] = []
    allowed_difference_notes: list[str] = []
    forbidden_drift_notes: list[str] = []
    retry_patch: dict[str, Any] = {}
    user_visible_summary: list[str] = []
    metadata: dict[str, Any] = {}
```

### 6.4 BoneStructureRetryPatch

```python
class BoneStructureRetryPatch(V3BaseModel):
    patch_id: str
    applies: bool = False
    reason_codes: list[str] = []
    prompt_additions: list[str] = []
    negative_additions: list[str] = []
    reduce_style_pressure: bool = False
    reduce_archetype_language: bool = False
    require_reference_image: bool = True
    metadata: dict[str, Any] = {}
```

## 7. Prompt And Rule Changes

### 7.1 Prompt Layer Ordering

Provider prompts for portrait image-to-image must be layered in this order:

```text
1. Reference identity contract
2. Bone-structure preservation contract
3. Allowed styling delta
4. User-requested scene / costume / mood
5. Beauty-realism rendering
6. Negative drift / artifact guard
```

The reference identity contract must appear before style archetype language.

### 7.2 Required Provider Prompt Semantics

Prompt wording must express:

```text
Use the uploaded reference as the same person's identity source.
Preserve the underlying bone structure and facial-feature relationships.
Change makeup, wardrobe, lighting, pose, expression, and scene only.
Do not reshape face, eyes, nose, mouth, jaw, chin, or age impression to fit a
generic beauty archetype.
```

When the user asks for strong stylization:

```text
Interpret the style as styling, costume, lighting, and atmosphere.
Do not interpret the style as permission to redesign the person's face.
```

### 7.3 Archetype Pressure Guard

Generic beauty words can still improve the image, but they must be constrained.

Risk words:

```text
perfect oval face
delicate stylized beauty
idol face
doll face
V-shaped jaw
large eyes
high nose bridge
thin elegant lips
ethereal goddess face
```

Rule:

```text
Use these as mood or polish only if they do not conflict with the reference
person's actual bone structure and feature relationships.
```

Prompt compiler should downgrade or scope these terms:

```text
"target beauty style" -> "requested styling, makeup, costume, and atmosphere"
"delicate face" -> "delicate styling while preserving the reference face"
"perfect oval face" -> remove or replace with "reference face shape preserved"
```

Doc88 clarification:

```text
Do not copy a style-family example into universal foundation prompts. The
compiler should use neutral wording such as "target styling" unless the user's
prompt explicitly names a specific style family.
```

## 8. Review And Retry Behavior

### 8.1 New Issue Codes

Add issue codes:

```text
bone_structure_drift
face_shape_drift
cheek_jaw_chin_drift
eye_shape_or_spacing_identity_drift
eyebrow_eye_relationship_drift
nose_mouth_relationship_identity_drift
lip_contour_identity_drift
age_impression_drift
styling_changed_face_geometry
archetype_overrode_reference_identity
same_type_not_same_person
identity_reference_underweighted
```

### 8.2 Review Prompt Requirements

The visual inspector must compare generated output against the reference under
this standard:

```text
Ignore allowed makeup, wardrobe, lighting, expression, pose, and scene changes.
Judge whether the underlying face bone structure and feature relationships
still read as the same person.
```

The inspector must not over-penalize:

```text
new makeup
changed styling
different hair arrangement
different lighting
different expression
different pose
different camera angle
```

The inspector must penalize:

```text
face geometry replacement
beauty-template remodeling
different eye/nose/mouth/jaw relationship
different age impression
same visual mood but different person
```

### 8.3 Auto Retry Conditions

Auto retry is allowed when:

```text
reference image was present
provider output exists
review status is fail_retryable
issue code is identity-specific
retry budget remains available under Doc53
retry patch can reduce style/archetype pressure and strengthen identity
```

Auto retry is not allowed when:

```text
review confidence is low
provider failed before creating an image
the user explicitly requested a different person
the reference is too occluded or low-quality and no reliable face truth exists
the same identity issue already repeated after a stronger patch
```

### 8.4 Retry Patch Strategy

For identity drift:

```text
1. Strengthen reference image usage.
2. Move bone-structure contract earlier in the prompt.
3. Reduce or scope generic beauty archetype words.
4. Convert style words into surface styling only.
5. Add negative drift rules for face, eyes, nose, mouth, jaw, chin, and age.
```

Retry patch example:

```text
The previous result changed the person's underlying face. Regenerate as the
same person from the reference image: keep face width/length ratio, cheek and
jaw direction, chin scale, eye spacing/base shape, eyebrow-eye relationship,
nose-mouth relationship, and lip contour. The requested styling, makeup,
lighting, scene, and pose may change, but facial geometry must not be
redesigned. Preserve the current prompt's intended color, mood, and atmosphere.
```

## 9. Runtime Behavior

### 9.1 Uploaded Portrait Reference

When an uploaded portrait reference has `use_policy = identity` or is inferred
as a face identity reference:

```text
1. Build PortraitBoneStructureLock from the active reference.
2. Build StylingDeltaPolicy from user prompt and mode.
3. Add both into the Visual Capability Cluster result.
4. Thread them into LLM Brain prompt guidance.
5. Thread them into provider prompt compiler.
6. Record them in output metadata.
```

### 9.2 Selected Generated Reference

When a user selects a generated output as reference:

```text
if there is an uploaded portrait truth source:
  uploaded portrait bone truth remains highest priority
  selected output reinforces style, pose family, composition, and project mood

if there is no uploaded portrait truth source:
  selected output becomes the active bone-structure identity source
```

This preserves Doc85:

```text
selected output does not erase uploaded truth
```

### 9.3 Text-Only Human Project

If no uploaded or selected reference exists:

```text
Doc86 does not claim exact identity.
V3 may create a first-output identity anchor after generation.
Subsequent continuations can use that selected/generated anchor.
```

## 10. Frontend / UX Requirement

No new complex beginner UI is required.

Optional folded workflow wording:

```text
V3 kept: the same face structure and facial-feature relationship.
V3 changed: styling, clothing, light, pose, and atmosphere.
```

Do not show:

```text
PortraitBoneStructureLock
bone_structure_identity_score
retry_patch
provider prompt
raw metadata
```

If a result fails identity review but is still visible in project records, the
beginner-friendly summary should be:

```text
This image looked good, but it did not keep the reference person's face closely
enough, so V3 tried again.
```

## 11. Implementation Plan

### Phase 1 - Contracts And Cluster Output

Files:

```text
shared_capabilities/visual_cluster/contracts.py
shared_capabilities/visual_cluster/identity_anchor.py
shared_capabilities/visual_cluster/module.py
```

Tasks:

```text
1. Add PortraitBoneStructureLock.
2. Add StylingDeltaPolicy.
3. Add PortraitIdentitySimilarityReview.
4. Add BoneStructureRetryPatch.
5. Extend existing cluster result metadata without adding a new top-level framework.
6. Ensure serialization is compact and safe.
```

Tests:

```text
contract validation
safe metadata serialization
no V1/V2 runtime imports
encoding guardrail
```

### Phase 2 - Reference Policy Construction

Files:

```text
shared_capabilities/visual_cluster/identity_anchor.py
shared_capabilities/visual_cluster/strong_reference_loop.py
shared_capabilities/visual_cluster/human_variation.py
shared_capabilities/visual_cluster/human_photorealism.py
```

Tasks:

```text
1. Detect portrait identity references from use_policy, role, asset hints, and project context.
2. Build bone-structure lock for uploaded identity references.
3. Build bone-structure lock for selected generated references only when no uploaded truth source exists.
4. Build styling delta policy from the user's requested transformation.
5. Add "style can change surface; identity keeps geometry" rules.
6. Ensure natural variation still allows expression, pose, gaze, head angle, and camera changes.
```

### Phase 3 - Prompt Compiler Layering

Files:

```text
llm_brain/prompts.py
llm_brain/fallback.py
prompt_compiler/provider_notes.py
prompt_compiler/compiler.py
agents/prompt_compiler_agent.py
```

Tasks:

```text
1. Insert identity contract before style/mood language.
2. Scope archetype words so they do not rewrite face geometry.
3. Add compact provider notes for bone-structure preservation.
4. Add negative prompt guidance for identity geometry drift.
5. Keep prompt purity for General Template and avoid product wording.
```

Regression target:

```text
final prompt must say "same person, styling changes only" in model-facing terms
without exposing internal names.
```

### Phase 4 - Provider Metadata And Reference Traceability

Files:

```text
generation_router/providers.py
product_api/outputs.py
product_api/service.py
```

Tasks:

```text
1. Record active bone-structure lock id.
2. Record source reference asset/output id.
3. Record provider reference image count.
4. Record styling delta policy summary.
5. Record whether retry patch reduced archetype pressure.
```

This is required for debugging cases where the output is beautiful but not the
same person.

### Phase 5 - Visual Review Upgrade

Files:

```text
shared_capabilities/visual_cluster/vision_inspector.py
shared_capabilities/visual_cluster/quality_review.py
shared_capabilities/visual_cluster/batch_identity_review.py
product_api/service.py
```

Tasks:

```text
1. Add Doc86 issue codes.
2. Add review prompt that separates allowed styling delta from forbidden bone drift.
3. Add scoring families and thresholds.
4. Mark same-type-not-same-person as fail_retryable when confidence is high.
5. Preserve Doc77 aesthetic review and Doc78 beauty-realism review.
```

Local heuristics must not pretend to judge face identity. They may only detect
objective file issues. Same-person scoring requires a vision-capable reviewer or
explicit metadata from a configured review provider.

### Phase 6 - Retry Closure

Files:

```text
shared_capabilities/visual_cluster/quality_review.py
product_api/service.py
```

Tasks:

```text
1. Convert identity issue codes into BoneStructureRetryPatch.
2. Apply at most one stronger identity retry per job unless Doc53 budget changes.
3. Append retry outputs; never overwrite original outputs.
4. Keep failed-but-visible outputs in project records with beginner-friendly status.
5. Avoid endless loops if the provider continues to ignore the reference.
```

### Phase 7 - Tests And Real Validation

New or updated tests:

```text
alchemy_creative_agent_3_0/tests/test_v3_doc86_portrait_bone_identity_lock.py
alchemy_creative_agent_3_0/tests/test_v3_doc85_image_to_image_reference_truth.py
alchemy_creative_agent_3_0/tests/test_v3_doc78_long_term_identity_beautiful_realism.py
alchemy_creative_agent_3_0/tests/test_v3_doc77_real_review_aesthetic_stability.py
alchemy_creative_agent_3_0/tests/test_v3_visual_auto_retry.py
```

Required assertions:

```text
uploaded identity reference creates PortraitBoneStructureLock
selected generated reference cannot override uploaded portrait truth
provider prompt places identity contract before style contract
archetype terms are scoped or reduced when they conflict with reference truth
vision review distinguishes styling delta from bone drift
identity drift creates bounded retry patch
retry patch asks for same face geometry, not just same vibe
General Template stays scenario-neutral
```

## 12. Real Output Validation Protocol

Use at least two real tests when provider availability allows.

### Test A - Same Person, Different Styling

Input:

```text
Upload a modern portrait reference.
Ask for a strongly different styling direction, scene direction, makeup level,
lighting treatment, or camera language.
Generate one or more images.
```

Pass:

```text
The generated person is readable as the same person after styling change.
Bone structure and feature relationships remain stable.
Makeup, wardrobe, lighting, pose, and mood may differ.
Commercial beauty remains high.
```

Fail:

```text
The result is only the same beauty type.
The face is narrowed, eye/nose/mouth relationship changed, or age impression
shifted into another model.
```

### Test B - Continuation After Selection

Input:

```text
Select the best generated portrait as a project reference.
Continue the project with a different pose, angle, or scene.
```

Pass:

```text
If an uploaded truth source exists, it remains highest priority.
If no uploaded truth source exists, selected output becomes identity source.
New outputs vary naturally without changing bone structure.
```

## 13. Acceptance Criteria

Doc86 is implemented only when all are true:

1. V3 has an explicit portrait bone-structure lock contract.
2. V3 has an explicit styling-delta policy separating allowed surface changes
   from forbidden identity geometry changes.
3. Provider prompts put identity preservation before style archetype language.
4. Review scoring uses "same person under changed styling" as the core
   standard.
5. Same-type-not-same-person is not accepted as strong identity continuity.
6. Identity drift can produce a bounded, precise retry patch.
7. Uploaded portrait truth remains higher priority than selected generated
   continuation references.
8. General Template remains beginner-friendly and scenario-neutral.
9. Existing Doc76, Doc77, Doc78, Doc84, and Doc85 tests continue to pass.
10. Real validation reaches at least:

```text
bone-structure identity >= 85
same-person readability >= 85
beauty-realism >= 85
styling delta correctness >= 85
```

## 14. Implementation Handoff Prompt

Use this prompt when coding begins:

```text
Implement Doc86.

Do not rewrite V3. Keep the work inside the existing Visual Capability Cluster,
LLM Brain adapter, prompt compiler, generation router, product API review/retry,
and project mode storage paths.

Add a portrait bone-structure identity lock and styling-delta policy. When an
uploaded portrait identity reference exists, preserve the same person's
underlying face structure and facial-feature relationships. Allow makeup,
wardrobe, hairstyle, lighting, pose, expression, and scene changes only as
surface/styling changes.

Provider prompts must place the same-person identity contract before style or
beauty archetype wording. Generic beauty words must never reshape face, eyes,
nose, mouth, jaw, chin, or age impression away from the reference.

Doc88 balance requirement: the identity contract must not become so long or so
negative-heavy that it damages the current prompt's requested color, light,
scene, mood, or user-approved positive visual direction. Identity repair must
keep the image as the same person inside the intended atmosphere, not merely as
a stricter but less faithful face-repair frame.

Upgrade visual review so it scores same-person readability by ignoring allowed
styling changes but penalizing bone-structure drift. If a result is merely the
same beauty type rather than the same person, mark it as retryable when
confidence and retry budget allow. Retry patches must reduce archetype pressure
and strengthen exact face-geometry preservation.

Do not expose engineering terms in beginner UI. Keep failed/retried outputs in
project records. Append retry outputs; never overwrite originals.

Run focused Doc86 tests plus Doc77/78/85/88 regressions, compile checks, frontend
static checks, and one real image-to-image validation when provider availability
allows.
```
