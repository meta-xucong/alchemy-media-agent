# 69A V3 Reference Experience Absorption Audit

Status: auxiliary audit for Doc69.

This document records what was learned from earlier V2 code/documents and from
public GPT-Image-2 prompt-case references, and where each lesson belongs in V3.

## 1. Absorption Principle

```text
Do not copy old systems.
Do not call V1/V2 at runtime.
Do not add a second visual framework.
Do extract the reusable method and fold it into V3 visual_cluster modules.
```

## 2. V2 Experience Map

| V2 pattern | Useful lesson | V3 owner after Doc69 |
| --- | --- | --- |
| reusable_prompt_atoms | Quality improves when prompt cues are reusable units, not prose blobs. | `visual_cluster/casebook_recipes.py` |
| prompt_directives | Camera, light, material, mood, layout, negative constraints need separate fields. | prompt atom metadata on mode role recipes |
| prompt guard | User hard constraints must not be weakened by prompt beautification. | existing Brain + prompt compiler guard, reinforced by atom layer wording |
| visual_grammar_lock | Composition, lighting, palette, lens, and texture should be reused as grammar, not copied as subject content. | visual grammar modules + prompt atom stacks |
| visual_review_agent | Review should output retry patches. | `vision_inspector.py` and retry packages |

## 3. Public GPT-Image-2 Casebook Map

The public casebook repeatedly demonstrates these prompt patterns:

```text
portrait:
  camera medium + light source + film/CCD texture + facial micro-detail
  + clothing/hair imperfections + anti-airbrushing negative prompt.

same-person grids:
  identity consistency is achieved by stable traits;
  natural variation happens through expression, pose, gaze, crop, angle, scene.

product campaigns:
  the uploaded product reference is the one product truth;
  preserve shape, proportion, material, label/logo placement;
  vary concept, surface, props, use context, and scene role.

suite/storyboard prompts:
  stronger results come from declaring each image duty.
```

Doc69 absorbs these as atom categories, not as copied prompt text.

## 4. What Was Already Absorbed Before Doc69

```text
Doc50:
  created the V3-native Visual Capability Cluster boundary.

Doc51-58:
  added visual consistency, identity/product locks, selected outputs, and
  project context reuse.

Doc59-60:
  added four modes, role plans, and E-Commerce slot roles.

Doc64-66:
  added commercial quality review, human photorealism, selected-reference
  closure, real-review signals, and candidate-scoped retry.

Doc67:
  cleaned up boundary drift so child modules own visual logic.

Doc68:
  introduced static V3 casebook recipe fragments.
```

## 5. What Was Not Fully Absorbed Before Doc69

```text
1. Prompt atoms were present as recipe fragments but not explicit stacks.
2. Provider prompt lines did not expose camera/light/texture/reference stacks.
3. Portrait realism lacked a stronger anti-AI editorial-polish vocabulary.
4. Product truth existed, but the "one product reference" casebook rule needed
   stronger prompt pressure.
5. Review/retry codes did not name over-retouching, weak photographic
   imperfection, flat catalog lighting, or reference guard failure precisely.
```

## 6. Doc69 Implementation Mapping

| Gap | Implementation |
| --- | --- |
| prompt atom stacks | add prompt atom recipe metadata inside `casebook_recipes.py` |
| provider exposure | extend `provider_casebook_prompt_lines()` |
| portrait AI feel | strengthen `human_photorealism_casebook()` and role overlays |
| product truth | strengthen product atom guard and E-Commerce recipe overlays |
| retry precision | extend `vision_inspector.py` and `vision_provider.py` issue code contract |

## 7. Non-Duplication Check

Doc69 must not create:

```text
new central brain strategy code;
new template system;
new scenario registry;
new runtime case retriever;
new V1/V2 adapter;
new provider-specific prompt engine.
```

Doc69 may create:

```text
helper functions under casebook_recipes.py;
new constants exported by visual_cluster;
new tests proving the prompt atom layer is consumed through existing contracts.
```

## 8. Quality Target

Doc69 should improve commercial quality through more disciplined visual grammar:

```text
human:
  same person, less cloned still, less AI-face polish, more real-camera texture.

product:
  same object, stronger material and label truth, more useful role variation.

suite:
  each image has a purpose that a non-technical user can understand after
  generation, while internal prompt logic remains hidden from the main UI.
```
