# 83 V3 Retry Delivery Layer And Reference Identity Conflict Closure Spec

## 1. Status And Authority

Doc83 is an additive bugfix and quality-closure document for the issues found
after Doc82 project-output reconciliation was deployed.

Authority chain:

```text
Doc50:
  Visual enhancement stays inside the V3 native Visual Capability Cluster.

Doc53:
  Owns bounded visual auto retry execution and loop prevention.

Doc55 / Doc77:
  Own real visual review and aesthetic-stability signals.

Doc56 / Doc58 / Doc66 / Doc78:
  Own human identity consistency, selected-output references, strong-reference
  closure, and beautiful-realism balance.

Doc82:
  Output store is the source of truth for generated image files, and frontend
  recovery must reconcile from project outputs.

Doc83:
  Defines how retry outputs become final deliverables, how over-sensitive
  watermark review is corrected, and how uploaded human reference images win
  over conflicting prompt details for identity-critical traits.
```

Doc83 must not replace Project Mode, ScenarioRuntime, Product API,
CentralCreativeBrain, provider adapters, or the Visual Capability Cluster. It
adds child behavior under existing modules.

## 2. Problem List

The latest VPS run exposed these user-visible issues:

```text
requested_count_display_mismatch:
  The user requested 4 images. The backend generated the original 4 plus an
  automatic retry 4, but the frontend treated all 8 as the same formal result.

retry_delivery_not_layered:
  Retry outputs and original outputs were not separated into final delivery,
  replaced/original versions, and workflow history.

watermark_false_positive:
  Original images were auto-retried for lower_right_mark_artifact and
  ai_generated_badge_trace even though manual review of the actual corners
  showed no obvious watermark, AI-generated text, logo, or signature.

identity_reference_too_weak:
  Uploaded portrait reference influenced broad style/type, but generated faces
  looked like similar East Asian women rather than the same person.

prompt_reference_conflict_not_resolved:
  A highly specific prompt changed hair length, makeup, setting, and mood. V3
  did not clearly separate identity-locked traits from allowed styling changes.

frontend_current_result_not_rebuilt_from_outputs:
  The project output store can contain the complete generated set, while the
  current result board may still show only the first response candidate unless
  reconstructed from project outputs.
```

## 3. Product Principles

Beginner-facing behavior:

```text
If the user asks for 4 images, the main result area should show 4 final images.
If V3 quietly fixed an obvious issue, the fixed set becomes the main set.
The earlier set is still available, but only inside workflow/history details.
The user should never feel that V3 ignored the requested count.
```

Commercial-quality behavior:

```text
Automatic retry must repair clear, high-confidence failures.
Low-confidence review should not spend extra credits or double the visible
deliverable count.
When a portrait reference image is uploaded, identity-critical traits are
protected before prompt aesthetics are applied.
```

## 4. Architecture Boundary

### 4.1 Visual Capability Cluster Owns Review And Identity Signals

Extend existing visual-cluster children only:

```text
VisionOutputInspector:
  stricter watermark/corner-mark confidence
  explicit low-confidence manual-review result

StrongReferenceClosurePackage / identity modules:
  uploaded portrait identity classification
  prompt-reference conflict map
  identity-locked trait package
  allowed-styling-change package
```

### 4.2 Product API Owns Delivery Layering

Extend existing Product API project/job output assembly:

```text
group outputs by job_id and visual_auto_retry_attempt
choose final delivery attempt
mark superseded attempts
return main_delivery_outputs separately from process_outputs
keep output store append-only
do not delete originals
```

### 4.3 Frontend Owns User-Friendly Presentation

Extend existing V3 frontend only:

```text
main result board shows final delivery outputs only
workflow/history can reveal replaced originals
recent project/gallery uses final delivery thumbnail first
advanced details may show "V3 made a cleaner pass" without engineering jargon
```

Doc83 must not:

```text
create another retry loop
increase retry budget
hide retry cost or output provenance from metadata
store visual logic in CentralCreativeBrain
make General Template require a vertical suite definition
delete or overwrite old outputs
```

## 5. Output Delivery Layer Contract

### 5.1 Delivery Group

For every project job, build a delivery group from output records:

```text
DeliveryGroup:
  project_id
  job_id
  requested_image_count
  attempts:
    attempt_index
    output_ids
    candidate_ids
    created_at_first
    created_at_last
    retry_reason_codes
    review_confidence
    delivery_state
  final_attempt_index
  final_output_ids
  superseded_output_ids
  user_visible_summary
```

### 5.2 Attempt Rules

Attempt index source order:

```text
metadata.visual_auto_retry_attempt
metadata.retry_attempt
0
```

Rules:

```text
attempt 0 is the original generation
attempt > 0 is a visual retry generation
if a later attempt exists and has at least requested_image_count usable outputs,
  it becomes final_delivery
if a later attempt exists but is incomplete, original remains final_delivery
if no attempt reaches requested_image_count, choose the largest usable attempt
  but mark delivery_state=partial
```

