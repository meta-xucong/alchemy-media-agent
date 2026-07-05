# 59 V3 Mode-Aware Role Director And Suite Differentiation Spec

## 1. Status And Authority

This document is the next development authority after document `58`.

It does not replace the existing V3 architecture. It refines the last observed
gap from real GPT image 2 validation:

```text
Doc58 made selected images stronger anchors and added suite roles.
Real outputs became more consistent, but the roles still collapsed into
similar near-portrait or similar product-scene variants.

The next step is not "more suite wording".
The next step is mode-aware execution:
  each of the four General Template modes must create different plans,
  different role recipes,
  different prompt pressure,
  different review criteria,
  and different beginner-facing summaries.
```

Authority chain:

```text
Doc32-47:
  Own Project Mode, beginner UX, template-first project creation, one
  production entry, selected outputs, and folded workflow artifacts.

Doc50:
  Owns the V3-native Visual Capability Cluster as the home of reusable visual
  enhancement.

Doc54:
  Owns the four General Template variation modes:
    similar candidates
    delivery suite
    creative exploration
    format/layout adaptation

Doc55:
  Owns real post-generation image inspection.

Doc56:
  Owns same-person consistency with natural variation.

Doc57:
  Owns E-Commerce lifestyle/count/watermark QA.

Doc58:
  Owns identity anchors, strong selected-output continuation, and the first
  General Suite Director role layer.

Doc59:
  Owns mode-aware role differentiation:
    each mode must behave differently in planning, prompt assembly, review,
    retry, and UI summaries.
```

If documents conflict:

```text
Doc54 still wins for the names and meaning of the four modes.
Doc58 still wins for selected-output anchors and strong reference continuation.
Doc59 wins for how role recipes are selected, separated, prompted, reviewed,
and retried inside each mode.
Doc57 wins for E-Commerce business slot definitions such as main image,
lifestyle scene, and detail image. Doc59 may provide shared role-separation
machinery, but it must not replace E-Commerce slot semantics.
Doc60 wins for E-Commerce product-suite slot fidelity: actual Scenario Pack
recipes are the source of truth for product-suite role keys, and Doc59 role
pressure may enrich but must not replace those slots.
Doc61 wins only for portrait validation and Lovart benchmark acceptance
wording. It does not change Doc59's role director mechanics.
Doc62 extends Doc59 for General Template portrait delivery-suite roles only:
it adds stronger role-specific expression, gaze, pose, subject-scale, crop,
and scene-depth lanes while keeping Doc59 role planning and Doc60 E-Commerce
slot contracts intact.
```

This document does not:

```text
rewrite Project Mode
rewrite Product API
replace ScenarioRuntime or Scenario Packs
move visual enhancement into the central brain
call V1/V2 runtime code
add Claude Code expert/provider mode
turn the frontend into a developer console
make exact real-person identity claims without suitable reference/provider support
```

## 2. Problem Found In Real Validation

The Doc58 real validation showed:

```text
Portrait:
  strong reference worked
  identity, green-highlight hair, outfit, lighting, and clean style were stable
  but continuation outputs stayed too close to one near-portrait family
  cover / side angle / wide scene roles were present in metadata but not strong
  enough in actual generated composition

E-Commerce:
  product form, mint color, ice, mint leaves, and clean summer mood were stable
  lifestyle realism improved
  but main / lifestyle / detail duties were still visually close
```

Root cause:

```text
The current role plan is mostly advisory.
The model receives a broad suite instruction, but each output does not receive
a sufficiently role-specific generation contract.
```

Doc59 fixes this by making every generated image carry a role recipe with:

```text
role goal
shot family
camera distance
angle/crop rule
scene-change allowance
must-keep rules
must-change rules
forbidden collapse rules
review criteria
retry patch strategy
beginner-facing label
```

## 3. Core Product Target

V3 should move from:

```text
same subject, similar good-looking variants
```

to:

```text
mode-specific output behavior

Similar Candidates:
  close alternatives for choosing the best frame

Suite Expansion:
  a purposeful set where each image has a useful role

Creative Exploration:
  several different art directions while keeping the project core

Format/Layout Adaptation:
  the same approved direction adapted to different crops or canvases
```

