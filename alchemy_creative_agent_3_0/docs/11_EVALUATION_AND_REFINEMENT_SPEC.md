# 11 Evaluation and Refinement Spec

Current Project Mode note:

```text
This document remains the foundational scoring/refinement concept. Document
51 is the current authority for Project Mode commercial visual review,
automatic retry patches, selected-reference consistency checks, identity/product
lock review, and best-output selection.
```

This document defines how Alchemy Creative Agent 3.0 should score candidates, decide accept/retry/reject, and produce refinement plans.

The first pass may use deterministic mock scoring. The contract should still match future real scoring providers.

## 1. Purpose

Lovart-like output stability comes from closed-loop generation, not from one prompt only.

Alchemy 3.0 should not behave like:

```text
prompt → first image → return
```

It should behave like:

```text
plan → generate candidates → score → critique → refine → accept best → update memory
```

## 2. Evaluation Dimensions

Each candidate or planning output should be evaluated on these dimensions:

```text
aesthetic_score
commercial_score
brand_consistency_score
layout_score
text_region_score
platform_fit_score
overall_score
```

All scores are floats from 0.0 to 1.0.

## 3. Score Meaning

### 3.1 aesthetic_score

Measures visual appeal.

First-pass mock factors:

```text
has visual tone
has creative direction
has non-empty prompt
```

Future real providers:

```text
ImageReward
vision model aesthetic critic
human preference model
```

### 3.2 commercial_score

Measures whether output serves the business goal.

Factors:

```text
industry relevance
clear product/service focus
promotion hook present
target audience fit
conversion-oriented composition
```

### 3.3 brand_consistency_score

Measures fit with BrandProfile.

Factors:

```text
visual_tone match
color_palette match
layout_preference match
copywriting_tone match
reference asset usage later
```

### 3.4 layout_score

Measures composition structure.

Factors:

```text
product area exists
headline area exists when text needed
CTA area exists when promotional
reserved text regions exist
visual hierarchy is clear
```

### 3.5 text_region_score

Measures whether exact text can be rendered safely later.

Factors:

```text
html_overlay / svg_overlay used
reserved text regions exist
prompt warns against fake text
explicit Chinese text captured in LayoutPlan
```

### 3.6 platform_fit_score

Measures whether asset matches platform requirements.

Factors:

```text
platform detected
aspect ratio correct
asset type appropriate
purpose matches platform
```

## 4. Overall Score Formula

First-pass default weighted formula:

```text
overall_score =
  aesthetic_score * 0.20
+ commercial_score * 0.25
+ brand_consistency_score * 0.20
+ layout_score * 0.15
+ text_region_score * 0.10
+ platform_fit_score * 0.10
```

Rationale:

```text
commercial usability and brand consistency matter more than pure aesthetics.
```

## 5. Recommendation Thresholds

Default thresholds:

```text
accept:
  overall_score >= 0.78
  and no hard_failure problems

retry:
  0.55 <= overall_score < 0.78
  and max_refine_rounds not exhausted

manual_review:
  overall_score >= 0.65
  but contains warning-level ambiguous issue

reject:
  overall_score < 0.55
  or hard_failure exists
  or retry budget exhausted with severe problems

planning_only:
  used in V3.0 when no real generation is executed
```

## 6. Hard Failures

Hard failures should override score.

Examples:

```text
missing product area for product image
no reserved text region when exact Chinese text is required
aspect ratio missing
platform mismatch
brand profile requested but ignored
provider returned invalid image later
unsafe or legally blocked output later
```

V3.0 foundation should implement only structural hard failures.

## 7. EvaluationProblem Schema

Each problem should include:

```text
code
message
severity
repair_hint
metadata
```

Recommended problem codes:

```text
missing_product_area
missing_text_region
fake_text_risk
platform_ratio_mismatch
brand_style_missing
commercial_hook_missing
layout_too_generic
prompt_too_empty
provider_failure
score_below_threshold
```

## 8. First-Pass Mock Scoring

V3.0 foundation may not generate images.

Use deterministic planning-level scoring:

