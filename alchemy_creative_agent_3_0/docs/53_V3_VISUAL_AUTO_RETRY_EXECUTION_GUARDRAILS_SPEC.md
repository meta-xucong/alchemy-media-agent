# 53 V3 Visual Auto Retry Execution Guardrails Spec

## 1. Status And Authority

This document is the implementation authority for the automatic retry
execution mechanism described in document `52`.

It does not replace document `50`, `51`, or `52`.

Authority chain:

```text
Doc50:
  Visual enhancement must stay inside the V3 native Visual Capability Cluster.

Doc51:
  Defines strong references, identity locks, visual review reports, and
  AutoRetryDecision contracts.

Doc52:
  Defines the complete post-generation quality loop and suite director target.

Doc53:
  Defines the narrow, safe, append-only execution rules that turn retry
  suggestions into real retry generation attempts.

Doc55:
  Supplies real post-generation visual inspection signals. Doc53 executes only
  after a retryable signal and non-empty retry patch exist; Doc55 is the
  authority for creating those signals from actual generated image files.
```

Doc53 is binding whenever code decides whether to automatically generate again
after a visual review.

Human-led batch extension:

```text
Document 56 adds retryable over-locking issue codes for human-led batches:
overlocked_expression_pose, duplicate_head_angle_batch, duplicate_pose_batch,
flat_human_variation_batch, identity_anchor_too_rigid, and
human_batch_looks_cloned. Doc53 still owns retry execution guardrails, budgets,
append-only merge, and loop prevention.

Document 57 adds stricter commercial watermark/corner-mark issue codes that
map into watermark_or_signature for retry compatibility: faint_corner_watermark,
ai_generated_badge_trace, signature_like_artifact, lower_right_mark_artifact,
and commercial_cleanliness_failure. Doc53 still owns whether retries may run.

Post-Doc57 provenance hardening adds file/source-level cleanliness issues:
third_party_aigc_metadata and provider_provenance_mismatch. These are not
provider/network failures. They mean the generated file carries unwanted
third-party AIGC traces or does not match the requested provider provenance
expectation, so they may trigger the same safe append-only visual retry budget
when a concrete retry patch exists.

Document 60 adds E-Commerce product-suite slot and label/logo QA issue codes:
product_label_drift, product_label_unreadable,
product_logo_or_label_obscured, ecommerce_slot_mismatch, and
ecommerce_suite_role_mismatch. Doc53 still owns retry budgets and loop
prevention for these issues.
```

## 2. Product Principle

Automatic retry exists to save beginner users from obvious fixable failures. It
must not become an invisible loop that wastes credits, time, provider quota, or
tokens.

The user-facing product should feel simple:

```text
V3 generated the set.
If one obvious issue was safely fixable, V3 quietly made one cleaner extra pass.
Old images stayed available.
The best images are shown first.
Details are folded inside workflow history.
```

The internal rule is stricter:

```text
No clear retryable visual issue -> no automatic retry.
No structured retry patch -> no automatic retry.
Provider or account failure -> no visual retry.
Same issue repeated -> stop.
Retry budget reached -> stop.
```

## 3. Ownership

### 3.1 Visual Capability Cluster Owns Policy Signals

The Visual Capability Cluster owns:

```text
VisualQualityReviewReport
AutoRetryDecision
retry_patch construction
issue categories
retryable or non-retryable classification
plain-language retry reason
```

### 3.2 Product API Owns Execution

The Product API owns:

```text
calling ScenarioRuntime again
preserving project_id and template context
passing retry patch metadata into the normal generation path
merging retry outputs append-only
saving retry execution records
returning merged candidates to the frontend
```

### 3.3 ScenarioRuntime And Providers Stay Normal

Retry execution must use the normal V3 generation path:

```text
Product API
  -> ScenarioRuntime.generate_job
    -> CentralCreativeBrain
      -> GenerationRouter
        -> Provider
```

No retry-specific provider shortcut is allowed.

## 4. Runtime Flow

```text
1. First generation runs normally.
2. Product API saves the first PlanningResult.
3. Product API inspects retry signals from generated metadata and request
   metadata.
4. If the signal is not explicit and safe, execution stops.
5. If execution is safe, Product API builds retry metadata:
   visual_auto_retry_attempt
   retry_attempt
   refine_round
   visual_retry_patch
   visual_retry_reason_codes
6. Product API calls ScenarioRuntime.generate_job again with the same job
   request plus retry metadata.
7. Retry outputs are marked with retry metadata.
8. Retry outputs, generation plans, evaluations, and packaged assets are
   appended to the original PlanningResult.
9. Product API records retry execution details in public status metadata.
10. A second retry is considered only if strict mode allows it and the same
    issue category did not repeat.
```

## 5. Retryable Cases

Automatic retry may execute only for visual issues that are likely fixable by a
prompt/reference patch:

```text
visible_text_artifact
watermark_or_signature
faint_corner_watermark
ai_generated_badge_trace
signature_like_artifact
lower_right_mark_artifact
third_party_aigc_metadata
provider_provenance_mismatch
commercial_cleanliness_failure
product_label_drift
product_label_unreadable
product_logo_or_label_obscured
ecommerce_slot_mismatch
ecommerce_suite_role_mismatch
collage_or_split_panel
unrelated_object
unrelated_product
identity_drift
hair_or_outfit_drift
camera_distance_drift
lighting_mismatch
composition_mismatch
bad_hands_or_body
face_artifact
low_commercial_finish
project_continuity_warning
quality_warning
```