The beginner-facing promise:

```text
Choose how you want V3 to continue:
  close options,
  a useful set,
  new creative directions,
  or different sizes and layouts.

V3 will use the mode to decide what each image should do.
```

## 4. Architecture Decision

### 4.1 Keep the implementation inside the V3 Visual Capability Cluster

Add or extend modules under:

```text
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/
```

Target ownership:

```text
mode_role_director.py
  owns mode-specific execution policy and role recipes

general_suite_director.py
  may delegate role selection to mode_role_director

batch_identity_review.py
  extends review to mode-specific role coverage and role collapse

strong_reference_loop.py
  remains responsible for selected-output anchor usage
```

Do not put these rules directly into:

```text
CentralCreativeBrain as hard-coded branches
Product API as prompt strings
frontend JavaScript as business logic
provider adapters as mode detection
```

The central brain may consume the structured policy and translate it into
creative language. It should not own the policy.

### 4.2 Make the role plan executable, not decorative

The current role plan must become a role-specific generation contract.

Every requested output must know:

```text
which mode it belongs to
which role it serves
what it must keep
what it must visibly change
what it must not become
what review will judge it against
```

The plan must be threaded through:

```text
ProjectContextPackage
VisualCapabilityClusterResult
LLM Brain result
SeriesPlanner assets
LayoutPlan
PromptCompilationResult
GenerationRequest metadata
Provider final prompt metadata
Post-generation review package
Project timeline / folded workflow summary
```

### 4.3 Keep E-Commerce compatible but not overridden

Doc59 can provide the reusable machinery:

```text
role-specific generation
role-separation review
role-collapse retry patches
mode-aware beginner summaries
```

But E-Commerce keeps its specialized slot source:

```text
main_image
scenario_image
detail_image
trust_image
ad_cover
store_banner
```

When the active template is E-Commerce:

```text
Doc57/E-Commerce slot planner chooses the business slots.
Doc59 enforces that each slot becomes a distinct role-specific generation
contract and that post-generation review checks slot separation.
Doc60 further clarifies that E-Commerce role count follows actual listing
recipes and requested slots; it is not truncated to the General Template
four-role cap.
```

When the active template is General Template:

```text
Doc59 chooses universal General roles from the selected mode.
```

## 5. Four Mode Execution Policies

### 5.1 Similar Candidates Mode

Internal id:

```text
selection_candidates
```

Product meaning:

```text
Give close options so the user can pick the best one.
```

This mode is for:

```text
same person, different poses
same product, slightly different angle
same style, several alternatives
choose one best frame
minor expression or crop shifts
```

This mode is not for:

```text
full campaign suites
large scene changes
different creative concepts
multiple aspect ratios
```

Execution policy:

```text
visual_distance_budget: micro
anchor_strength: strongest available anchor
scene_change_allowed: false by default
role_strategy: near-neighbor candidates
role_difference_requirement: exactly one or two visible axes per output
review_priority: same identity/product, not identical stills
```

Default roles:

```text
candidate_best_frame
  closest to the approved direction

candidate_expression_shift
  same shot family, different expression or gaze

candidate_pose_shift
  same scene and style, different pose or hand position

candidate_crop_shift
  same scene and subject, slight crop or camera distance change
```

Human prompt pressure:

```text
Keep the same recognizable person, body type, hair direction, outfit category,
lighting, and scene family. Vary only a small presentation detail such as
expression, gaze, pose, head angle, hand placement, or crop. Do not create a
new concept or a different location.
```

Product/object prompt pressure:

```text
Keep the same product/object shape, color, material, proportions, label
position, lighting family, and scene family. Vary only camera angle, placement,
light direction, crop, or minor prop placement.
```

Review criteria:

```text
pass:
  outputs are close enough to compare as choices
  at least one visible small difference exists

retry:
  outputs look like different people/products
  outputs are exact cloned stills
  scene changed so much the user cannot compare options

do not retry:
  differences are acceptable but subjective
```

Beginner UI wording:

```text
Close options
Use this when you want several similar choices and will pick the best one.
```

### 5.2 Suite Expansion Mode

Internal id:

