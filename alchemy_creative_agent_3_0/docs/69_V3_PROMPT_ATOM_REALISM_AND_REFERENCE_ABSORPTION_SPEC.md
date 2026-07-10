# 69 V3 Prompt Atom Realism And Reference Absorption Spec

Doc93 compatibility note:

```text
Prompt atoms remain reusable guidance. Reference-derived atoms must carry their
source role and allowed channel, and must be dropped when they conflict with a
current prompt-owned channel.
```

Status: accepted optimization document after Doc68.

This document answers the latest audit question:

```text
Has V3 fully absorbed the useful V2 and GPT-Image-2 prompt-case experience?
If not, what is the next compatible implementation pass?
```

## 1. Current Audit

Doc68 has been implemented for its accepted scope:

```text
DONE:
  V3-owned casebook recipe helper exists under visual_cluster.
  Human photorealism consumes casebook fragments.
  Mode-role recipes receive casebook overlays.
  Strong reference closure consumes casebook reference rules.
  E-Commerce recipes reuse the same overlay without losing pack ownership.
  Provider prompts expose compact casebook lines from metadata.
  Focused Doc68 tests and full V3 regression were executed.
  Real portrait and product generation were attempted and produced usable outputs.
```

Remaining gap:

```text
Doc68 absorbs case experience as compact recipes, but it does not yet make the
V2 "prompt atom" method explicit enough.

The outputs improved, but the next quality ceiling is now:
  more real-photo texture,
  less generic AI beauty-face polish,
  stronger camera/light/material grammar,
  stronger product one-reference truth,
  clearer role-specific photo duties,
  and more precise retry signals when these fail.
```

Therefore the next pass is not a new architecture. It is a stricter absorption
layer inside the existing V3 Visual Capability Cluster.

## 2. Compatibility Rule

Doc69 must remain compatible with the current V3 architecture:

```text
V3 Project Mode remains unchanged.
CentralCreativeBrain remains a coordinator.
Scenario Pack and Template contracts remain unchanged.
Visual Capability Cluster remains the owner of reusable visual intelligence.
Doc68 casebook recipes remain the base recipe layer.
Doc69 extends Doc68 with structured prompt atom stacks.
No V1/V2 runtime import is allowed.
No web/runtime case search is introduced.
No duplicate visual framework is introduced.
```

If this document conflicts with older recipe details, use Doc69. If it conflicts
with architecture ownership, use Doc50 and Doc67.

## 3. Reference Experience To Absorb

### 3.1 V2 Lessons

The useful V2 behavior is not the old code itself. The useful pattern is:

```text
1. Prompt directives include reusable prompt atoms.
2. Case/reference grammar is extracted into composition, lighting, color,
   material, lens, and mood cues.
3. Hard user constraints are protected during prompt expansion.
4. Negative prompts are merged as first-class repair pressure.
5. Output review can produce retry patches rather than only a pass/fail label.
```

Doc69 brings this into V3 as static, V3-owned prompt atom stacks.

### 3.2 GPT-Image-2 Casebook Lessons

The external prompt-case evidence is useful because it repeatedly shows:

```text
Portrait:
  explicit camera medium, lens feel, light source, film/CCD grain,
  slight imperfection, skin texture, hair strand detail, fabric wrinkles,
  real environment interaction, and anti-airbrushing negatives.

Character consistency:
  the same person can remain consistent while each frame has a different
  expression, camera distance, gaze, pose, or layout role.

Product:
  one supplied product reference should be treated as product truth;
  silhouette, label/logo placement, proportions, material, and visible text
  shapes must be preserved while concepts, scenes, props, and lighting vary.

Suite direction:
  a set works better when every image has a clear role, such as cover,
  close/detail, angle, context, lifestyle, layout-safe, or format-adapted.

Negative control:
  no watermark, no generated text, no fake logos, no repeated concepts,
  no flat catalog light when a lifestyle scene is requested.
```

Doc69 must turn these into atom stacks and retry signals, not copy prompts.

## 4. New Module Behavior

Doc69 extends the existing file:

```text
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/casebook_recipes.py
```

with a V3-owned prompt atom recipe layer:

```text
VISUAL_PROMPT_ATOM_RECIPE_ID = "visual_prompt_atom_recipe"

prompt atom stack categories:
  camera_stack
  light_stack
  texture_stack
  realism_guard
  reference_guard
  product_truth_guard
  negative_guard
  review_targets
```

This is a child behavior of the existing casebook recipe helper, not a separate
runtime module.

## 5. Portrait Rules

For photoreal human-oriented requests, Doc69 must strengthen:

