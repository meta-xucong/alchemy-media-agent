# V2 Central Brain Task Intent Model Development Design

Date: 2026-06-29

Status: pre-implementation design. This document records the required design,
test plan, rollout plan, and coding boundary before runtime code changes.

## Verified Baseline

The unified working tree is:

```text
D:\AI\Alchemy Dev Agent System\_worktrees\alchemy-media-agent-full-v3-1782102044
```

Current branch:

```text
agent/v3-unified-20260629
```

V2 code status:

```text
custom_media_agent_2_0 has no diff from origin/main.
origin/main and origin/codex/v2-qr-intent-gate both point at the latest V2 fix:
0eabbda Fix V2 image retry timeout handling
```

Verification before this design document:

```text
python -m pytest custom_media_agent_2_0\tests\test_v2_api.py -q
157 passed
```

## Problem Statement

The latest failed V2 image example was not a provider outage or frontend display
issue. The generated pixels already contained the wrong white boxes and cropped
uploaded-image fragments.

The user intent was:

```text
Use the selected premium food poster template as the visual style/frame.
Use six uploaded food images as the concrete food subjects.
Replace the template food imagery with those six foods.
Keep each food complete and reasonably arranged.
```

The current pipeline drifted toward:

```text
Uploaded images are composite content evidence.
Extract food/copy/business facts.
Rebuild semantic content inside the selected template.
```

That interpretation is too weak for this task. It lets the image model treat
the uploaded food photos as reference fragments instead of one-to-one food
replacement subjects.

The root issue is architectural:

```text
Local asset-binding heuristics pre-interpret uploaded assets before Claude
produces a high-level task relationship model.
Claude then has to obey an already-biased asset_binding_policy and
visual_grammar_contract.
```

The fix must not be a larger pile of narrow prompt bans such as "do not create
white boxes" or "do not crop food". The fix is to let the central brain first
understand the general relationship between the user request, selected template,
and uploaded assets.

## Design Principle

Claude Code remains the central creative brain.

Local deterministic policy remains important, but its job is to:

```text
carry, validate, cap, and guard the central-brain decision
```

not to:

```text
replace general task understanding with early regex buckets
```

Short form:

```text
Central brain understands the task relationship first.
Local policy preserves safety, isolation, template priority, and provider
contracts after that relationship is known.
```

This preserves the existing V2 principles:

- selected template remains the highest-priority visual grammar anchor
- uploaded assets fill replaceable slots
- hard identity assets stay as provider input images
- Claude decisions must not leak internal IDs
- V2 must remain isolated from V1 and V3 runtime paths

The refinement is:

```text
Template priority controls the visual grammar.
The task relationship model decides which semantic/template elements are being
replaced, referenced, extracted, fused, generated, or ignored.
```

## Target Architecture

Current simplified flow:

```text
request
  -> build_asset_context()
       -> local role/fusion/placement heuristics
  -> build_visual_grammar_contract()
  -> Claude checkpoint/single-stage decision
  -> compose_prompt_plan()
  -> image provider
```

Target flow:

```text
request
  -> preliminary evidence package
       user prompt
       selected template summary
       uploaded asset briefs
       raw requested roles/notes
  -> Claude task relationship checkpoint
       final artifact goal
       template role
       asset roles
       asset-template relationships
       count correspondence
       fidelity requirements
       conflict policy
  -> local policy normalization
       validate against V2 template lock/isolation/provider rules
       derive asset_binding_policy from task model
       derive visual_grammar_contract from task model
  -> Claude visual strategy / final prompt
  -> prompt plan with preserved task_relationship_model metadata
  -> image provider
  -> output review against relationship expectations
```

## Task Relationship Model

The model is not a provider prompt. It is a compact decision record that tells
the rest of V2 what the user actually wants to happen.

Draft shape:

```json
{
  "artifact_goal": "premium food weekly/monthly card poster",
  "selected_template_role": {
    "mode": "visual_grammar_anchor",
    "preserve": [
      "premium mood",
      "overall hierarchy",
      "lighting logic",
      "typography discipline",
      "spatial rhythm"
    ],
    "may_adapt": [
      "recipe/ingredient cards",
      "literal original food subjects",
      "template placeholder panels"
    ]
  },
  "uploaded_asset_relationships": [
    {
      "relationship": "replace_template_food_subject",
      "asset_group": "uploaded_food_photos",
      "target": "visible food display slots",
      "count_policy": "map all six uploaded foods into visible slots",
      "fidelity": "preserve each food as a complete subject, not a crop fragment",
      "provider_input_required": true
    }
  ],
  "generated_content_policy": {
    "allowed": [
      "compatible background hero food when requested",
      "template-native supporting surfaces"
    ],
    "forbidden": [
      "empty placeholders",
      "invented QR or scan areas unless explicitly requested",
      "using uploaded photos as small decorative fragments"
    ]
  },
  "conflict_resolution": [
    "Selected template visual grammar remains primary.",
    "User-requested replacement relationship overrides literal recipe-card content.",
    "If the selected template has modules that cannot fit six foods, adapt those modules rather than treating uploaded foods as generic evidence."
  ],
  "confidence": 0.86
}
```