```text
delivery_suite
```

Product meaning:

```text
Make a useful set under the same approved direction.
```

This mode is for:

```text
one set
series
cover plus detail
same model with different camera distances
same product in main/lifestyle/detail roles
social media set under one style
```

This mode is not for:

```text
only picking one best frame
unrelated creative directions
pure size adaptation
```

Execution policy:

```text
visual_distance_budget: moderate
anchor_strength: strong for selected human/product anchors
scene_change_allowed: true when role requires it
role_strategy: purposeful delivery roles
role_difference_requirement: different shot family or different image duty
review_priority: role coverage and project consistency
```

General Template human roles by count:

```text
1:
  cover_hero

2:
  cover_hero
  subject_focus

3:
  cover_hero
  side_or_three_quarter_angle
  wide_scene_or_context

4:
  cover_hero
  subject_focus
  side_or_three_quarter_angle
  wide_scene_or_context
```

General Template object/product-like roles by count:

```text
1:
  hero_object

2:
  hero_object
  context_scene

3:
  hero_object
  context_scene
  detail_or_material_closeup

4:
  hero_object
  context_scene
  detail_or_material_closeup
  layout_safe_cover
```

E-Commerce mapping:

```text
1:
  main_image

2:
  main_image
  scenario_image

3:
  main_image
  scenario_image
  detail_image

4:
  main_image
  scenario_image
  detail_image
  trust_or_ad_cover
```

Human prompt pressure:

```text
Each output must be one complete image with a different duty in the same shoot:
cover hero, side/three-quarter angle, wide context, or detail/mood. Preserve
the same recognizable person, body type, hair direction, outfit category, and
lighting language, but visibly change camera distance, angle, pose, scene role,
or crop according to the role.
```

Product prompt pressure:

```text
Each output must serve a different commercial image duty: product-first hero,
realistic context scene, detail/material closeup, or layout-safe cover. Preserve
the product shape, color, material, proportions, and label position while
changing surface, scene, camera distance, crop, or supporting props according
to the role.
```

Review criteria:

```text
pass:
  roles are visible in the images
  outputs feel like one project set
  no image is a clone of another role

retry:
  all outputs share the same crop and camera distance
  wide/context role is still a near portrait or near product packshot
  detail role is not closer or more detailed than hero role
  product/person identity drifts
```

Beginner UI wording:

```text
Make a set
Use this when you want several images with different useful jobs.
```

### 5.3 Creative Exploration Mode

Internal id:

```text
creative_exploration
```

Product meaning:

```text
Explore several art directions before deciding what to keep.
```

This mode is for:

```text
try different styles
different moods
different visual concepts
show several directions
explore before locking a direction
```

This mode is not for:

```text
strict same-person continuity unless the user also locks the selected reference
commercial slot delivery
small candidate differences
format-only changes
```

Execution policy:

```text
visual_distance_budget: broad
anchor_strength: medium by default, strong only when user selected/locked anchor
scene_change_allowed: true
role_strategy: concept lanes
role_difference_requirement: different concept, mood, palette, scene, or lens
review_priority: keep core subject while avoiding random unrelated outputs
```

Default roles:

```text
concept_clean_bright
  clean, approachable, high-clarity direction

concept_editorial
  more styled, magazine-like, stronger art direction

concept_cinematic
  stronger atmosphere, more dramatic light or scene depth

concept_minimal_or_graphic
  simpler composition, stronger shape/layout language
```

Prompt pressure:

```text
Explore distinct visual directions while preserving the user core subject and
hard project constraints. Each output should feel like a different possible
direction, not a small variation of the same frame. Do not lose selected hard
references, product truth, or user-forbidden items.
```

Review criteria:

```text
pass:
  outputs are meaningfully different concepts
  core subject remains recognizable
  no output violates hard selected references

retry:
  all outputs are near-identical
  concept drift loses the requested subject
  selected hard anchor is ignored

do not retry:
  one direction is less preferred but still valid
```

Beginner UI wording:

```text
Explore ideas
Use this when you want different possible directions.
```

### 5.4 Format/Layout Adaptation Mode

Internal id:

```text
format_layout_adaptation
```

Compatibility alias:

