# 68B V3 Four-Mode Recipe Matrix

Status: auxiliary reference for Doc68.

This document defines how Doc68 casebook recipes must behave under the four
General Template modes.

## 1. Mode Matrix

```text
selection_candidates
  user meaning:
    I want several close options and will pick one.
  visual distance:
    micro.
  portrait behavior:
    same person, same shoot, small expression/gaze/pose/crop differences.
  product behavior:
    same product setup, small angle/surface/lighting/crop differences.
  retry tolerance:
    do not punish similarity; punish cloned stills, artifacts, or drift.

delivery_suite
  user meaning:
    I want a useful set under one direction.
  visual distance:
    moderate.
  portrait behavior:
    cover hero, closer subject, angle variation, wider context.
  product behavior:
    hero object, context/lifestyle, detail/material, layout-safe cover.
  retry tolerance:
    punish role collapse and over-cloned batches.

creative_exploration
  user meaning:
    I want different ideas before choosing one.
  visual distance:
    broad but controlled.
  portrait behavior:
    different mood, styling, scene, or lens while preserving person direction.
  product behavior:
    different art direction, location, prop language, palette, or light.
  retry tolerance:
    punish random drift; do not punish meaningful creative distance.

format_layout_adaptation
  user meaning:
    I want the same idea adapted to different uses.
  visual distance:
    layout-only.
  portrait behavior:
    same person and styling; crop, safe area, and aspect ratio change.
  product behavior:
    same product and idea; crop/layout/negative space changes.
  retry tolerance:
    punish identity/product drift and bad crop; do not punish repeated styling.
```

## 2. Portrait Recipe Matrix

### Similar Candidates

```text
candidate_best_frame:
  keep same scene and identity; adjust micro-expression or tiny crop.

candidate_expression_shift:
  vary gaze or smile intensity without changing face identity.

candidate_pose_shift:
  vary hand placement or shoulder line.

candidate_crop_shift:
  vary camera distance or blank space.
```

### Delivery Suite

```text
cover_hero:
  direct or near-camera gaze, clear hero posture, cover-safe crop.

subject_focus:
  closer crop, hair/skin detail, softer expression, shallow depth.

side_or_three_quarter_angle:
  different face plane, body turn, gaze away or toward the scene.

wide_scene_or_context:
  wider body scale, lifestyle action, environmental depth.
```

### Creative Exploration

```text
clean_bright:
  fresh accessible visual language.

editorial:
  fashion/editorial treatment and stronger styling.

cinematic:
  stronger depth, atmosphere, lens, and light.

minimal_graphic:
  shape, negative space, and layout rhythm.
```

### Format Layout Adaptation

```text
vertical_cover:
  portrait-safe top/bottom margins.

square_feed:
  balanced crop and central readability.

horizontal_banner:
  side negative space without identity drift.

tight_crop:
  close crop that keeps face natural and readable.
```

## 3. Product Recipe Matrix

### Similar Candidates

```text
candidate_best_frame:
  same product and setup, small crop or angle difference.

candidate_light_shift:
  same product truth, slightly changed shadow/highlight.

candidate_surface_shift:
  same product, small surface or prop rhythm difference.

candidate_crop_shift:
  same setup, different subject scale or negative space.
```

### Delivery Suite

```text
hero_object:
  clear silhouette and premium product truth.

context_scene:
  real environment, natural surface, hand/use cue or lived-in context.

detail_or_material_closeup:
  material, label area, edge, texture, condensation, functional detail.

layout_safe_cover:
  strong crop with usable blank space for later UI copy.
```

### Creative Exploration

```text
studio_premium:
  refined commercial studio direction.

lifestyle_real:
  lived-in or outdoor context, natural use moment.

editorial_bold:
  stronger art direction and campaign style.

minimal_graphic:
  clean shape and layout emphasis.
```

### Format Layout Adaptation

```text
vertical_listing:
  tall product-readable crop.

square_thumbnail:
  marketplace/feed-readable center crop.

horizontal_banner:
  side negative space, product identity clear.

detail_crop:
  close crop without losing product truth.
```

## 4. Provider Prompt Rules

Every provider prompt should receive:

```text
one role instruction
one mode distance instruction
one identity/product preservation instruction
one variation instruction
one artifact/text/watermark restriction
```

Avoid:

```text
stacking many generic adjectives
contradicting strong reference closure
using product words in pure portrait/general tasks
making every output in a batch share the same pose/crop
```