This model must support other generic relationships too:

```text
replace_template_subject
replace_template_food_subject
preserve_uploaded_subject_identity
place_logo_on_scene_surface
use_uploaded_frame_as_primary
extract_composite_content
use_as_style_signal
use_as_color_signal
use_as_negative_reference
generate_missing_anchor_content
ignore_unrelated_upload
```

## Key Behavioral Distinctions

### Replacement vs Extraction

Replacement:

```text
Uploaded image is the concrete subject to appear in the new image.
The prompt must preserve the subject and place it in target slots.
```

Extraction:

```text
Uploaded image is a source of information.
The prompt may extract facts, text, offers, food names, or business meaning.
The source layout is not copied.
```

The six-food example is replacement, not extraction.

### Template Grammar vs Literal Template Content

The selected template controls:

```text
composition discipline
visual hierarchy
mood
lighting
background density
typographic treatment
overall visual rhythm
```

It does not automatically force preservation of:

```text
literal original subject
literal recipe/ingredient semantics
empty card modules that conflict with the user's task
QR or scan-code placeholders
```

### Input Images vs Text-Only Prompting

Hard visual constraints must remain provider input images when the provider
supports them. The task relationship model must not downgrade exact uploaded
food/product/logo/face/background requirements into text-only descriptions.

## Integration Points

Expected code areas, once implementation begins:

```text
custom_media_agent_2_0/app/services/asset_binding.py
  Current early role/fusion heuristics.
  Should consume the task relationship model instead of deciding the final
  relationship alone.

custom_media_agent_2_0/app/services/visual_grammar_lock.py
  Should distinguish selected template grammar from literal template semantics.
  Should include task_relationship_model conflict policy in the contract.

custom_media_agent_2_0/app/services/claude_orchestrator.py
  Should add or extend an intent checkpoint that outputs the task relationship
  model before asset_binding_policy is hardened.

custom_media_agent_2_0/app/services/prompting.py
  Should build the final prompt from the task relationship model, Claude final
  prompt, visual grammar contract, and provider plan without adding narrow,
  one-off bans as the main solution.

custom_media_agent_2_0/app/services/output_review.py
  Should review against relationship expectations such as "all six food
  replacement subjects are visibly represented", where possible.

custom_media_agent_2_0/tests/test_v2_api.py
  Should add fake-Claude and prompt-plan tests for replacement, extraction,
  template lock, QR exclusion, and provider input preservation.
```

## Non-Goals

This work must not:

- implement V3 logic inside V2
- call V1 APIs or V1 storage from V2
- change image provider failover behavior
- use mock fallback as a production image fallback
- replace Claude with deterministic creative decisions
- add only a long list of prompt prohibitions
- build a full deterministic layout compositor for all V2 tasks
- weaken the selected-template-first principle

## Implementation Phases

### Phase 1: Model and Trace Contract

Add an internal task relationship model shape and persist it in prompt/run
metadata.

Acceptance:

- Existing tests pass.
- Runs expose task_relationship_model in history metadata.
- No provider behavior changes yet.

### Phase 2: Claude Intent Checkpoint

Extend the Claude intent stage to output the compact relationship model.

Acceptance:

- Fake-Claude tests prove replacement and extraction are distinguished.
- Multimodal source selection still happens when uploaded images need visual
  understanding.
- If Claude fails before any checkpoint, V2 fails or falls back exactly as the
  existing Claude continuation policy allows.

### Phase 3: Asset Binding Consumes Relationship Model

Use the relationship model to derive or correct fusion mode, placement intent,
target surface, provider input requirements, and review expectations.

Acceptance:

- "Replace template food photos with six uploads" does not become
  composite_content_source.
- Composite poster/menu extraction tasks still become content extraction.
- Logo-on-product and logo-on-apparel behaviors remain protected.

### Phase 4: Visual Grammar Contract Uses Relationship Model

Keep the selected template as the visual grammar anchor while allowing literal
template modules to adapt when they conflict with the relationship model.

Acceptance:

- Template grammar remains locked.
- User-requested replacement relationships can adapt literal recipe/ingredient
  cards or empty placeholder panels.
- QR exclusion remains stronger than template or reference QR-like affordances.

### Phase 5: Prompt Composition and Review

Compile final prompts from the relationship model and Claude prompt without
making narrow bans the primary mechanism.

