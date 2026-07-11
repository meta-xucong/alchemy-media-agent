# 67 V3 Visual Boundary And Quality Reinforcement Spec

Doc94 correction note:

```text
Doc67 remains the module-boundary authority. Its named real-generation cases
are regression fixtures only. They cannot become category-specific shared
runtime rules; Doc94 owns the anti-overfitting gate.
```

Status: accepted current-stage optimization spec.

This document is the next implementation authority after document 66.

It does not create a new architecture layer. It tightens the existing V3 visual
module boundary, then improves quality by refining existing module standards,
prompt contracts, retry decisions, tests, and real validation.

Document 68 is the next accepted authority after this document. Doc68 keeps the
same boundary rules and adds casebook-guided photographic recipe tuning inside
the existing Visual Capability Cluster. If Doc68 and Doc67 conflict on recipe
details, use Doc68. If they conflict on architecture ownership, use this
document and Doc50: reusable visual intelligence belongs inside the V3 Visual
Capability Cluster, not in CentralCreativeBrain or provider routing.

Document 69 is the accepted authority after Doc68 for prompt atom realism and
reference absorption. It keeps this boundary intact and only strengthens
existing visual_cluster modules.

Doc101 execution refinement:

```text
This document still forbids CentralCreativeBrain and fallback Brain from
constructing visual modules. Central Brain may emit semantic capability intent.
The Visual Capability Cluster owns manifest validation, dependency/conflict
resolution, and selective execution. Inactive modules must not leak into prompt,
review, retry, or project memory.
```

## 0. Boundary Cleanup Pre-Chapter

### 0.1 Goal

Recent V3 work successfully moved strong references, human photorealism, mode
quality profiles, real review signals, and commercial quality review under the
V3 Visual Capability Cluster.

The remaining risk is not missing functionality. The remaining risk is boundary
drift:

```text
visual rules accidentally rebuilt inside CentralCreativeBrain
fallback Brain instantiating visual child modules
template-specific role mapping leaking into the central framework
retry policy duplicating visual issue semantics outside the cluster contract
```

This document requires a small cleanup before further quality tuning.

### 0.2 Ownership Rule

Use this ownership table for all future changes:

```text
CentralCreativeBrain
  may orchestrate V3 stages
  may read visual_cluster metadata
  may copy existing role metadata onto assets and generation plans
  must not instantiate visual child modules
  must not rebuild visual role plans
  must not own reusable visual rules

LLM Brain / fallback Brain
  may read visual_cluster summaries
  may format checkpoint output
  may degrade to simple generic fallback text when cluster data is absent
  must not instantiate visual child modules
  must not become a second visual module runtime

Visual Capability Cluster
  owns reusable visual grammar, identity, reference, mode, suite, realism,
  review, and quality contracts
  owns the capability registry, Activation Planner validation, selective child
  module execution, and exported cluster payloads

Scenario Pack / Vertical Pack
  owns business/template-specific asset intent
  may attach template-specific asset metadata such as ecommerce slots
  may attach already-shaped role metadata for its own assets
  must not bypass the shared visual cluster for reusable visual rules

Generation Provider
  consumes final prompt, reference, negative, and metadata contracts
  may not decide visual strategy

Product API
  owns job/project lifecycle and bounded retry execution
  may call visual review/merge helpers
  must use visual-cluster signal packages as the source of issue semantics
```

### 0.3 Required Cleanup

Implement these cleanup tasks before or together with Doc67 quality tuning:

```text
1. Remove direct visual child module construction from CentralCreativeBrain.
2. Keep CentralCreativeBrain as a metadata consumer only.
3. Move ecommerce role metadata construction into the ecommerce vertical pack,
   because ecommerce slot intent belongs to the ecommerce template path.
4. Remove direct visual child module construction from llm_brain fallback.
5. Let fallback Brain consume visual_cluster human variation fields when present.
6. Add boundary tests proving forbidden imports and constructions do not return.
```

### 0.4 Non-Goals

Do not:

```text
rewrite ScenarioRuntime
rewrite Project Mode
create a second visual cluster
create a second retry loop
remove existing Product API retry execution
remove provider prompt consumption of visual contracts
make V3 depend on V1/V2 runtime code
```

## 1. Quality Reinforcement Goal

Doc67 should make the current modules stricter and more useful. It should not
add another module unless an existing module has no natural owner.

The target is:

```text
same V3 architecture
same Project Mode
same Visual Capability Cluster
same provider layer
better generated-photo realism
clearer commercial suite roles
stronger selected-reference continuity
less over-cloned portrait output
better product-suite usefulness
stricter artifact/watermark rejection
clearer tests and real acceptance evidence
```

## 2. Module Tuning Map

### 2.1 Human Photorealism Layer

Owner:

```text
app/shared_capabilities/visual_cluster/human_photorealism.py
```

Tune:

```text
skin realism
micro-expression variety
natural face asymmetry
real-camera lens behavior
non-plastic makeup and lighting
do-not-inherit AI-face artifacts from selected references
identity consistency without cloning the same expression and head angle
```

Prompt additions should be compact, provider-facing, and not exposed as UI
engineering text.

### 2.2 Mode-Aware Role Director

Owner:

```text
app/shared_capabilities/visual_cluster/mode_role_director.py
```

Tune all four modes:

```text
selection_candidates
  close alternatives, same core idea, small expression/pose/crop differences

delivery_suite
  purposeful set roles such as cover, focus, angle/detail, context/scene

creative_exploration
  broader art-direction distance while preserving subject identity or product truth

format_layout_adaptation
  same creative direction adapted to different crop/layout/output-use needs
```

