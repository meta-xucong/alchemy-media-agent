# 64 V3 Lovart-Level Commercial Quality Closure Spec

## 1. Status And Authority

Doc64 is the next quality-closure plan after Doc63.

Authority chain:

```text
Doc50:
  Reusable visual enhancement belongs in the V3 native Visual Capability
  Cluster.

Doc54:
  Owns the four user-facing General Template modes.

Doc55:
  Owns post-generation vision inspection.

Doc56:
  Owns human identity consistency with natural variation.

Doc58:
  Owns selected-output identity anchors and strong reference continuation.

Doc59:
  Owns mode-aware role differentiation.

Doc60:
  Owns E-Commerce product-suite slot fidelity and label/logo QA.

Doc61:
  Owns portrait real-validation protocol and Lovart benchmark wording.

Doc62:
  Owns stronger portrait-suite art direction.

Doc63:
  Owns image-edit provider stability and bounded image-edit waiting.

Doc64:
  Owns the next commercial quality closure layer: real-output quality review,
  identity/product continuity scoring, suite role coverage auditing, and
  issue-specific retry planning.

Doc65:
  Extends Doc64 for photoreal human outputs. Doc64 stays the broad commercial
  quality closure layer; Doc65 contributes human realism and anti-AI-face
  signals into the same visual cluster and retry pipeline.
```

Doc64 must not replace Project Mode, ScenarioRuntime, Scenario Packs, Product
API, provider adapters, the V3 Brain, or the Visual Capability Cluster. It must
be implemented as V3-owned quality modules under the existing visual cluster and
post-generation review path.

Doc64 is not a sub2api document. Provider availability and upstream cooldowns
remain Doc63/sub2api concerns. Doc64 assumes images can be generated and focuses
on whether the generated images are good enough.

## 2. Current State

V3 has already proven these capabilities:

```text
project-first generation loop
General Template project continuation
four user-facing generation modes
V3-owned LLM/checkpoint Brain path
native Visual Capability Cluster
selected image as strong reference
prompt-level identity preservation
prompt-level natural variation
mode-aware role recipes
post-generation review metadata
bounded visual auto retry mechanism
image-edit provider timeout and retry stabilization
```

The current quality level is:

```text
single image quality:
  close to commercial social-media use in good provider conditions

project style consistency:
  usable and visibly improved

selected-reference continuation:
  working when image-edit provider is stable

Lovart-level commercial suite quality:
  not yet complete
```

Remaining Lovart-gap symptoms:

```text
identity consistency is often directionally correct but not always certain
some portrait sets still look like near-duplicates rather than a directed shoot
some product/lifestyle sets still lean toward safe studio images
post-generation review does not yet judge real image quality deeply enough
auto retry exists but does not always know exactly what to fix
frontend artifacts can explain workflow, but quality evidence is not yet strong
```

## 3. Product Goal

Beginner-facing promise:

```text
The user writes one simple request, optionally picks one image they like, and V3
continues the project into a polished commercial image set without requiring
prompt engineering, model settings, or manual quality diagnosis.
```

Commercial quality promise:

```text
The final set should feel like it was directed by a photographer/art director:
same person or product direction
same visual world
clear role separation
usable composition
clean artifacts
no accidental text or watermark
enough variation for real selection or publishing
```

Doc64 does not claim that every model output will equal Lovart. It defines the
next engineering layer needed to close the gap: V3 must see what it generated,
judge it against the intended mode, and retry only when the issue is specific
and worth fixing.

## 4. Architecture

Doc64 adds one orchestration layer inside the existing V3 visual path:

```text
Project
  -> Template / Scenario Pack
      -> ScenarioRuntime
          -> V3 Brain
          -> Visual Capability Cluster
              -> Reference Continuity Evaluator
              -> Suite Role Coverage Auditor
              -> Commercial Aesthetic Reviewer
              -> Artifact And Text Guard
              -> Issue-Specific Retry Planner
          -> Product API generation
          -> Post-Generation Review
          -> Project Timeline / Workflow Artifacts
```

Implementation location:

```text
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/
```

Allowed new submodules:

```text
reference_continuity_evaluator.py
suite_role_coverage_auditor.py
commercial_aesthetic_reviewer.py
quality_issue_taxonomy.py
quality_retry_planner.py
quality_evidence_package.py
```

Allowed integration points:

```text
post_generation_review pipeline
visual_auto_retry planner
project timeline/workflow artifacts
provider metadata summaries
mode-aware role director outputs
```

Not allowed:

```text
adding quality logic directly into the central framework as hard-coded branches
calling V1/V2 runtime code
changing the four-mode frontend contract
changing provider account routing
auto-writing Brand Memory
raising retry loops without strict budgets
showing engineering scores or debug fields to beginner users
```

## 5. Quality Review Objects

Doc64 requires a structured review package for generated image sets.

Minimum object:

```text
VisualCommercialQualityReview
  review_id
  project_id
  job_id
  template_id
  variation_mode
  reviewed_output_ids
  reference_output_ids
  identity_continuity
  product_continuity
  suite_role_coverage
  natural_variation
  commercial_finish
  artifact_cleanliness
  mode_fit
  retry_recommendations
  user_facing_summary
  advanced_evidence
```

Score bands must be plain and stable:

```text
pass
watch
retry_recommended
block
not_applicable
```

Do not expose raw numeric scores to beginner UI by default. Numeric confidence
may exist internally, but user-facing copy must stay simple.

## 6. Quality Issue Taxonomy

Doc64 standardizes issues so retry can be targeted.

Shared issues:

```text
visible_text_or_watermark
ai_generated_mark
severe_face_artifact
severe_hand_or_body_artifact
composition_unusable
weak_commercial_finish
style_drift
scene_drift
role_collapse
over_cloned_frames
insufficient_variation
format_or_crop_mismatch
```

Human/portrait issues:

```text
identity_drift
face_shape_drift
hair_direction_drift
wardrobe_family_drift
same_expression_repetition
same_head_angle_repetition
same_camera_distance_repetition
unnatural_beauty_render
```

Product issues:

```text
product_identity_drift
label_or_logo_distortion
material_or_shape_drift
unrequested_product_or_prop
unsafe_claim_or_fake_badge
studio_only_when_lifestyle_requested
lifestyle_context_too_weak
```

Each issue must define:

```text
when_to_detect
severity_band
which_modes_it_applies_to
whether_retry_is_allowed
retry_patch_strategy
when_to_stop_retrying
user_facing_wording
```

## 7. Four-Mode Quality Contracts

Doc64 must preserve the four user-facing modes from Doc54.

### 7.1 Similar Candidates Mode

Purpose:

```text
Give the user close alternatives so they can pick the best frame.
```

Quality expectations:

```text
same identity or product direction
same visual world
minor expression, pose, crop, angle, detail, or lighting micro-variation
no large scene jump unless requested
```

Retry emphasis:

```text
identity_drift
style_drift
visible_text_or_watermark
severe artifacts
```

Do not over-penalize:

```text
role_collapse
close visual similarity
```

The mode is allowed to be similar. The problem is not similarity; the problem is
unusable sameness, artifact errors, or loss of the selected direction.

### 7.2 Delivery Suite Mode

Purpose:

```text
Create a useful commercial set with different image duties.
```

Quality expectations:

```text
same person/product/brand world
clear role separation
different crop, angle, scale, scene duty, or usage purpose
coherent set-level finish
```

Retry emphasis:

```text
role_collapse
over_cloned_frames
same_expression_repetition
same_head_angle_repetition
studio_only_when_lifestyle_requested
weak commercial role coverage
```

This is the primary Lovart-benchmark mode.

### 7.3 Creative Exploration Mode

Purpose:

```text
Explore different creative directions before the user locks one.
```

Quality expectations:

```text
broader mood, palette, scene, styling, camera, or concept differences
subject direction remains understandable unless user asks for abstraction
each option feels intentionally different, not randomly drifted
```

Retry emphasis:

```text
uncontrolled identity/product drift
weak concept separation
unusable composition
visible text or watermark
```

Do not over-penalize:

```text
large visual differences
broader styling variation
```

### 7.4 Format / Layout Adaptation Mode

Purpose:

```text
Adapt the same selected idea to different platform ratios, crops, and layouts.
```

Quality expectations:

```text
same core image idea
same identity/product/brand world
different crop, aspect ratio, safe area, and layout affordance
no unnecessary scene or styling drift
```

Retry emphasis:

```text
format_or_crop_mismatch
safe_area_failure
identity/product drift
unwanted new elements
visible text or watermark
```

Do not over-penalize:

```text
repeated styling
same pose if the format adaptation requires it
```

## 8. Reference Continuity Evaluator

