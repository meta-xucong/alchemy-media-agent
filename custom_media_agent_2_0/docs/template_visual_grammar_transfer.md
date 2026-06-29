# V2 Template Visual Grammar Transfer Development Design

Date: 2026-06-29

Status: implementation design and test checklist for the V2 central-brain
template-fidelity upgrade.

## Problem Statement

The latest six-food poster run no longer produced white placeholder boxes or a
random QR slot, but it still drifted away from the selected template. The
selected case, `Premium Food Recipe Poster Elegant Layout`, is a premium recipe
infographic poster: large hero food image, title system, ingredient strip,
step-by-step cards, tips, serving suggestions, and refined typography.

The generated image became a two-column meal-card catalog. That means V2 now
understands the uploaded images as replacement food subjects, but it does not
yet transfer the selected template's visual grammar deeply enough.

## Design Principle

Do not fix this with template-name rules, regex buckets, or a growing list of
negative prompt bans.

The central brain must produce a reusable visual grammar transfer plan:

```text
Selected template controls the frame.
Uploaded assets fill or adapt slots inside that frame.
Claude decides the frame/slot/content/typography plan generically.
Local code carries and guards that plan without replacing Claude's judgment.
```

## Target Contract

Extend the central-brain decision with four generic plan groups:

```text
template_frame_directive
  What visual frame must survive: hero area, title area, module rhythm,
  background density, information architecture, and premium mood.

asset_distribution_directive / slot_plan
  How uploaded images map into the template's visual hierarchy: primary,
  secondary, step/module, ingredient/detail, or supporting evidence. This must
  avoid equal-size catalog grids when the template is not a catalog.

virtual_content_directive
  Missing content that should be generated to satisfy the template, such as a
  large compatible background/hero light-food image when uploads do not provide
  that anchor.

typography_directive
  How to preserve the template's typography system while converting visible
  copy into the user's requested language and content.
```

The visual strategy checkpoint should also output equivalent plan fields so the
generation decision stage can compress from a concrete template-fidelity plan
instead of only broad composition/lighting/palette notes.

## Runtime Flow

```text
request
  -> preliminary asset/template evidence
  -> Claude intent checkpoint
       task_intent + template visual grammar directives
  -> Claude visual_strategy checkpoint
       frame plan + slot plan + virtual content + typography + fidelity gates
  -> compressed generation decision
  -> local asset context applies task_intent
       preserve provider input images
       attach visual grammar transfer plan
  -> prompt plan prepends a concise guard block
  -> image provider
```

## Expected Six-Food Behavior

For the recent food poster case, the plan should say:

```text
template frame:
  keep premium recipe infographic hierarchy, not a meal catalog

virtual content:
  generate a large compatible light-meal hero/background food image

asset distribution:
  six uploaded food photos appear as complete food modules, but with varied
  scale and template-native staggered/module rhythm; they do not all become
  equal large catalog cards

typography:
  use refined small Chinese text hierarchy, preserve premium recipe-poster
  typography discipline, and do not inherit English placeholder recipe labels
```

## Claude Timeout Boundary

This work must reduce pressure on Claude rather than widening deterministic
fallback. The prompt contract is compact and stage-based:

- intent stage stays short and outputs task intent plus directives.
- visual strategy stage sees only the selected template evidence and compact
  uploaded asset summaries when a template is hand-selected.
- generation stage receives compressed checkpoints and does not re-read source
  material.
- if Claude is required and still cannot produce a usable checkpoint, V2 must
  fail or retry according to the existing Claude continuation policy; it must
  not silently generate from deterministic creative fallback.

## Non-Goals

- No V3 runtime changes.
- No V1 calls or shared storage.
- No provider failover changes.
- No template-specific hardcoding for `Premium Food Recipe Poster`.
- No deterministic layout compositor.
- No weakening of provider input image preservation for hard uploaded assets.

## Implementation Checklist

1. Extend `OrchestratorTaskIntent` with template visual grammar transfer fields.
2. Extend Claude checkpoint schemas, skeletons, instructions, and compaction to
   carry frame/slot/virtual/typography/fidelity plans.
3. Apply task-intent visual grammar fields into `asset_context`.
4. Include a concise `TEMPLATE VISUAL GRAMMAR TRANSFER` block in the final
   prompt guard.
5. Add regression tests proving the six-food template case no longer compiles
   as an equal-size catalog grid plan.
6. Add checkpoint prompt tests proving the visual strategy stage asks Claude for
   the new generic plan fields.
7. Run focused and full V2 API tests.

## Acceptance Criteria

- The prompt plan carries a template visual grammar transfer plan in metadata.
- The final prompt guard includes frame, asset distribution, virtual content,
  typography, slot plan, and fidelity gates when Claude provides them.
- Provider input image preservation remains unchanged.
- Existing extraction/menu/QR behaviors remain unaffected.
- Claude timeout behavior remains checkpoint-based and does not introduce a new
  deterministic creative fallback.

## 2026-06-29 Follow-Up Findings

The first real provider validation improved size, hero presence, QR removal, and
the white source-photo inset problem, but the composition still leaned toward a
weekly menu card grid. The root cause was not a missing negative prompt. The V2
central relationship had been corrected to `replace_template_food_subject`, but
per-asset relationship metadata and `placement_intent` could still retain an
older `content_evidence`/`semantic_content_slots` interpretation from the
preliminary asset analysis.

The follow-up implementation therefore keeps the optimization generic:

- when Claude task intent overrides the task relationship, each uploaded
  asset's relationship is rewritten to the central relationship;
- template replacement placement intent is overwritten, not merged with stale
  content-evidence placement;
- compact relationship context now carries materialization, narrative, and
  module-completion summaries into later Claude stages;
- `APIConnectionError: Connection error.` from the OpenAI-compatible image
  route is treated as transient/retryable, matching the existing retry behavior
  for 502/503/504/timeout-style failures.

Local validation produced one successful `openai_gpt_image/images.edit` output
with 6 reference images at `1024x2304`; later attempts hit retryable upstream
connection errors, which confirms the remaining failed generation attempts were
provider/network layer failures rather than a prompt-plan regression.