```text
aesthetic_score:
  0.75 if CreativePlan.visual_direction exists else 0.50

commercial_score:
  0.78 if CommercialBrief.business_goal and commercial_hooks exist else 0.60

brand_consistency_score:
  0.78 if BrandProfile exists and its visual_tone appears in PromptCompilationResult else 0.65

layout_score:
  0.80 if LayoutPlan has product_area and at least one text region else 0.55

text_region_score:
  0.82 if text_rendering is html_overlay/svg_overlay and no-fake-text note exists else 0.50

platform_fit_score:
  0.82 if platform aspect ratio matches defaults else 0.55
```

V3.0 recommendation should usually be:

```text
planning_only
```

unless structural failure occurs.

## 9. RefinementPlan Contract

A `RefinementPlan` should be created when:

```text
recommendation is retry
or hard_failure can be repaired
or evaluation detects fixable issues
```

It should include:

```text
prompt_modifications
layout_modifications
condition_modifications
provider_modifications
reason
action
```

## 10. Refinement Action Mapping

### 10.1 missing_text_region

Repair:

```text
add headline_area or cta_area
reserve top/bottom clean regions
update PromptCompilationResult to request clean negative space
```

### 10.2 fake_text_risk

Repair:

```text
set text_rendering to html_overlay
add provider note: do not render fake final Chinese text
move exact text into LayoutPlan
```

### 10.3 product_area too weak

Repair:

```text
increase product_area priority
set product area to center_large
update visual prompt to emphasize product hero shot
```

### 10.4 brand_style_missing

Repair:

```text
inject BrandProfile.visual_tone and color_palette into style_notes
activate style_condition if reference assets exist
```

### 10.5 platform_ratio_mismatch

Repair:

```text
replace aspect ratio with platform default
update LayoutPlan
update GenerationPlan metadata
```

### 10.6 commercial_hook_missing

Repair:

```text
add commercial_hooks from CommercialBrief
add CTA region
update copy_strategy
```

## 11. Refine Loop Policy

Default loop:

```text
max_refine_rounds: 2
```

Pseudo-flow:

```text
for each asset:
  create candidate or planning candidate
  evaluate
  if accept or planning_only:
    package result
  elif retry and rounds remain:
    create RefinementPlan
    update plan
    retry
  else:
    package best result with warning
```

V3.0 does not need to execute real retries, but it should define the structures.

V3.2 should execute the loop with mock or real generation providers.

## 12. Candidate Selection

If multiple candidates exist:

```text
1. remove hard failures
2. sort by overall_score desc
3. prefer higher commercial_score if tie
4. prefer higher brand_consistency_score if tie
5. prefer lower text risk if tie
6. select best
```

## 13. Brand Memory Update Interaction

Only accepted candidates should propose memory updates.

If recommendation is:

```text
accept → may propose MemoryUpdate
planning_only → may propose but not apply
retry → do not update memory yet
reject → do not update memory
manual_review → wait for user selection
```

## 14. Evaluation Metadata

EvaluationReport metadata should include:

```text
scorer_names
scorer_versions
rule_version
thresholds
formula_version
refine_round
```

Recommended formula version:

```text
v3.0-eval-formula-001
```

## 15. V3.1 Evaluation Goal

V3.1 should implement:

```text
1. deterministic mock scoring
2. overall score formula
3. structural problem detection
4. recommendation thresholds
5. refinement plan generation without real image regeneration
```

## 16. V3.2 Evaluation Goal

V3.2 should implement:

```text
1. multiple candidate handling
2. candidate ranking
3. actual retry loop against mock or real generation provider
4. accepted candidate selection
5. MemoryUpdate proposal from accepted candidate
```

## 17. Future Evaluation Providers

Future providers may include:

```text
ImageRewardProvider
VisionLLMCommercialCritic
BrandConsistencyVisionScorer
LayoutVisionScorer
TextRegionDetector
HumanFeedbackScorer
```

All must implement V3-owned ScoringProvider interface.

## 18. Required Tests

Tests should cover:

```text
1. overall score formula
2. accept threshold
3. retry threshold
4. reject threshold
5. hard failure override
6. fake text risk problem
7. missing text region repair
8. brand style missing repair
9. candidate ranking
10. no memory update for rejected candidate
11. planning_only evaluation in V3.0
```