### 5.3 Main Result Count Rule

The main result board must never show more than requested_image_count images for
one generation action unless the user explicitly opens process history.

```text
requested 4
original 4
retry 4
main result = retry 4
process history = original 4 + retry reason
```

If retry is a candidate-scoped future enhancement rather than whole-set retry:

```text
main result = original good candidates + retry replacements
count <= requested_image_count
```

## 6. Watermark And Corner-Mark Retry Precision

### 6.1 False Positive Case

Observed case:

```text
issue codes:
  lower_right_mark_artifact
  ai_generated_badge_trace

manual image review:
  no obvious watermark, no readable AI-generated mark, no logo, no signature
  corner crops contained flowers, skin, dress texture, bokeh, and background
```

This means the current watermark detector is too sensitive for floral/bokeh
portrait images.

### 6.2 New Retry Gate

Watermark-related automatic retry may execute only when all conditions pass:

```text
issue code is watermark-related
review_confidence >= high threshold
evidence region contains text-like or logo-like structure
evidence is not explained by natural bokeh, flowers, fabric texture, shadow,
  skin highlight, hair strands, or background clutter
retry patch contains a concrete fix
same issue did not already repeat
```

Low-confidence result:

```text
do not retry
record non_retryable_reason=low_confidence_watermark_review
show no scary user-facing warning
optionally place the note in advanced workflow details
```

### 6.3 Required Metadata

Every watermark/corner issue must include:

```text
issue_code
confidence: low | medium | high
evidence_region: lower_right | lower_left | upper_right | upper_left | center | unknown
evidence_type: readable_text | logo_shape | signature_stroke | metadata_trace | ambiguous_texture
human_review_hint
retry_allowed
```

Only `retry_allowed=true` may enter Doc53 execution.

## 7. Uploaded Portrait Reference Conflict Closure

### 7.1 Root Cause Analysis

The latest run showed identity consistency was not strong enough because:

```text
reference image:
  short-to-medium black hair with subtle green highlights
  seaside summer portrait
  cool clean facial type

new prompt:
  long black hair
  garden flowers
  muse-like face
  coral lips and orange-pink eye makeup
  soft-film floral atmosphere

current behavior:
  model preserved broad type and mood, but not exact facial identity
```

Primary cause:

```text
The prompt contained strong face/style/hair instructions that conflicted with
the uploaded identity reference, and V3 did not perform a strict conflict
resolution pass before provider prompt compilation.
```

Systemic cause:

```text
Uploaded human images are not yet always promoted to hard identity references.
They may behave like general visual/style references when the prompt is very
specific.
```

### 7.2 Identity Priority Rule

When a user uploads a portrait reference and does not explicitly ask to create a
new person:

```text
identity-critical traits from the reference image win over prompt aesthetics
```

Identity-critical traits:

```text
face shape
eye shape and spacing
brow direction
nose-mouth relationship
lip shape
jaw and chin direction
cheek volume
natural complexion family
hair length family
hair color family / distinctive highlight
overall age range and subject identity
```

Allowed variation traits:

```text
scene
lighting
pose
camera angle
crop
wardrobe if user requests it
makeup intensity if it does not change face identity
hair movement and styling within the locked hair family
```

Prompt-conflict examples:

```text
Reference has short-medium hair; prompt says long hair:
  keep short-medium hair unless user explicitly says "change hairstyle".

Reference has subtle green highlights; prompt says black hair:
  preserve subtle green highlight as identity/style marker unless user says
  "remove highlight".

Prompt says "muse-like face":
  interpret as mood/beauty direction, not new facial geometry.
```

### 7.3 Conflict Map Contract

Add/extend a conflict package inside the visual cluster:

```text
ReferencePromptConflictMap:
  project_id
  job_id
  reference_asset_ids
  subject_type: human_portrait | product | style | unknown
  identity_locked_traits
  prompt_requested_changes
  allowed_changes
  blocked_changes
  provider_prompt_rules
  negative_prompt_rules
  user_visible_summary
  metadata
```

Provider prompt rules must include plain instructions such as:

```text
Use the uploaded portrait as the same-person identity reference.
Preserve face shape, eye spacing, brow direction, nose-mouth relationship,
jaw/chin direction, complexion family, and hair-length family.
Apply the new scene, lighting, pose, and composition around that same person.
Do not replace the person with a similar-looking model.
```

Negative prompt rules:

```text
different person
generic similar East Asian model
changed face geometry
changed eye spacing
changed jaw/chin shape
changed hair length family unless explicitly requested
beauty redesign that overrides identity
```

## 8. Frontend UX Requirements

### 8.1 Result Board

The result board must show:

```text
title: 本次生成
cards: final_delivery_outputs only
count: requested_image_count or available final count
```

