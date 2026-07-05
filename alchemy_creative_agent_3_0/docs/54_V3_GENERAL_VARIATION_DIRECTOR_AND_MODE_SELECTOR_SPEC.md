# 54 V3 General Variation Director And Mode Selector Spec

## 1. Status And Authority

This document defines how the General Template should decide what kind of
multi-image continuation to generate.

It refines the "SuiteVariationDirector" wording from document `52` for the
General Template.

Authority chain:

```text
Doc47:
  Owns the single beginner-facing production entry.

Doc52:
  Defines the broader post-generation review, retry, suite direction, and
  curation target.

Doc54:
  Owns the General Template variation-mode model:
    similar candidates
    delivery suite
    creative exploration
    format/layout adaptation
```

When there is a conflict about General Template continuation behavior, Doc54
wins over generic "suite" wording in older documents.

Doc54 does not unfreeze E-Commerce Template and does not define ecommerce
business image slots.

Current human-series authority:

```text
Document 56 extends Doc54 for portrait/model/person-led image sets. When a
General Template variation mode is used for humans, the mode must preserve the
same recognizable person and body direction while allowing natural commercial
variation in expression, gaze, pose, head angle, camera angle, crop, and small
hair styling details. "Similar candidates" must not mean cloned stills.

Document 58 extends Doc54 for the next implementation phase. It defines how the
four General Template modes produce concrete suite roles, how selected outputs
become strong project references, and how batch review detects both identity
drift and over-cloned repetition. Doc54 remains the mode taxonomy; Doc58 is the
identity-anchor and strong-reference execution plan.

Document 59 extends Doc54 and Doc58 after real generation validation. It is the
authority for making the four modes functionally different in actual execution:
mode-specific role recipes, role-specific prompts, role-collapse review,
mode-specific retry patches, and beginner-facing mode summaries. Doc54 still
owns the mode names and user meaning.
```

## 2. Core Product Decision

The General Template must not hard-code business suite slots such as:

```text
main image
white background image
detail image
lifestyle scene image
comparison image
package image
```

Those belong to specialized templates such as E-Commerce, Photographer, New
Media, and Brand IP.

The General Template owns a more universal concept:

```text
Variation Director:
  Decide whether the user wants similar alternatives, a visual delivery set,
  creative directions, or layout/size adaptations.
```

General Template continuation is therefore:

```text
same project context
same selected references when available
same visual grammar unless exploration is requested
different outputs according to a selected variation mode
```

## 3. Variation Modes

The General Template supports four modes.

### 3.0 Frontend Mode Selector Contract

The Project Workspace must expose the four General Template variation modes in
the production composer. This control replaces generic "image purpose" wording
for the General Template.

Beginner-facing control:

```text
生成方式
默认：智能选择
手动可选：
  1. 相似备选模式
  2. 套图扩展模式
  3. 创意探索模式
  4. 尺寸/版式适配模式
```

Behavior:

```text
智能选择:
  UI sends variation_mode = "auto"
  UI may also send inferred_variation_mode for audit/debug
  central brain remains allowed to choose the final mode from the prompt

manual selection:
  UI sends variation_mode as the selected internal id
  UI sends variation_mode_source = "manual"
  central brain and prompt assembly must respect this user choice unless safety blocks it
```

The selector must be small, clear, and beginner-facing. It must not be hidden
inside engineering controls, and it must not be labeled as "preset", "provider",
"scenario mode", or "prompt compiler".

### 3.1 Similar Candidate Mode

Internal id:

```text
selection_candidates
```

User meaning:

```text
Give me several similar options so I can pick the best one.
```

Typical prompts:

```text
same person, different poses
give me a few similar options
same style, slight changes
generate several alternatives to choose from
same product, different angles
similar composition, small differences
```

Portrait rules:

```text
lock:
  subject identity direction when a selected/uploaded reference exists
  hairstyle direction
  outfit category
  lighting language
  background atmosphere
  camera/lens language

allow:
  pose
  expression
  face angle
  hand placement
  crop
  tiny background position changes

forbid:
  face swap
  major hairstyle change
  major wardrobe category change
  age drift
  ethnicity drift
  unrelated objects
  visible text or watermark
```

Product/object rules:

```text
lock:
  product/object identity when a selected/uploaded reference exists
  color
  shape
  material
  proportion
  key structure

allow:
  camera angle
  placement
  light direction
  crop
  minimal prop or background variation

forbid:
  replacing the product/object
  changing material family
  changing core color
  adding random labels
  visible text or watermark
```

Important limitation:

```text
If the user has not uploaded or selected a reference image, V3 can keep a
similar archetype and style, but cannot guarantee exact same identity.
```

Beginner-facing wording:

```text
多给几个相似备选
```

### 3.2 Delivery Suite Mode

Internal id:

```text
delivery_suite
```

User meaning:

```text
Make a useful set under the same visual direction.
```

Typical prompts:

```text
make a set
generate a series
create a group of images
make several useful images for this project
extend this into a visual set
```

Universal General Template slots:

```text
hero_key_visual
close_subject_or_detail
atmosphere_wide
clean_space_cover
alternate_crop
```

