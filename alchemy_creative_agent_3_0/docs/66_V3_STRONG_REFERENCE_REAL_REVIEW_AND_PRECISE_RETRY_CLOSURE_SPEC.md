# 66 V3 Strong Reference Real Review And Precise Retry Closure Spec

## 1. Status And Authority

Doc66 is the next Lovart-gap optimization after Doc65.

Authority chain:

```text
Doc50:
  Reusable visual enhancement belongs in the V3 native Visual Capability
  Cluster.

Doc53:
  Owns bounded visual auto retry.

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

Doc64:
  Owns commercial quality closure.

Doc65:
  Owns human photorealism and anti-AI-face pressure.

Doc66:
  Owns the next integration pass: selected-reference closure, real-review
  signal packaging, issue-scoped retry selection, and four-mode quality
  differentiation.
```

Doc66 must not replace Project Mode, ScenarioRuntime, Product API, provider
adapters, the LLM Brain, Doc65, or the Visual Capability Cluster. It adds
child behavior under the existing V3 visual cluster and the existing Product
API review/retry path.

## 2. Problem

V3 now produces better portrait outputs and has a working Doc65 human-realism
layer. However, the remaining Lovart gap is not just prompt wording.

Remaining gaps:

```text
selected references are available, but the continuation contract is not yet
summarized as one clear closure package for provider prompts and audits

post-generation review can detect retryable issues, but retry decisions are
still too job-level and not sufficiently candidate/issue scoped

the four General Template modes have role recipes, but quality review and retry
priorities do not yet differ enough by mode

real-image review signals are not packaged into beginner-facing and
developer-facing summaries that make it clear what was checked and what V3 fixed
```

## 3. Product Goal

Beginner-facing promise:

```text
Pick the image you like, then V3 keeps that direction while making a new set.
If one image has a visible problem, V3 repairs only that type of problem without
replacing the whole project history.
```

Commercial-quality promise:

```text
The system should know what it is preserving, what it is allowed to vary, what
each image in the set is for, and which image-specific issues deserve a bounded
retry.
```

## 4. Architecture Boundary

Doc66 must stay inside these existing seams:

```text
Visual Capability Cluster:
  selected-reference closure package
  mode quality profile
  real-review signal summary

ProductionImageGenerationProvider:
  consumes the closure package as prompt/reference guidance

VisionOutputInspector / OutputQualityReviewMerger:
  emits issue-scoped review signals

V3ProductApiService visual retry path:
  chooses bounded retry actions using candidate/issue-scoped signals
```

Doc66 must not:

```text
create a second template system
create a second retry loop
hard-code visual logic into the central Brain
make General Template depend on V1/V2 runtime code
overwrite old outputs during retry
make E-Commerce rules run inside pure General Template unless product intent is explicit
```

Document 67 follows this rule by cleaning up remaining boundary drift before
quality tuning: selected-reference closure and real-review signals stay in the
visual cluster, while CentralCreativeBrain and fallback Brain consume exported
payloads instead of rebuilding child-module logic.

## 5. New Contracts

### 5.1 StrongReferenceClosurePackage

Purpose:

```text
Convert selected outputs and reference images into one clear continuation
contract that can be read by provider prompts, review modules, and future UI.
```

Minimum fields:

```text
closure_id
project_id
job_id
active
subject_type
reference_strength
provider_reference_required_ids
prompt_only_reference_ids
identity_keep_rules
style_keep_rules
allowed_variations
forbidden_drift
provider_prompt_rules
negative_prompt_rules
user_visible_summary
metadata
```

Rules:

```text
selected outputs are positive context
unselected candidates are history only
selected outputs with file_path become provider-required references
selected outputs without file_path become prompt-only references
human references must include Doc65 do-not-inherit AI-face cleanup rules
product references must preserve product identity and visible label/logo truth
```

### 5.2 ModeQualityProfile

Purpose:

```text
Make the four Doc54 modes behave differently in review and retry, not only in
frontend labels.
```

Modes:

```text
Canonical mode keys must stay compatible with Doc54/front-end values. Short
aliases may be accepted only as compatibility input, but stored metadata should
prefer the canonical keys below.

selection_candidates:
  goal: create close alternatives for choosing the best one
  review priority: identity consistency, small but visible pose/expression/crop
  failure: options are too different, or too identical

delivery_suite:
  goal: create a useful commercial set
  review priority: role separation, cover/detail/context usefulness
  failure: roles collapse into the same image duty

creative_exploration:
  goal: explore stronger visual directions while keeping the core subject
  review priority: creative distance without subject drift
  failure: no meaningful exploration, or subject identity is lost

format_layout_adaptation:
  goal: adapt the same visual direction to layout/aspect/platform needs
  review priority: crop safety, subject placement, usable negative space
  failure: layout does not fit or subject is cropped badly

Compatibility aliases:
  creative_explore -> creative_exploration
  layout_adaptation -> format_layout_adaptation
  format_adaptation -> format_layout_adaptation
```

Minimum fields:

```text
profile_id
mode
user_visible_label
review_priorities
pass_conditions
retry_triggers
prompt_guidance
negative_guidance
metadata
```

### 5.3 RealReviewSignalPackage

Purpose:

```text
Turn actual image inspections and quality reports into one package that can
drive precise retry and user-friendly workflow explanations.
```

Minimum fields:

```text
package_id
project_id
job_id
candidate_signals
retryable_candidate_ids
non_retryable_candidate_ids
issue_summary
mode_quality_status
reference_continuity_status
commercial_readiness_status
user_visible_summary
metadata
```

Each candidate signal:

```text
candidate_id
output_id
status
issue_codes
retryable_issue_codes
retry_patch
recommended_action
user_visible_summary
metadata
```

## 6. Provider Prompt Rules

Provider prompts must consume the new strong-reference closure package.

For human subjects:

```text
Preserve:
  broad face shape, age direction, body type, hair direction, wardrobe category,
  lighting direction, selected style world

Allow:
  expression, gaze, head angle, pose, camera distance, crop, scene depth,
  small hair motion/styling changes

Avoid:
  same exact expression, same face angle, copied still, over-smoothed AI face,
  inherited waxy skin or template smile
```

For product subjects:

```text
Preserve:
  shape, material, color, proportions, label/logo location, package silhouette

Allow:
  scene, camera angle, lighting, props, background, layout

Avoid:
  invented product, rewritten label, hidden logo, unrelated product, label drift
```

## 7. Precise Retry Rules

Retry must be candidate/issue scoped.

Default policy:

```text
retry only if there is at least one retryable issue and a non-empty retry patch
retry at most the configured Doc53 budget
do not retry only because a passable image is not perfect
do not retry all outputs when only one candidate has an issue
append retry outputs; never overwrite existing outputs
stop if the same issue repeats after the configured retry budget
```

Issue groups:

```text
artifact_cleanup:
  visible_text_artifact, watermark_or_signature, ai_generated_badge_trace,
  faint_corner_watermark, lower_right_mark_artifact

identity_reference:
  identity_drift, hair_or_outfit_drift, camera_distance_drift,
  same_ai_face_repetition

human_realism:
  plastic_skin, over_smoothed_skin, missing_skin_texture, template_smile,
  uncanny_eye_expression, wax_skin_highlight

suite_role:
  mode_role_duplication, delivery_suite_role_collapse,
  ecommerce_suite_role_mismatch, format_layout_collapse

product_truth:
  product_identity_drift, product_label_drift, product_label_unreadable,
  product_logo_or_label_obscured
```

## 8. Frontend/UX Contract

Doc66 does not require new UI in this coding pass, but it must expose metadata
that future UI can show without engineering language:

```text
V3 kept:
  selected person/product/style direction

V3 changed:
  pose, crop, role, layout, or scene according to the chosen mode

V3 checked:
  consistency, role usefulness, text/watermark artifacts, human realism/product truth

V3 fixed:
  concise issue names from retry execution records
```

Normal UI must not show:

```text
provider
job id
manifest
prompt compiler
capability module
runtime class names
```

Advanced folded workflow may show:

```text
final prompt excerpts
selected reference rules
quality checks
retry reasons
```

## 9. Implementation Plan

### Step 1: Contracts

Add contracts under `visual_cluster/contracts.py`:

```text
StrongReferenceClosurePackage
ModeQualityProfile
RealReviewCandidateSignal
RealReviewSignalPackage
```

Do not remove existing contracts.

### Step 2: Visual Cluster Builders

Add or extend visual cluster submodules:

```text
strong reference closure builder:
  consumes StrongReferenceContinuationPlan, ProjectIdentityAnchor,
  VisualIdentityLockProfile, Doc65 guidance

mode quality profile builder:
  maps the effective Doc54 mode into review priorities and retry triggers

real review signal builder:
  summarizes candidate-level reports and retry patches
```

### Step 3: Provider Integration

Update `ProductionImageGenerationProvider`:

```text
read strong_reference_closure_package from visual_cluster
add provider_prompt_rules to final provider prompt
add negative_prompt_rules to negative constraints
include closure metadata in persisted output metadata
```

### Step 4: Post-Generation Review Integration

Update `OutputQualityReviewMerger`:

```text
emit candidate-scoped review signals
preserve existing auto_retry_decisions for backward compatibility
add metadata source: doc66_real_review_signal_package
```

### Step 5: Product API Retry Selection

Update `V3ProductApiService`:

```text
prefer RealReviewSignalPackage retryable candidates when present
merge retry patches by issue group
keep bounded retry attempts
append outputs instead of replacing them
record candidate ids and issue groups in visual_retry_execution records
```

### Step 6: Tests

Add focused tests:

```text
selected output with file_path creates strong reference closure package
Doc65 human do-not-inherit rules appear in closure negative rules
provider consumes closure prompt and negative rules
fake post-generation AI-face issue creates candidate-scoped signal
visual retry signal prefers candidate-scoped real-review package
four modes expose different ModeQualityProfile review priorities
beauty portrait still does not route to local service
```

Run:

```text
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_strong_reference_real_review_closure.py -q --tb=short
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_human_photorealism_layer.py alchemy_creative_agent_3_0/tests/test_v3_post_generation_vision_review.py alchemy_creative_agent_3_0/tests/test_v3_visual_auto_retry.py -q --tb=short
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_project_mode.py alchemy_creative_agent_3_0/tests/test_v3_provider_output_production.py -q --tb=short
python -m pytest alchemy_creative_agent_3_0/tests tests -q --tb=short
git diff --check
```

## 10. Acceptance Criteria

Doc66 is complete when:

```text
documentation is added and indexed
selected-reference closure package is present in visual_cluster facts
provider prompts consume closure rules
real review signal package exists after post-generation review
candidate-scoped retry signals are available without breaking old retry decisions
four modes expose different quality/retry profiles
all focused and broad tests pass
```

## 11. Compatibility Statement

Doc66 is compatible with existing V3 architecture because:

```text
Project still wraps Job
Template still wraps Scenario Pack
Visual enhancements remain under the V3 native Visual Capability Cluster
Post-generation review still uses Doc55 contracts
Retry still obeys Doc53 budgets
Doc65 remains the human-realism specialist, not a replacement for review/retry
E-Commerce remains product-gated and does not leak into General Template
```

If Doc66 conflicts with Doc65 for human outputs, preserve identity first, then
apply human realism cleanup. If Doc66 conflicts with user-requested stylization,
the user request wins and human photorealism is reduced or disabled.