```text
format_adaptation
```

The code may keep accepting `format_adaptation` for backwards compatibility,
but new metadata and docs should use `format_layout_adaptation`.

Product meaning:

```text
Keep the approved idea and adapt it to different sizes, crops, or layouts.
```

This mode is for:

```text
vertical cover
square feed image
horizontal banner
leave blank space
crop adaptation
same direction, different layout
```

This mode is not for:

```text
new concepts
different people/products
full scene reinvention
```

Execution policy:

```text
visual_distance_budget: layout-only
anchor_strength: strongest available anchor
scene_change_allowed: false unless required by crop safety
role_strategy: format roles
role_difference_requirement: aspect ratio, crop, negative space, or subject
position must change
review_priority: format fit and identity/style preservation
```

Default roles:

```text
vertical_cover
  tall crop, subject safe for cover, optional external overlay space

square_feed
  square crop, balanced central subject, clean margins

horizontal_banner
  wide crop, subject shifted to preserve useful blank area

tight_crop_or_detail
  close crop or detail-safe version under the same direction
```

Prompt pressure:

```text
Preserve the same approved identity, product, style, light, palette, and visual
idea. Change only canvas, crop, subject placement, negative space, and layout
balance according to the role. Do not create a new concept.
```

Review criteria:

```text
pass:
  layout/crop differs by role
  identity/product/style remains stable
  useful blank space exists when requested

retry:
  all outputs use the same crop
  wrong aspect ratio or no layout distinction
  subject/product changed instead of the layout
```

Beginner UI wording:

```text
Adapt size/layout
Use this when you want the same idea in different crops or formats.
```

## 6. Auto Mode Detection

Manual selection remains the strongest signal.

Priority:

```text
1. user manual mode override
2. explicit user prompt
3. requested count plus selected reference state
4. requested sizes/aspect ratios
5. template default
```

Detection rules:

```text
selection_candidates:
  similar, alternatives, choose, pick, best one, same person different poses,
  slight change, a few options

delivery_suite:
  set, series, suite, group, cover plus detail, several useful images,
  half-body / side angle / wide shot, main / lifestyle / detail

creative_exploration:
  different directions, explore, try concepts, different styles, new mood,
  more creative

format_layout_adaptation:
  vertical, horizontal, square, banner, cover crop, layout, blank space,
  size adaptation, crop adaptation
```

Default behavior:

```text
requested_image_count <= 1:
  no multi-output role plan is required unless format adaptation is explicit

requested_image_count > 1 and prompt is vague:
  selection_candidates

requested_image_count > 1 and user asks for "set", "series", role names, or
different use cases:
  delivery_suite

multiple aspect ratios or layout words:
  format_layout_adaptation
```

Important:

```text
The four modes must not all fall back to delivery_suite.
The chosen mode must change role recipes, prompt pressure, and review rules.
```

## 7. Data Contracts

Add or extend contracts under the Visual Capability Cluster.

### 7.1 ModeExecutionPolicy

```python
class ModeExecutionPolicy(V3BaseModel):
    policy_id: str
    mode: str
    mode_source: str = "auto"
    template_id: str | None = None
    requested_image_count: int = 1
    visual_distance_budget: str  # micro | moderate | broad | layout_only
    anchor_strength: str  # weak | medium | strong | strongest_available
    scene_change_allowed: bool = False
    role_strategy: str
    role_difference_requirement: list[str] = []
    review_focus: list[str] = []
    retry_focus: list[str] = []
    beginner_label: str
    beginner_summary: str
    metadata: dict[str, Any] = {}
```

### 7.2 ModeRoleRecipe

```python
class ModeRoleRecipe(V3BaseModel):
    recipe_id: str
    mode: str
    role_id: str
    role_index: int
    beginner_label: str
    role_goal: str
    shot_family: str
    camera_distance: str | None = None
    angle_rule: str | None = None
    crop_rule: str | None = None
    scene_rule: str | None = None
    aspect_ratio: str | None = None
    requested_size: str | None = None
    must_keep: list[str] = []
    must_change: list[str] = []
    forbidden: list[str] = []
    prompt_additions: list[str] = []
    negative_additions: list[str] = []
    review_checks: list[str] = []
    metadata: dict[str, Any] = {}
```