The evaluator compares selected references against generated outputs.

Inputs:

```text
selected_output_refs from Project Context
strong_reference_bindings from Doc58
identity_lock_profiles from Doc56/58
generated output metadata
actual generated image files
variation_mode
role recipe
```

For portraits it should judge:

```text
same broad face direction
same body/proportion direction
same hair color/length/styling direction
same wardrobe family
same lighting/color world
natural expression and pose variation
```

For products it should judge:

```text
same product shape
same label/logo direction
same material/color cues
same package proportions
no unrequested new product identity
```

Doc64 does not require perfect biometric or product-recognition precision. It
requires a pragmatic commercial reviewer that can catch obvious drift and
produce useful retry instructions.

## 9. Suite Role Coverage Auditor

The auditor checks whether a set actually covers the intended roles.

Inputs:

```text
variation_mode
mode role recipes from Doc59/62
generated image files
output metadata
prompt role lanes
```

Delivery Suite minimum checks:

```text
at least one hero/cover-like frame
at least one closer subject/detail frame when requested
at least one angle/pose/crop variation when requested
at least one environment/context/lifestyle frame when requested
no majority collapse into the same crop and pose
```

Similar Candidates minimum checks:

```text
enough small differences to make selection meaningful
no large unwanted scene/style jump
```

Creative Exploration minimum checks:

```text
options have intentionally different directions
differences match user intent rather than random drift
```

Format Adaptation minimum checks:

```text
output composition fits requested ratio or layout use
core visual idea remains recognizable
```

## 10. Commercial Aesthetic Reviewer

The reviewer checks whether the output feels commercially usable.

General criteria:

```text
clear main subject
intentional composition
good lighting
clean color palette
usable crop
background supports the subject
no random text or watermark
no severe anatomical or product artifacts
no clutter that weakens the intended use
```

Portrait-specific criteria:

```text
skin rendering is natural enough for commercial use
face is not melted or over-smoothed
eyes, mouth, hairline, hands, and shoulders are plausible
pose is believable
```

Product-specific criteria:

```text
product remains inspectable
label/logo is not falsely rewritten
materials and edges are plausible
scene supports commercial selling intent
```

The reviewer should not reject images merely because they are not perfect. It
should reject or retry only when the issue would hurt user trust or commercial
usefulness.

## 11. Issue-Specific Retry Planner

Doc64 retry must be targeted, not generic.

Retry package:

```text
retry_reason
affected_output_ids
mode
role_key
reference_requirements
prompt_patch
negative_patch
provider_reference_strategy
max_attempts_remaining
stop_condition
user_facing_reason
```

Examples:

```text
identity_drift:
  strengthen selected-reference wording
  emphasize same broad face, hair, body, wardrobe family
  reduce concept drift
  keep pose/expression variation allowed

over_cloned_frames:
  preserve identity through reference image, not by copying the still
  vary expression, head angle, camera distance, and pose by role
  avoid repeating the selected frame composition

role_collapse:
  regenerate only collapsed roles when possible
  inject role-specific crop/angle/scene duties
  keep selected identity and visual world constant

visible_text_or_watermark:
  reinforce no visible text, no watermark, no AI-generated mark
  retry affected outputs only

studio_only_when_lifestyle_requested:
  add real environment, natural context, scene interaction, and lifestyle depth
  preserve product/person identity
```

Retry guardrails:

```text
max one automatic retry per affected output by default
max two automatic retries for a whole job unless explicitly configured
no visual-quality retry if provider failure is the only issue
provider failures with zero candidates are handled by Doc81 provider-failure
recovery before visual review begins
no retry if issue confidence is low and image is otherwise usable
no retry if the same issue persists after retry
no retry loop that keeps changing the user's locked direction
```

When retry is skipped, V3 should still record the issue in the advanced workflow
artifact and show a simple user-facing message if needed.

## 12. User-Facing Workflow Artifact

Beginner UI must stay image-first.

Default visible summary:

```text
V3 checked this set for consistency, useful variation, and obvious visual
problems.
```

Useful plain-language bullets:

```text
same style direction kept
selected reference used
roles are different enough / need improvement
no obvious text or watermark found / issue found and retried
```

Advanced folded details may show:

```text
selected reference used
mode chosen
role plan
what V3 checked
what V3 retried
final prompt summary
remaining cautions
```

Forbidden in beginner-visible default UI:

```text
provider
job id
raw score values
capability module names
manifest
debug payload
stack trace
```

## 13. Development Plan

### Phase 1: Review Contracts

Add typed contracts or dataclasses for:

```text
VisualCommercialQualityReview
ReferenceContinuityResult
SuiteRoleCoverageResult
CommercialAestheticResult
QualityIssue
QualityRetryPlan
QualityEvidencePackage
```

Acceptance:

```text
objects can serialize into Product API job metadata
objects can be shown in project timeline/workflow artifacts
objects do not expose engineering language by default
```

### Phase 2: Deterministic Review Layer

Before using expensive vision calls, add deterministic review based on:

```text
mode role metadata
prompt lanes
reference_asset_count
post-generation review package
known issue flags
image size / aspect ratio
existing output metadata
```

Acceptance:

```text
unit tests can simulate role collapse
unit tests can simulate missing reference continuation
unit tests can simulate visible-text issue flags
retry planner receives structured issues
```

### Phase 3: Real Vision Review Layer

Add or extend a vision inspector that can inspect actual generated images.

Acceptance:

```text
can compare selected reference to generated outputs
can detect obvious text/watermark/artifact issues
can flag over-cloned portrait suite
can flag role collapse in delivery suite
can keep similar candidates mode tolerant of close variants
```

The implementation may use an available V3-owned vision provider adapter. It
must degrade gracefully when no vision provider is configured.

### Phase 4: Issue-Specific Retry Integration

Wire quality issues into Doc53 visual auto retry.

Acceptance:

```text
retry plan is issue-specific
retry budgets are bounded
retry patch preserves selected reference and mode
same issue does not loop indefinitely
retry result is recorded in workflow artifact
```

### Phase 5: Project Evidence And UI Summary

Persist the quality evidence package into Project timeline and workflow
artifacts.

Acceptance:

```text
project page can show simple quality summary
advanced folded panel can show what V3 checked
no raw engineering fields leak into default UI
old project history remains readable
```

### Phase 6: Real Validation

Run real validation for:

```text
portrait similar candidates
portrait delivery suite
portrait creative exploration
portrait format/layout adaptation
product delivery suite
product lifestyle suite
```

Acceptance:

```text
contact sheets saved
result JSON saved
quality review package saved
retry decisions recorded
manual Lovart comparison notes recorded
```

## 14. Test Plan

Focused tests:

```text
test_v3_commercial_quality_review_contracts.py
test_v3_reference_continuity_evaluator.py
test_v3_suite_role_coverage_auditor.py
test_v3_quality_retry_planner.py
test_v3_project_mode.py
test_v3_post_generation_vision_review.py
test_v3_visual_auto_retry.py
test_v3_mode_aware_role_director.py
```

Regression:

```text
python -m pytest alchemy_creative_agent_3_0/tests tests -q --tb=short
python -m compileall -q alchemy_creative_agent_3_0/app alchemy_creative_agent_3_0/tests tests src_skeleton/app
node --check src_skeleton/app/static/app.js
git diff --check
```

Real validation:

```text
run portrait delivery-suite continuation with selected reference
run portrait similar-candidates continuation with selected reference
run product delivery-suite project
inspect contact sheets
compare against Doc61-63 outputs
record whether identity certainty, role separation, and commercial finish improve
```

## 15. Completion Criteria

Doc64 is complete when:

```text
quality review contracts exist
real-output quality review package is produced for generated jobs
four modes receive mode-specific quality checks
identity/product continuity is reviewed against selected references when present
delivery-suite role coverage is reviewed
issue-specific retry plans are generated and bounded
user-facing workflow artifact explains checks in plain language
focused tests pass
broad regression passes
real portrait and product validations are recorded
remaining Lovart gaps are explicitly documented instead of hidden
```

## 16. Compatibility Audit

Doc64 remains compatible with existing V3 design because:

```text
Project remains the application layer over jobs
Template remains the user entry
Scenario Pack remains the template runtime mechanism
Visual Capability Cluster remains the home for reusable visual intelligence
Post-generation review remains the quality integration point
Doc53 remains the retry-budget authority
Doc54 remains the four-mode authority
Doc60 remains E-Commerce product-suite authority
Doc63 remains provider-stability authority
```

If implementation work discovers a conflict, the newer commercial-quality goal
does not automatically win. The developer must preserve the core architecture
and move the new behavior into the correct Visual Capability Cluster submodule
or Project workflow artifact.