```text
camera:
  real lens perspective, handheld or shutter-moment variation where useful,
  natural crop differences, non-identical head angle, gaze, and expression.

light:
  believable source direction, soft highlight roll-off, imperfect skin response,
  mild film/CCD grain or lens softness when the style permits.

texture:
  visible skin pores, non-uniform cheek texture, under-eye detail, hair strands,
  flyaways, fabric wrinkles, clothing drape, and environmental contact.

realism guard:
  professional but not plastic; polished but not porcelain; no generic
  AI-influencer face; no repeated template smile.

identity guard:
  keep broad face shape, age direction, body type, hair family, and feature
  relationships while allowing expression, pose, crop, camera, and small
  hair-styling variation.
```

## 6. Product Rules

For product/object-oriented requests, Doc69 must strengthen:

```text
product truth:
  when a reference exists, it is the one product truth.
  Preserve silhouette, proportions, material, edge shape, label/logo placement,
  and visible text shapes. Do not translate, rewrite, invent, blur, cover,
  crop, darken, or replace the label/logo.

commercial variation:
  vary scene role, camera distance, surface, prop language, environment depth,
  lifestyle/use cue, and lighting according to the selected mode and role.

anti-flatness:
  lifestyle/context roles must not collapse back into studio-only packshots.
  Product detail roles must show inspectable material/edge/label detail.
```

## 7. Four Mode Integration

Doc69 must preserve the four General Template modes:

```text
selection_candidates:
  small, comparable differences; same visual family; useful alternative picks.

delivery_suite:
  role-separated set; cover, closer detail, angle/context, and layout duties.

creative_exploration:
  stronger concept variation while preserving identity/product truth.

format_layout_adaptation:
  crop, safe area, subject scale, and negative-space adaptation.
```

The prompt atom layer must make each mode more precise without inventing a fifth
mode.

## 8. Provider Prompt Contract

Provider prompt generation must consume atom stacks only through role-recipe
metadata:

```text
Prompt atom camera stack: ...
Prompt atom light/texture stack: ...
Prompt atom reference guard: ...
Prompt atom negative guard: ...
Prompt atom review target: ...
```

Provider code must not own the strategy. It only renders the already-prepared
metadata into compact instructions.

## 9. Real Review And Retry Signals

Doc69 adds or verifies precise issue codes for:

```text
over_retouching
poreless_beauty_surface
synthetic_fashion_face
weak_photographic_imperfection
flat_catalog_lighting
weak_lifestyle_context
repeated_concept_or_prop
reference_guard_ignored
```

These issue codes should map to retry patches:

```text
portrait realism repair:
  add natural skin/hair/fabric/lens imperfections;
  remove AI beauty-face pressure;
  keep identity through stable traits, not cloned stills.

product realism repair:
  preserve product truth from reference;
  increase real-use context for lifestyle roles;
  avoid flat studio-only repetition when not requested.

suite direction repair:
  strengthen role separation and remove repeated concept/prop collapse.
```

Doc53 retry-budget safety still wins. Doc69 must not create unbounded loops.

## 10. Tests Required

Add or update tests to prove:

```text
1. Doc69 code is V3-owned and has no V1/V2 runtime imports.
2. Portrait role recipes contain camera/light/texture atom stacks.
3. Product/ecommerce role recipes contain one-reference product truth guards.
4. Provider prompt renders atom stack lines from metadata only.
5. General non-product prompts do not receive product-truth language.
6. Vision inspection accepts the new issue codes and creates retry patches.
7. Focused Doc68 tests still pass.
8. Full V3 regression still passes.
```

## 11. Real Validation Required

After implementation, run:

```text
1. A portrait suite using the earlier East Asian summer cool portrait task.
2. A product suite with a real product/commercial-use request.
3. Compare against the immediately previous Doc68 outputs.
```

Expected improvement:

```text
portrait:
  less AI-beauty polish, more real-photo skin/hair/fabric/camera imperfection,
  preserved identity with more natural variation.

product:
  stronger product truth, more role-specific scene duties, fewer flat packshots
  where lifestyle/context was requested.

overall:
  closer to Lovart-style commercial direction, but still explicitly dependent
  on provider image quality and available reference fidelity.
```

## 12. Completion Standard

Doc69 is complete only when:

```text
docs updated;
casebook atom stacks implemented inside visual_cluster;
provider prompt consumes atom stacks through metadata;
review/retry issue codes and patches are updated;
focused tests pass;
full V3 tests pass;
compileall passes;
diff check passes;
real portrait and product generation are attempted;
quality is evaluated against Doc68.
```