### 7.3 RoleSpecificGenerationPlan

```python
class RoleSpecificGenerationPlan(V3BaseModel):
    plan_id: str
    project_id: str | None = None
    job_id: str | None = None
    mode: str
    requested_image_count: int
    policy: ModeExecutionPolicy
    role_recipes: list[ModeRoleRecipe]
    prompt_plan_summary: list[str] = []
    provider_metadata: dict[str, Any] = {}
    user_visible_summary: list[str] = []
    metadata: dict[str, Any] = {}
```

### 7.4 ModeDifferentiationReview

```python
class ModeDifferentiationReview(V3BaseModel):
    review_id: str
    project_id: str | None = None
    job_id: str | None = None
    mode: str
    status: str  # pass | warning | fail_retryable | manual_review
    role_coverage_status: str  # covered | collapsed | partial | unknown
    identity_or_subject_status: str  # stable | drift | too_cloned | unknown
    duplicate_role_pairs: list[dict[str, Any]] = []
    missing_role_ids: list[str] = []
    over_distance_role_ids: list[str] = []
    retry_patch_by_role: dict[str, dict[str, Any]] = {}
    user_visible_summary: list[str] = []
    metadata: dict[str, Any] = {}
```

Extend `GeneralSuiteRolePlan` without breaking old code:

```text
Keep existing fields.
Add optional:
  mode_execution_policy
  role_specific_generation_plan
  mode_differentiation_review
```

## 8. Runtime Behavior

### 8.1 Planning

Before generation:

```text
1. Resolve effective variation mode.
2. Build ModeExecutionPolicy.
3. Build one ModeRoleRecipe per requested output.
4. Attach the role recipes to the visual cluster result.
5. Thread the role recipes into LLM Brain and deterministic fallback.
6. Pass role metadata to SeriesPlanner so each output asset has its own role.
```

### 8.2 Series planning

SeriesPlanner must not create N identical assets with the same purpose.

Instead:

```text
for each role recipe:
  create one asset/spec with:
    role_id
    beginner_label
    asset purpose
    desired aspect ratio / size if present
    role-specific metadata
```

Examples:

```text
selection_candidates:
  asset purpose = close option for choosing the best frame

delivery_suite:
  asset purpose = cover hero / side angle / wide context / detail

creative_exploration:
  asset purpose = concept lane A / B / C

format_layout_adaptation:
  asset purpose = vertical cover / square feed / horizontal banner
```

### 8.3 Layout planning

LayoutPlan should consume role recipes:

```text
cover_hero:
  strong subject scale, clean cover rhythm

side_or_three_quarter_angle:
  camera/body/head angle distinction required

wide_scene_or_context:
  wider camera distance, environment visible

detail_or_material_closeup:
  closer crop and texture/detail emphasis

horizontal_banner:
  wide composition, subject shifted, blank area preserved
```

### 8.4 Prompt compilation

PromptCompiler must include role-specific instructions in the final prompt for
each output.

Do:

```text
This output role: wide_scene_or_context.
Make the environment visibly wider than the cover/subject-focus image.
Preserve the same identity/style anchor.
Do not use the same crop or camera distance as the cover image.
```

Do not:

```text
Generate a set with cover, side, and wide images.
```

The second form is too broad and lets all images collapse into similar outputs.

### 8.5 Provider behavior

Provider adapters must record:

```text
variation_mode
role_id
role_beginner_label
mode_execution_policy
role_recipe
role_specific_generation_plan_id
active_anchor_ids
reference_asset_count
final_provider_prompt
```

Provider adapters should continue to generate one complete image per output.

Do not ask the model to create a collage, contact sheet, storyboard, or several
roles inside one image.

### 8.6 Review and retry

After outputs exist:

```text
1. Run Doc55 image review.
2. Build ModeDifferentiationReview.
3. Compare outputs against their role recipes.
4. Detect role collapse.
5. Detect identity drift or over-cloning using Doc56/58 rules.
6. Trigger retry only for the failed role(s) when possible.
7. Append retry outputs; never overwrite old outputs.
```