Acceptance:

- Final prompt carries the high-level relationship clearly.
- Provider input images remain referenced as uploaded reference images, not
  internal asset IDs.
- Review metadata records the intended relationship checks.

### Phase 6: Rollout and VPS Verification

Deploy behind a feature flag first.

Suggested flag:

```text
V2_CLAUDE_TASK_RELATIONSHIP_MODEL_ENABLED=true|false
```

Suggested rollout:

```text
local tests
VPS staging-style run with one text-to-image task
VPS image-edit task with six uploaded food references
VPS composite menu/content extraction task
VPS QR-exclusion task
```

## Test Matrix

| Case | Expected relationship | Must prove |
| --- | --- | --- |
| Six food uploads + selected food poster template | replace_template_food_subject | Uploaded foods are hard replacement subjects, not composite evidence |
| Uploaded finished menu/poster + selected template + "extract copy/price" | extract_composite_content | Source layout is not copied, facts are preserved |
| Product image + selected product template | replace_template_subject | Product identity remains provider input image |
| Logo requested on shirt/packaging/bottle | place_logo_on_scene_surface | Logo is not converted to corner badge |
| Prompt says no QR | generated_content_policy forbids QR | No QR or empty scan placeholder is requested by prompt plan |
| Uploaded layout explicitly requested as frame | use_uploaded_frame_as_primary | Uploaded frame may control layout when no selected template overrides it |
| No uploaded assets | normal creative planning | Existing smart enhance/template flow remains stable |
| Timeout/retry path | unchanged | Queue retry and failure details from 0eabbda remain intact |

## Golden Scenario For The Recent Failure

Input summary:

```text
User uploaded six food images.
User selected "Premium Food Recipe Poster Elegant Layout".
User asked to replace the template's food photos with uploaded foods.
User asked for complete, reasonable food presentation and no arbitrary crop.
```

Expected task relationship:

```text
selected template role:
  visual grammar anchor

uploaded assets:
  six concrete food replacement subjects

relationship:
  map all six uploaded foods into visible food display slots

template adaptation:
  preserve premium visual rhythm, typography discipline, and hierarchy
  adapt or suppress recipe/ingredient cards if they become empty placeholders

generated content:
  background hero food may be generated when requested
  do not turn uploaded foods into small decorative fragments
```

Expected prompt-plan effects:

```text
provider operation: image_edit_with_reference_images
reference_image_count: 6
fusion mode: replacement/subject-slot mapping, not composite_content_source
review expectations: all uploaded food subjects visibly represented
```

## Observability Requirements

Prompt/run metadata should include:

```text
task_relationship_model
task_relationship_model_source
relationship_confidence
asset_relationships
template_role
relationship_conflict_policy
relationship_review_expectations
```

The UI does not need to show every field by default, but history/debug views
should preserve enough detail to diagnose whether a bad generation came from:

```text
wrong task relationship
wrong prompt compilation
provider ignoring reference images
provider failure/retry issue
post-generation review gap
```

## Rollback Plan

If the new path regresses production:

1. Disable `V2_CLAUDE_TASK_RELATIONSHIP_MODEL_ENABLED`.
2. Keep the model in metadata only if safe.
3. Fall back to the current asset_binding and visual_grammar behavior.
4. Preserve all queue retry and provider error-detail improvements.

Rollback must not require reverting unrelated V3 files or VPS SSH runbook docs.

## Pre-Implementation Checklist

Before coding:

- Confirm worktree is clean.
- Start a V2-specific branch from `agent/v3-unified-20260629`, for example:

```text
agent/v2-central-brain-task-intent-model
```

- Re-run:

```text
python -m pytest custom_media_agent_2_0\tests\test_v2_api.py -q
```

- Capture at least these production examples for regression comparison:

```text
run_a86e126fc365  six-food replacement failure
run_fe2a34e497b2  image upstream failure/retry sample
run_93e4f29e646d  uploaded-asset status closure sample
```

- Add fake-Claude fixtures before changing live Claude prompts.
- Add tests before changing provider calls.
- Keep provider failover and sub2api behavior out of scope.
- Do not deploy until local V2 tests and V3 smoke tests pass in the unified
  worktree.

## Open Decisions

These should be decided before implementation:

1. Feature flag default:
   - recommended: default off locally until tests are complete, then enable on
     VPS for supervised verification.
2. Relationship model source of truth:
   - recommended: Claude checkpoint is primary; local heuristics may propose
     hints but must not harden the relationship before Claude sees the task.
3. Output review strictness:
   - recommended: metadata warnings first; do not block successful generations
     until review reliability is proven.
4. Final prompt budget:
   - recommended: keep current prompt caps, but allow relationship model to
     replace repetitive local guard text instead of adding more text.