If retry occurred:

```text
small folded note:
  V3 已自动做了一次更干净的版本

button:
  查看被替换版本
```

Do not show:

```text
8 cards for a requested 4-card job
engineering labels such as visual_auto_retry_attempt
raw issue codes in beginner view
```

### 8.2 Project Gallery And Recent Projects

Recent project thumbnails:

```text
use final_delivery_outputs first
do not let superseded originals become the primary thumbnail when retry exists
```

Project history modal:

```text
default tab: final images
optional folded section: earlier versions
```

### 8.3 Workflow Details

Beginner text:

```text
V3 检查到可能影响成片干净度的问题，已保留原图并做了一版更干净的结果。
```

If review confidence was low and no retry ran:

```text
No beginner-facing warning is needed.
Advanced details may say: 检查到可疑边角纹理，但置信度不足，未自动重做。
```

## 9. Implementation Plan

### Step 1: Backend Delivery Group Builder

Add a private helper under Project Mode or Product API:

```text
build_delivery_group(records, requested_image_count)
```

It should:

```text
group records by visual_auto_retry_attempt
sort attempts by attempt index and created_at
detect final attempt
mark superseded outputs
return final outputs and process outputs
```

Where to integrate:

```text
ProjectModeService._project_output_items
ProjectModeService.list_project_outputs
project detail metadata.project_outputs
job response metadata where project_outputs are embedded
```

### Step 2: Frontend Final-Delivery Filter

Add frontend helpers:

```text
v3DeliveryOutputItems(items)
v3ProcessOutputItems(items)
v3OutputDeliveryState(item)
```

Update:

```text
renderV3ResultBoard
renderV3ProjectOutputBoard
renderV3History
openV3ProjectHistoryModal
syncV3CurrentJobFromProjectOutputs
```

### Step 3: Watermark Confidence Gate

Update visual review modules:

```text
VisionOutputInspector watermark/corner-mark code paths
StrictVisualReviewPolicy retry whitelist
AutoRetryDecision construction
```

Required behavior:

```text
ambiguous floral/bokeh/fabric/skin corner findings do not trigger retry
high-confidence readable marks still trigger retry
metadata-only provenance issues remain governed by Doc53/Doc57
```

### Step 4: Reference-Prompt Conflict Closure

Update visual cluster identity/reference modules:

```text
strong_reference_loop.py
identity_lock / identity anchor planner code paths
prompt compiler consumption of closure packages
LLM brain fallback exported artifacts
```

Required behavior:

```text
uploaded portrait reference becomes same-person identity reference by default
conflicting prompt traits are classified as blocked or allowed
provider prompt receives hard same-person identity guidance
new scene/style prompt is applied without replacing face identity
```

### Step 5: Tests And Audit

Add tests:

```text
test_delivery_group_shows_retry_attempt_as_final_only
test_project_outputs_marks_superseded_originals
test_frontend_result_board_filters_process_outputs
test_low_confidence_corner_mark_does_not_retry
test_high_confidence_watermark_still_retries
test_uploaded_portrait_reference_blocks_conflicting_hair_length_change
test_prompt_specificity_does_not_override_face_identity_rules
```

Audit commands:

```text
rg "visual_auto_retry_attempt" src_skeleton/app/static/app.js
rg "delivery_state|final_delivery|superseded" alchemy_creative_agent_3_0/app
rg "low_confidence_watermark_review|ai_generated_badge_trace" alchemy_creative_agent_3_0/app
```

## 10. Acceptance Criteria

1. A job requested for 4 images may internally store 8 outputs after retry, but
   beginner-facing result board shows exactly 4 final images.
2. Earlier retry-superseded outputs are accessible only from folded
   workflow/history details.
3. Project history and recent project thumbnails prefer final delivery outputs.
4. Ambiguous lower-right floral/bokeh/fabric/skin texture does not trigger
   automatic retry.
5. High-confidence real watermark/signature/text still triggers bounded retry.
6. Uploaded human portrait references produce a conflict map before prompt
   compilation.
7. Identity-critical traits from the uploaded portrait override conflicting
   prompt aesthetics unless the user explicitly asks to redesign/change person.
8. Tests for Doc53, Doc66, Doc77, Doc82, and Doc83 all pass.

## 11. Compatibility Notes

Doc83 is compatible with older docs because:

```text
Doc53 retry execution remains bounded and append-only.
Doc66 candidate-scoped retry remains the long-term direction.
Doc77 review quality remains inside the visual cluster.
Doc82 output store remains the source of truth.
Doc83 only changes which outputs are presented as final delivery and raises
the confidence threshold for automatic watermark/corner retries.
```

If older docs imply "old images stayed available and best images are shown
first", Doc83 clarifies:

```text
old images stay available in process history
best/final images appear in beginner-facing result board
requested count is respected in the main delivery surface
```