Role-collapse examples:

```text
delivery_suite:
  cover, side, and wide roles are all near half-body front portraits

format_layout_adaptation:
  vertical, square, and horizontal roles all return the same square crop

creative_exploration:
  concept lanes all use the same mood, palette, scene, and composition

selection_candidates:
  all candidates are exact clones, or candidates are so different they cannot
  be compared
```

Retry patch examples:

```text
delivery_suite wide role collapsed:
  "Retry only the wide/context role. Keep identity and style, but use a visibly
  wider camera distance and show more environment."

selection candidates too different:
  "Retry with micro variation only. Keep same scene, outfit, lighting, and
  camera distance; vary only expression or hand position."

creative exploration too similar:
  "Retry one concept lane with a clearly different mood, palette, or art
  direction while keeping the core subject."

format adaptation wrong crop:
  "Retry horizontal banner role with 1536x1024 canvas, subject offset, and
  blank area preserved."
```

## 9. Frontend Requirements

The existing four-mode selector must remain visible in the production composer.

Labels:

```text
Auto
Close options
Make a set
Explore ideas
Adapt size/layout
```

Each label must mean a different thing in the product:

```text
Close options:
  similar alternatives for choosing one best image

Make a set:
  several images with different useful jobs

Explore ideas:
  different possible directions

Adapt size/layout:
  same idea in different crops or formats
```

Result cards may show beginner role labels:

```text
Option 1
Expression shift
Cover
Side angle
Wide scene
Detail
Idea A
Idea B
Vertical cover
Square feed
Horizontal banner
```

Do not show normal users:

```text
ModeExecutionPolicy
ModeRoleRecipe
role_specific_generation_plan_id
visual_cluster
provider
manifest
job id
raw JSON
```

Folded workflow details may show:

```text
Mode used:
  Make a set

V3 kept:
  same selected person, green-highlight hair, bright clean light

V3 changed:
  cover, side angle, wider scene

V3 checked:
  not a different person
  not the same cloned pose
  no visible text or watermark
```

## 10. Implementation Plan

### Phase 1 - Contracts

Files:

```text
app/shared_capabilities/visual_cluster/contracts.py
app/shared_capabilities/visual_cluster/mode_role_director.py
app/shared_capabilities/visual_cluster/__init__.py
```

Tasks:

```text
1. Add ModeExecutionPolicy.
2. Add ModeRoleRecipe.
3. Add RoleSpecificGenerationPlan.
4. Add ModeDifferentiationReview.
5. Extend VisualCapabilityClusterResult and GeneralSuiteRolePlan with optional
   mode-aware fields.
6. Keep existing Doc58 fields backward-compatible.
```

Tests:

```text
contract validation
serialization
no V1/V2 runtime imports
encoding guardrail
```

### Phase 2 - ModeRoleDirector

Files:

```text
app/shared_capabilities/visual_cluster/mode_role_director.py
app/shared_capabilities/visual_cluster/general_suite_director.py
app/shared_capabilities/visual_cluster/module.py
```

Tasks:

```text
1. Resolve effective mode using Doc54 priority.
2. Build ModeExecutionPolicy for each mode.
3. Build count-aware role recipes.
4. Support subject kind:
   human
   product/object
   brand/style
   generic scene
5. Preserve E-Commerce slot semantics when template_id is ecommerce_template.
6. Attach user-visible beginner labels.
```

Tests:

```text
selection_candidates returns micro near-neighbor recipes
delivery_suite returns purposeful role recipes
creative_exploration returns concept-lane recipes
format_layout_adaptation returns format/crop recipes
ecommerce_template maps to ecommerce business slots without using General roles
```

### Phase 3 - Role-Specific Series And Prompt Threading

Files:

```text
app/agents/series_planner_agent.py
app/agents/layout_agent.py
app/agents/prompt_compiler_agent.py
app/creative_core/central_brain.py
app/llm_brain/fallback.py
app/llm_brain/prompts.py
```

Tasks:

```text
1. Thread RoleSpecificGenerationPlan into planning metadata.
2. Give each output asset one role_id and one role recipe.
3. Make layout planning role-aware.
4. Make prompt compilation role-aware.
5. Ensure each provider request says what this one image should do.
6. Keep selected-output anchors and reference images intact.
```