The role director must avoid producing multiple images that read as the same
face, same pose, same crop, and same commercial purpose unless the user
explicitly asks for near-identical options.

### 2.3 Strong Reference Closure

Owner:

```text
app/shared_capabilities/visual_cluster/doc66_closure.py
```

Tune:

```text
selected images remain strong anchors
identity/product/brand traits are preserved
pose, expression, crop, camera angle, lighting nuance, and scene depth may vary
strong reference does not mean pixel cloning
```

### 2.4 Commercial Quality Review

Owner:

```text
app/shared_capabilities/visual_cluster/commercial_quality.py
app/shared_capabilities/visual_cluster/quality_review.py
```

Tune:

```text
mode role collapse becomes a stronger retry reason
over-cloned portrait batches become retryable when the requested mode expects variety
product lifestyle suites must include at least one genuinely lived-in scene when requested
watermark, AI-generated badges, random text, obvious provider marks remain hard failures
```

### 2.5 Vision Inspector

Owner:

```text
app/shared_capabilities/visual_cluster/vision_inspector.py
```

Tune only deterministic/local checks in this phase:

```text
AI-generated badge traces
watermark-like lower-corner text
provider provenance mismatch
random visible text when no text is requested
```

When real vision provider inspection is unavailable, local checks must still
produce useful retry signals and readable summaries.

### 2.6 Provider Prompt Consumer

Owner:

```text
app/generation_router/providers.py
```

Tune:

```text
consume refined visual cluster contracts
keep final prompt compact enough for the provider
make role-specific instructions visible to the provider
avoid contradictory rules such as "keep identical face" plus "change angle"
avoid product/ecommerce language in pure General Template prompts
```

## 3. Retry Strategy

Doc67 does not replace Doc53 or Doc66. It refines issue selection.

Retry may run only when:

```text
issue is candidate-scoped or clearly batch-scoped
retry patch is specific
retry budget remains
provider failure is not the only issue
the patch changes the next attempt meaningfully
```

Retry must not run when:

```text
the issue is only subjective preference without a clear correction
the same issue already failed after the bounded retry budget
the provider returned no usable output because of external instability
the retry would overwrite old project outputs
```

Priority order:

```text
1. hard artifact: watermark, AI badge, provider mark, broken file
2. product truth: wrong product, missing label/logo, wrong count
3. identity drift: selected human/product reference not preserved
4. over-cloning: same expression/pose/crop across a suite that needs variety
5. role collapse: suite roles do not differ enough
6. commercial finish: image is usable but below publish standard
```

## 4. Implementation Plan

### Step 1: Boundary Cleanup

```text
remove direct ModeAwareRoleDirector construction from CentralCreativeBrain
remove direct HumanNaturalVariationPolicy construction from llm_brain fallback
make ecommerce vertical pack attach mode_role_recipe from ecommerce_recipe
keep CentralCreativeBrain role handling as read-only metadata propagation
```

### Step 2: Quality Rule Tightening

```text
strengthen human realism prompt and negative rules
strengthen role recipes for the four modes
strengthen strong-reference allowed variation language
strengthen review/retry issue text for over-cloning and role collapse
```

### Step 3: Tests

Add or update tests proving:

```text
central brain does not import visual child builders/directors
fallback brain does not instantiate visual child modules
ecommerce assets carry role metadata from ecommerce pack
general portrait prompt contains natural variation but not clone pressure
delivery-suite roles differ by expression, pose, gaze, crop, and scene depth
strong reference keeps identity while allowing natural variation
AI-generated badge/watermark issues remain retryable
product/ecommerce language does not leak into pure General Template prompts
```

### Step 4: Real Validation

Run real validation when provider health allows:

```text
portrait prompt:
  East Asian summer cool portrait with green-highlighted hair

portrait checks:
  same person direction
  less AI-face feel
  different expression/pose/camera/crop between outputs
  no watermark or AI-generated badge
  role separation visible

product prompt:
  summer beverage/product commercial image set

product checks:
  product identity preserved
  label/logo preserved where visible
  roles are distinct
  at least one lifestyle/context image when requested
  no watermark or random text
```

If image generation fails because of upstream instability, record:

```text
request path
provider/model
whether prompt/metadata contracts were correct
whether retry/fallback behaved correctly
```

## 5. Acceptance Criteria

Doc67 is complete only when:

```text
1. The boundary cleanup tests pass.
2. Focused visual cluster tests pass.
3. Provider prompt tests pass.
4. Product API retry/review tests pass.
5. General Template deproductization tests pass.
6. Python compile audit passes.
7. Real portrait validation is attempted and assessed.
8. Real product validation is attempted and assessed.
9. No new V1/V2 runtime dependency is introduced.
10. No engineering internals are added to normal frontend UI.
```

## 6. Compatibility Notes

Doc67 extends, but does not replace:

```text
Doc50: Visual Capability Cluster ownership
Doc53: bounded auto retry guardrails
Doc54: four General Template modes
Doc55: real vision inspection
Doc56: identity and natural variation balance
Doc59: mode-aware role director
Doc60: ecommerce slot and label QA
Doc64: commercial quality closure
Doc65: human photorealism and anti-AI-face layer
Doc66: strong reference closure and real-review signal package
```

When conflict exists, use this priority:

```text
Doc50 for architecture ownership
Doc67 for boundary cleanup and quality tuning
Doc66 for selected-reference and candidate-scoped retry payloads
Doc60 for ecommerce product slot truth
Doc65 for human photorealism
```