Slot selection should be count-aware:

```text
1 image:
  hero_key_visual

2 images:
  hero_key_visual
  close_subject_or_detail

3 images:
  hero_key_visual
  close_subject_or_detail
  atmosphere_wide

4 images:
  hero_key_visual
  close_subject_or_detail
  atmosphere_wide
  clean_space_cover
```

Beginner-facing wording:

```text
沿这个风格做一组图
```

### 3.3 Creative Exploration Mode

Internal id:

```text
creative_exploration
```

User meaning:

```text
Show me different creative directions.
```

Typical prompts:

```text
try different styles
give me several directions
explore a few concepts
make it more creative
show different moods
```

Rules:

```text
lock:
  user core subject
  project constraints
  safety and no-text constraints

allow:
  palette
  mood
  composition
  background
  lens language
  art direction

forbid:
  losing the core subject
  violating selected hard references
  changing confirmed brand/product truth
  visible text or watermark
```

Creative exploration should not be used when the user says:

```text
same person
same product
similar options
only slightly different
```

Beginner-facing wording:

```text
换几个新方向看看
```

### 3.4 Format And Layout Adaptation Mode

Internal id:

```text
format_adaptation
```

User meaning:

```text
Keep the idea, adapt it to another size, crop, or layout.
```

Typical prompts:

```text
make a vertical version
make a horizontal version
adapt for cover
leave blank space for text
make a square version
change the layout
```

Rules:

```text
lock:
  subject
  style
  color and lighting
  selected references
  main visual idea

allow:
  crop
  negative space
  subject position
  aspect ratio
  layout balance

forbid:
  changing the visual concept
  changing identity/product
  adding generated text
```

Beginner-facing wording:

```text
调整尺寸和版式
```

## 4. Auto Detection And Manual Override

The default behavior is automatic.

Frontend must expose:

```text
自动判断
多给几个相似备选
沿这个风格做一组图
换几个新方向看看
调整尺寸和版式
```

Default selected option:

```text
自动判断
```

Manual click behavior:

```text
If the user selects a mode manually, manual selection wins over prompt
inference for this generation job.
```

Mode source values:

```text
auto
manual
project_default
template_default
```

Metadata contract:

```python
variation_mode: str | None
variation_mode_source: str = "auto"
variation_mode_override: str | None = None
variation_intensity: str = "micro"  # micro | moderate | broad
```

Manual frontend selection should send:

```json
{
  "variation_mode_override": "selection_candidates",
  "variation_mode_source": "manual"
}
```

Auto detection should set:

```json
{
  "variation_mode": "selection_candidates",
  "variation_mode_source": "auto"
}
```

## 5. Detection Rules

Priority:

```text
1. manual frontend override
2. explicit user prompt
3. project context and selected references
4. requested count/aspect ratio
5. General Template default
```

Prompt keyword examples:

```text
selection_candidates:
  similar, alternatives, choose, pick one, same person, same product,
  different poses, slight change, a few options, 几个备选, 挑一张,
  同一个人, 不同姿势, 稍微变化, 类似几张

delivery_suite:
  set, series, group, suite, visual set, 一组, 套图, 系列, 成套,
  多张用于不同场景

creative_exploration:
  different directions, explore, various styles, try concepts,
  不同风格, 多个方向, 创意探索, 换几个方向

format_adaptation:
  vertical, horizontal, square, crop, layout, cover, blank space,
  竖版, 横版, 方图, 封面, 留白, 版式, 尺寸
```

Default fallback:

```text
If requested_image_count <= 1:
  no variation plan is required

If requested_image_count > 1 and no explicit intent exists:
  selection_candidates
```

Reason:

```text
When beginners ask for several images without more detail, they usually want
several good choices, not a complex delivery suite.
```

## 6. Data Contracts

### 6.1 GeneralVariationPlan

```python
class GeneralVariationPlan(V3BaseModel):
    plan_id: str
    project_id: str | None = None
    job_id: str | None = None
    template_id: str = "general_creative"
    mode: str
    mode_source: str = "auto"
    confidence: float = 0.0
    requested_count: int = 1
    variation_intensity: str = "micro"
    aspect_ratios: list[str] = []
    slots: list[dict[str, Any]] = []
    locked_elements: list[str] = []
    allowed_changes: list[str] = []
    forbidden_changes: list[str] = []
    reference_requirements: list[str] = []
    user_visible_summary: list[str] = []
    metadata: dict[str, Any] = {}
```

### 6.2 VariationSlot

```python
class VariationSlot(V3BaseModel):
    slot_id: str
    slot_type: str
    user_visible_label: str
    purpose: str
    composition_goal: str
    lock_rules: list[str] = []
    allowed_changes: list[str] = []
    forbidden_changes: list[str] = []
    aspect_ratio: str | None = None
    metadata: dict[str, Any] = {}
```

Slot examples for `selection_candidates`:

```text
similar_pose_variant
similar_expression_variant
similar_crop_variant
similar_angle_variant
```

Slot examples for `delivery_suite`:

```text
hero_key_visual
close_subject_or_detail
atmosphere_wide
clean_space_cover
alternate_crop
```

Slot examples for `creative_exploration`:

```text
fresh_direction
mood_shift
palette_shift
composition_shift
```

Slot examples for `format_adaptation`:

```text
square_crop
vertical_cover
horizontal_cover
clean_space_layout
```

## 7. Backend Ownership

### 7.1 Visual Capability Cluster

Owns:

```text
reference locks
identity/product/style constraints
visual grammar reuse
allowed/forbidden changes
```

### 7.2 General Variation Director

Suggested location:

```text
app/shared_capabilities/visual_cluster/general_variation_director.py
```

Owns:

```text
mode inference
slot planning
variation intensity
plain-language summary
```

### 7.3 Product API / Project Mode

Owns:

```text
receive frontend manual override
store selected variation mode in job metadata
return plan summary in ProductJobStatus / Project timeline
```

### 7.4 CentralCreativeBrain

Consumes:

```text
GeneralVariationPlan
selected references
VisualIdentityLockProfile
ProjectVisualGrammarSnapshot
```

Does not own:

```text
variation mode taxonomy
front-end selector state
business template slot definitions
```

## 8. Frontend UX

Where to show it:

```text
V3 project production drawer / generation modal
Continue this project modal
```

Control:

```text
segmented control or compact radio group
```

Default:

```text
自动判断
```

Options:

```text
多给几个相似备选
沿这个风格做一组图
换几个新方向看看
调整尺寸和版式
```

Do not show:

```text
selection_candidates
delivery_suite
creative_exploration
format_adaptation
VariationDirector
slot taxonomy
provider strategy
```

Beginner-facing one-line explanations:

```text
自动判断:
  V3 会根据你的描述决定生成方式。

多给几个相似备选:
  同风格小幅变化，方便挑一张最满意的。

沿这个风格做一组图:
  同一方向下生成几张用途不同的图。

换几个新方向看看:
  多试几种风格和画面方向。

调整尺寸和版式:
  保持画面感觉，换构图、留白或横竖版。
```

Mobile:

```text
Use a compact selector or bottom sheet.
Do not wrap five options into cramped tiny buttons.
```

## 9. Relationship With Specialized Templates

Specialized templates may reuse the mode selector pattern but own their own
slot registry.

```text
General Template:
  universal visual variation slots

E-Commerce Template:
  product main image, white background, detail, lifestyle, packaging,
  comparison, marketplace-specific slots

Photographer Template:
  full body, half body, close-up, profile, environment, editorial crop

New Media Template:
  cover, article illustration, title-safe layout, thumbnail, vertical story

Brand IP Template:
  character sheet, expression sheet, pose sheet, scene key visual, social avatar
```

General Template must not borrow ecommerce slots unless the user explicitly
selects the E-Commerce Template after it is unfrozen.

## 10. Implementation Phases

### Phase 1 - Documentation

1. Add Doc54.
2. Update Doc52 to point General Template suite behavior to Doc54.

### Phase 2 - Contracts

1. Add `GeneralVariationPlan`.
2. Add `VariationSlot`.
3. Add public metadata fields:

```text
variation_mode
variation_mode_source
variation_mode_override
variation_intensity
general_variation_plan
```

### Phase 3 - Backend Inference

1. Implement deterministic keyword/rule fallback.
2. Allow LLM Brain to propose mode, but fallback must work without remote LLM.
3. Manual override must win.
4. Store mode source.

### Phase 4 - Generation Consumption

1. SeriesPlanner should use requested count and variation mode.
2. PromptCompiler should add slot-specific guidance.
3. Provider prompt should receive slot purpose and lock rules.
4. Selected references should be applied according to mode.

### Phase 5 - Frontend

1. Add `自动判断` plus four user-facing options.
2. Save manual override into generation metadata.
3. Show one short explanation line.
4. Keep default UI image-first and beginner-friendly.

### Phase 6 - Tests

Add tests for:

```text
manual mode override wins over prompt inference
"different poses" auto-detects selection_candidates
"make a set" auto-detects delivery_suite
"different styles" auto-detects creative_exploration
"vertical cover" auto-detects format_adaptation
requested_count > 1 with no explicit clue defaults to selection_candidates
selection_candidates with no reference emits soft identity limitation metadata
selection_candidates with selected reference uses hard/strong reference rules
General Template does not emit ecommerce slots
frontend payload sends variation_mode_override
UI labels contain no engineering ids
```

## 11. Acceptance Criteria

```text
General Template no longer treats every multi-image request as a business suite.
Default frontend state is automatic mode detection.
User can manually choose the four modes.
Similar candidate mode supports same-person/same-product small variations.
Delivery suite mode supports universal non-business visual slots.
Creative exploration mode supports broader direction changes.
Format adaptation mode supports crop/size/layout changes.
Manual mode selection wins over auto inference.
Specialized templates remain free to define their own business slots.
E-Commerce Template remains frozen until intentionally unfrozen.
No engineering terms appear in beginner UI.
Tests prove detection, override, and slot planning behavior.
```