Tests:

```text
requested count 3 creates 3 role-specific asset specs
each asset has a unique role_id
final prompts differ by role
delivery_suite wide role prompt contains wider camera/context instruction
selection_candidates prompts stay close and comparable
format_layout_adaptation prompts contain size/crop/layout rules
```

### Phase 4 - Provider Metadata And Output Persistence

Files:

```text
app/generation_router/providers.py
app/product_api/service.py
app/project_mode/service.py
```

Tasks:

```text
1. Persist role_id and mode on each candidate/output.
2. Persist role recipe summary in output metadata.
3. Preserve active_anchor_ids and reference_asset_count.
4. Ensure generated history can group outputs by project and display role labels.
5. Do not overwrite old outputs when retrying failed roles.
```

Tests:

```text
generated output metadata contains variation_mode and role_id
project history still groups by project
retry output appends with retry source role
old output remains visible
```

### Phase 5 - Mode Differentiation Review

Files:

```text
app/shared_capabilities/visual_cluster/batch_identity_review.py
app/shared_capabilities/visual_cluster/vision_inspector.py
app/product_api/service.py
```

Tasks:

```text
1. Build ModeDifferentiationReview after outputs exist.
2. Detect role collapse per mode.
3. Detect too-different or too-cloned outputs using Doc56/58 rules.
4. Create role-specific retry patches.
5. Retry only failed role(s) when possible.
6. If review confidence is low, mark manual_review and do not auto retry.
```

Tests:

```text
fake delivery_suite collapse produces retry patch for missing/deduplicated role
fake selection_candidates over-distance produces micro-variation retry patch
fake creative_exploration sameness produces concept-diversity retry patch
fake format adaptation wrong crop produces layout retry patch
low confidence does not retry
same issue repeated stops retry loop
```

### Phase 6 - Frontend Productization

Files:

```text
src_skeleton/app/static/app.js
src_skeleton/app/static/styles.css
src_skeleton/app/mobile_static/mobile.js
src_skeleton/app/mobile_static/mobile.css
tests/test_v3_commercial_frontend_shell.py
```

Tasks:

```text
1. Replace any generic "image purpose" control in General Template with the
   four-mode selector.
2. Keep Auto as default.
3. Render concise mode helper text.
4. Show beginner role labels on result cards when available.
5. Fold workflow details.
6. Hide engineering terms.
7. Verify mobile layout.
```

Tests:

```text
four mode labels are present
manual selected mode is sent to API
result cards can render role labels
folded workflow detail includes kept/changed/checked summaries
forbidden engineering terms are not visible in normal UI
mobile static syntax passes
```

### Phase 7 - Real Smoke And Quality Comparison

Run real provider tests only when configured provider is available.

Portrait tasks:

```text
1. Similar Candidates:
   selected green-highlight East Asian model, count 3.
   Expected: same model, small pose/expression/crop differences.

2. Suite Expansion:
   selected green-highlight East Asian model, count 4.
   Expected: cover, side/three-quarter, wider context, detail/mood or layout.

3. Creative Exploration:
   same project core, count 3.
   Expected: different visual directions while retaining selected anchor if
   the anchor is active.

4. Format/Layout Adaptation:
   same selected image direction, vertical/square/horizontal.
   Expected: same person/style, visibly different layout/canvas.
```

Product tasks:

```text
1. E-Commerce delivery suite:
   product reference, count 3.
   Expected: main image, lifestyle scene, detail image are visually distinct.

2. E-Commerce similar candidates:
   product reference, same slot, count 3.
   Expected: comparable alternatives, not a full suite.
```

Quality comparison must record:

```text
identity/product consistency
role separation
mode-specific behavior
watermark/text cleanliness
old outputs not overwritten
reference count and active anchor ids in metadata
```

## 11. Acceptance Criteria

### 11.1 Mode behavior is genuinely different

Pass:

```text
selection_candidates does not create wide scene / concept lanes
delivery_suite does not create only near-identical candidates
creative_exploration creates distinct concepts
format_layout_adaptation changes layout/crop/canvas instead of subject
```