The first implementation may use explicit metadata test signals while the real
post-generation vision inspector is still being expanded. That is acceptable
only when the same guardrails are applied.

## 6. Non-Retryable Cases

Automatic retry must not execute for:

```text
provider_error
provider_timeout
rate_limit
insufficient_balance
missing_api_key
policy_or_safety_block
unsupported_file
file_download_failure
low_confidence_review
manual_review
subjective_quality_only
conflicting_user_request
empty_retry_patch
same_issue_repeated
max_retry_attempts_reached
```

Provider errors should remain provider errors. They must not be hidden as visual
quality retry events.

Provider provenance mismatch is different from provider_error: provider_error
means generation or download failed and should not be retried as a visual issue;
provider_provenance_mismatch means an image was produced but the file contains
source/provenance traces that make it commercially unsafe to pass as a clean
V3 output.

## 7. Retry Budget

Default budgets:

```text
standard: 1 automatic retry
strict: 2 automatic retries
explore: 0 automatic retries unless request metadata explicitly enables it
```

The request may lower the budget with:

```text
max_visual_retry_attempts
disable_visual_auto_retry
```

The request must not raise the budget above:

```text
standard: 1
strict: 2
explore: 1
```

## 8. Retry Patch Contract

The retry patch is a dict. Supported fields:

```text
prompt_additions
negative_additions
negative_prompt_additions
reference_requirements
identity_reinforcement
composition_repair
artifact_repair
object_removal_instruction
provider_hint_overrides
user_visible_reason
```

At least one prompt, negative, reference, identity, composition, artifact, or
object-removal field must be non-empty. Otherwise the retry is skipped.

Provider prompt generation must consume this patch:

```text
prompt_additions -> appended as retry repair guidance
identity_reinforcement -> appended as subject/identity lock guidance
composition_repair -> appended as composition repair guidance
artifact_repair -> appended as artifact repair guidance
object_removal_instruction -> appended as remove/avoid guidance
negative_additions and negative_prompt_additions -> appended to negative
constraints
```

## 9. Append-Only Merge Rules

Retry outputs must be appended to the same Product API job result.

Append:

```text
generation_plans
layout_plans
prompt_compilations
condition_plans
evaluation_reports
asset_pack.assets
asset_pack.manifest retry metadata
PlanningResult.metadata retry metadata
```

Do not overwrite:

```text
old packaged assets
old candidate summaries
old output records
old selected results
old project timeline items
```

Retry assets must carry:

```text
visual_auto_retry_attempt
retry_source_issue_codes
visual_auto_retry_output
retry_patch
```

Provider candidate ids must be unique for retry attempts. Production provider
candidate ids must include the retry attempt only when retry metadata is active.

## 10. Loop Prevention

The executor must stop when:

```text
attempt_index >= max_attempts
same issue category appears again
retry patch is empty
retry generation fails
provider error occurs
quality mode does not allow retry
disable_visual_auto_retry is true
```

The executor may record a skipped or blocked retry execution record, but it must
not call the provider again after a stop condition.

## 11. Public Metadata

ProductJobStatus.metadata should expose:

```text
visual_auto_retry:
  enabled
  executed_count
  max_attempts
  issue_codes
  records
  append_only
```

This is workflow detail metadata. The beginner UI may show a short folded
summary such as:

```text
V3 made one cleaner extra pass because it found visible text risk.
Original images were kept.
```

The UI must not show internal class names such as AutoRetryDecision,
VisualRetryExecutor, ScenarioRuntime, or provider strategy.

## 12. Implementation Plan

### Phase 1 - Documentation

1. Add this Doc53.
2. Add a Doc52 note that Doc53 owns execution guardrails.

### Phase 2 - Product API Executor

1. Add helper methods to `V3ProductApiService`:

```text
_visual_auto_retry_max_attempts
_visual_retry_execution_plan
_visual_retry_patch_from_issues
_run_visual_auto_retries
_merge_retry_generation_result
_mark_retry_generation_result
```

2. Call `_run_visual_auto_retries` after first successful generation and before
   status persistence.

### Phase 3 - Provider Patch Consumption

1. Propagate retry metadata through CentralCreativeBrain generation metadata.
2. Append retry patch text to provider prompt.
3. Append retry negative patch to provider negative constraints.
4. Add retry attempt to production candidate ids only for retry attempts.

### Phase 4 - Tests

Required tests:

```text
explicit retryable visual issue appends retry outputs
same issue does not create repeated retry loop
empty patch skips retry
explore mode does not auto retry by default
production provider consumes retry patch in prompt and negatives
production provider retry candidate id differs from original
```

### Phase 5 - Audit

Run:

```text
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_visual_auto_retry.py -q
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_provider_output_production.py -q
python -m pytest alchemy_creative_agent_3_0/tests tests -q
python -m compileall -q alchemy_creative_agent_3_0/app alchemy_creative_agent_3_0/tests tests
git diff --check
```

## 13. Acceptance Criteria

```text
Doc53 exists and is referenced by Doc52.
Retry execution is opt-out and strictly budgeted.
Retry never runs on provider errors.
Retry requires explicit retryable issue codes and a non-empty patch.
Retry outputs append to the original job result.
Retry candidates are visible in ProductJobStatus.candidates.
Original candidates remain visible after retry.
Retry execution records are stored in status metadata.
Same repeated issue does not trigger repeated provider calls.
Provider prompts consume retry patch text.
Tests prove the append-only and loop-prevention behavior.
```