### 11.2 Role-specific prompts exist

Pass:

```text
each generated output has a role_id
each final provider prompt contains this output's role goal
prompts differ meaningfully across roles
provider metadata records mode and role recipe
```

### 11.3 Strong reference remains active

Pass:

```text
selected output remains the active anchor
continuation outputs use the selected output file as provider reference when available
role differentiation does not weaken identity/product lock
unselected candidates remain historical only
```

### 11.4 Review catches role collapse

Pass:

```text
delivery_suite all-near-portrait batch is not accepted as ideal
format adaptation same-crop batch is not accepted as ideal
creative exploration near-identical concept batch is flagged
selection candidates totally different-person batch is flagged
clear retryable issues produce concrete role-specific retry patches
```

### 11.5 Beginner UI remains simple

Pass:

```text
normal UI shows four plain modes and image-first results
result role labels are plain language
workflow details are folded
normal UI does not expose engineering terms
mobile remains usable
```

## 12. Test Plan

Focused backend:

```powershell
pytest alchemy_creative_agent_3_0/tests/test_v3_shared_capability_modules.py -q
pytest alchemy_creative_agent_3_0/tests/test_v3_llm_brain_adapter.py -q
pytest alchemy_creative_agent_3_0/tests/test_v3_project_mode.py -q
pytest alchemy_creative_agent_3_0/tests/test_v3_visual_auto_retry.py -q
pytest alchemy_creative_agent_3_0/tests/test_v3_post_generation_vision_review.py -q
pytest alchemy_creative_agent_3_0/tests/test_v3_encoding_guardrails.py -q
```

Frontend:

```powershell
pytest tests/test_v3_commercial_frontend_shell.py -q
node --check src_skeleton/app/static/app.js
node --check src_skeleton/app/mobile_static/mobile.js
```

Full verification:

```powershell
pytest alchemy_creative_agent_3_0/tests tests -q
python -m compileall -q alchemy_creative_agent_3_0 src_skeleton
git diff --check
```

Real smoke:

```powershell
$env:PYTHONPATH='src_skeleton;.;alchemy_creative_agent_3_0'
```

Then run:

```text
same selected green-highlight East Asian model:
  selection_candidates count 3
  delivery_suite count 4
  creative_exploration count 3
  format_layout_adaptation count 3

same product reference:
  ecommerce delivery suite count 3
  ecommerce similar candidates count 3
```

If provider fails:

```text
record provider error
wait and retry once
do not mark mode logic failed when upstream did not return images
```

## 13. Implementation Handoff Prompt

Use this prompt when coding begins:

```text
Implement document 59.

Keep Doc54 as the four-mode taxonomy, Doc58 as the identity-anchor and strong
reference lifecycle, and Doc50 as the Visual Capability Cluster architecture.

Add mode-aware execution contracts under the V3 Visual Capability Cluster:
ModeExecutionPolicy, ModeRoleRecipe, RoleSpecificGenerationPlan, and
ModeDifferentiationReview.

Make the four General Template modes functionally different:
selection_candidates = close alternatives for choosing the best frame;
delivery_suite = a purposeful set with distinct image duties;
creative_exploration = distinct concept lanes;
format_layout_adaptation = same idea with different crops/canvases.

Thread each role recipe into SeriesPlanner, LayoutAgent, PromptCompiler,
provider metadata, generated output metadata, Project Mode summaries, and
post-generation review. Each generated output must have a role_id and a
role-specific prompt. Do not rely on one broad suite prompt for all outputs.

For E-Commerce, preserve the existing E-Commerce slot planner from Doc57.
Use Doc59 only to enforce role-specific generation and review; do not replace
main_image, scenario_image, detail_image, or other business slots with General
Template universal roles.

Add review logic that detects role collapse per mode and produces role-specific
retry patches. Retry only clear, retryable failed roles within budget, and
append outputs without overwriting old ones.

Keep the frontend beginner-facing: four simple mode labels, image-first result
cards, plain role labels, folded workflow details, and no engineering terms.

Run focused backend tests, frontend static checks, full regression, compile
checks, and real GPT image 2 smoke when the provider is available.
```
