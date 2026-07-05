# 58 V3 Identity Anchor Strong Reference And Suite Director Spec

## 1. Status And Authority

This document is the next development authority after documents `51`, `54`,
`55`, and `56` for Lovart-level General Template improvement.

It focuses on three gaps observed during real GPT image 2 validation:

```text
1. Human identity is directionally consistent, but not yet strong enough to feel
   like the same commercial character/model across a project.
2. Strong selected-image references exist, but the closed loop is not strict
   enough: selected outputs must automatically become the next generation's
   identity/style anchor.
3. General Template multi-image output can be visually nice, but it does not
   yet feel directed as a purposeful suite with image roles such as cover,
   half-body, side angle, wide scene, atmosphere, and layout/crop adaptation.
```

Authority chain:

```text
Doc50:
  Owns the V3-native Visual Capability Cluster as the home of reusable visual
  enhancement.

Doc51:
  Owns strong selected references, identity/product/brand locks, and
  Lovart-gap closure.

Doc54:
  Owns General Template variation modes:
  similar candidates, delivery suite, creative exploration, and
  format/layout adaptation.

Doc55:
  Owns real post-generation inspection and retry execution.

Doc56:
  Owns human identity consistency balanced with natural variation.

Doc58:
  Owns the next closure layer:
  Identity Anchor lifecycle, automatic strong-reference continuation,
  identity similarity/difference balance, and General Suite Director roles.

Doc59:
  Extends Doc58 after real generation validation. It does not replace the
  Identity Anchor or Strong Reference Loop. It makes the four Doc54 modes
  execute differently through mode-specific role recipes, prompts, review,
  retry patches, and beginner summaries.

Doc61:
  Adds the portrait commercial consistency validation and Lovart benchmark
  acceptance layer. It does not replace Doc58's identity-anchor or strong
  reference lifecycle; it verifies that the lifecycle works in real portrait
  generation.
```

If documents conflict:

```text
Doc58 wins for:
  selected output becoming a strong identity/style anchor
  human identity anchor lifecycle
  same-person-but-not-cloned evaluation
  General Template suite role planning
  post-generation batch-level identity/diversity review

Doc56 still wins for:
  the principle that human consistency must not freeze expression, pose, head
  angle, crop, camera angle, or hair frame.

Doc54 still wins for:
  the four user-facing General Template variation modes.

Doc51 still wins for:
  keeping the architecture inside the V3-native Visual Capability Cluster.

Doc59 wins for:
  role differentiation after a mode has been chosen
  preventing all four modes from collapsing into the same suite behavior
  role-specific prompts and role-collapse review

Doc61 wins for:
  real portrait validation protocol
  Lovart benchmark comparison wording
  acceptance evidence required before claiming portrait-suite commercial
  readiness
```

This document does not:

```text
rewrite Project Mode
rewrite ScenarioRuntime
rewrite Product API
replace V3 LLM Brain
call V1/V2 runtime code
add Claude Code as a brain/provider route
unfreeze E-Commerce Template beyond already planned interfaces
turn the beginner UI into an engineering console
guarantee exact real-person identity without suitable reference/provider support
```

## 2. Product Target

V3 should move from:

```text
same visual style
same rough model archetype
similar nice pictures
```

to:

```text
same project character/model direction
selected image becomes a strong anchor
new outputs read the anchor automatically
identity does not drift into a different person
outputs do not clone the same expression/angle/pose
each image has a clear role in the suite
the user can keep working in the project without prompt expertise
```

Benchmark:

```text
Lovart-like project continuity:
  not a copied UI
  not an infinite canvas clone
  but a project-level design chain where chosen assets influence the next step
```

Beginner-facing promise:

```text
V3 will remember the image you chose, keep the person/product/design direction,
and make the next images feel like part of the same project rather than random
new generations.
```

Important identity principle:

```text
Same person, different shoot moments.

Not:
  same exact face crop in every image
  same smile in every image
  same head angle in every image
  same pose in every image

Also not:
  different person with only similar style
  random hair/age/body/wardrobe drift
```

## 3. Architecture Decision

### 3.1 Keep V3 visual enhancement modular

All new logic belongs under:

```text
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/
```

Do not add the new logic as a heavy top-level CentralCreativeBrain feature.

Target new child modules:

```text
visual_cluster/
  identity_anchor.py
  strong_reference_loop.py
  batch_identity_review.py
  general_suite_director.py
```

These may be implemented as separate files or as focused classes in existing
files if that better matches the current codebase. Ownership must remain clear:

```text
Visual Capability Cluster owns:
  identity anchor profiles
  selected-output strong reference promotion
  batch identity/diversity review
  suite role planning policy
  retry patch suggestions for identity drift or over-cloning

LLM Brain owns:
  translating these structured policies into generation strategy and prompt
  guidance.

Provider layer owns:
  passing available reference image files to the image provider and recording
  final provider prompt metadata.

Project Mode owns:
  storing selected outputs, project context, timeline items, and beginner UI
  summaries.
```

### 3.2 No framework rewrite

Implementation must wrap the current V3 flow:

```text
Project
  -> ProjectContextPackage
  -> ScenarioRuntime / Product API Job
  -> Visual Capability Cluster
  -> LLM Brain
  -> Prompt Compiler / Generation Router
  -> Provider
  -> Generated outputs
  -> Post-generation review
  -> Selection updates ProjectContextPackage
```

Do not replace these with a new project/job system.

### 3.3 Additive compatibility

The existing Doc56 implementation remains valid:

```text
HumanNaturalVariationPolicy
HumanIdentityAnchorProfile
HumanNaturalVariationPlan
HumanBatchDiversityReview
```

Doc58 extends it with a stronger lifecycle:

```text
prompt-only identity direction
  -> first generated candidate
  -> user selected identity anchor
  -> strong reference binding
  -> continuation generation
  -> batch identity/diversity review
  -> retry if too loose or too cloned
```

## 4. Core Concepts

### 4.1 Identity Anchor

An Identity Anchor is the project-scoped source of truth for a human character,
model, product, brand asset, or other repeatable subject.

For humans:

```text
stable:
  recognizable facial feature relationship
  broad age band
  skin tone direction
  face shape direction
  body type and proportions
  broad hair color and length range
  broad wardrobe category when relevant
  same commercial visual world

flexible:
  expression
  gaze
  head angle
  pose
  body turn
  hand placement
  crop
  camera angle
  camera distance within planned role
  hair movement and small styling details
  scene role when suite mode calls for it
```

For products:

```text
stable:
  product shape
  material
  color
  proportions
  label/logo position
  visible key details

flexible:
  angle
  surface
  scene
  lighting
  crop
  supporting props when allowed
```

### 4.2 Strong Reference Loop

When the user selects an output as satisfactory, V3 must treat it as a stronger
future reference than generic project style text.

Rules:

```text
1. Selected output becomes positive context.
2. Unselected candidates stay historical only.
3. Rejected/deleted outputs become negative context, not positive anchors.
4. Selected output file path is passed to provider when available.
5. If file path is unavailable, V3 degrades to prompt-level anchor metadata and
   records the degraded mode.
6. Strong reference is project-scoped by default.
7. Brand Memory update still requires explicit user confirmation.
```

### 4.3 Identity Similarity Window

V3 must not optimize for maximum similarity only.

Target window:

```text
too loose:
  looks like a different person/product

acceptable:
  same recognizable model/product/design direction, with natural variation

too cloned:
  same expression, head angle, pose, crop, or camera angle repeated across most
  outputs
```

Review should classify both sides:

```text
identity_drift
face_feature_drift
body_shape_drift
hair_direction_drift
wardrobe_category_drift
over_cloned_face
over_cloned_expression
over_cloned_pose
over_cloned_camera_angle
over_cloned_crop
```

### 4.4 General Suite Director

The General Template must support purposeful suite roles without hard-coding
e-commerce listing slots.

Universal General Template roles:

```text
cover_hero
  strongest first impression, cover-safe crop, clean subject hierarchy

portrait_or_subject_focus
  clear subject, medium crop, identity/product visibility

side_or_three_quarter_angle
  different angle while preserving identity

wide_scene_or_context
  environment and atmosphere, subject still recognizable

detail_or_mood_closeup
  texture, expression, material, hair movement, hand/object detail, or mood cue

layout_adaptation
  crop/negative space/layout-safe variant for covers, posts, banners

atmosphere_bridge
  supports campaign mood, not necessarily the strongest standalone hero
```

These are not all required in every job. The Suite Director chooses roles based
on variation mode, requested count, project state, and user prompt.

## 5. Data Contracts

Add or extend contracts under the Visual Capability Cluster.

### 5.1 ProjectIdentityAnchor

```python
class ProjectIdentityAnchor(V3BaseModel):
    anchor_id: str
    project_id: str
    subject_type: str  # human | product | brand_asset | object | style
    source_type: str  # selected_output | uploaded_reference | generated_candidate | prompt_only
    source_output_id: str | None = None
    source_candidate_id: str | None = None
    source_asset_id: str | None = None
    source_file_path: str | None = None
    strength: str = "medium"  # weak | medium | strong
    status: str = "active"  # draft | active | inactive | rejected
    stable_traits: list[str] = []
    flexible_traits: list[str] = []
    forbidden_drift: list[str] = []
    provider_reference_required: bool = False
    prompt_only_fallback: bool = False
    user_visible_summary: list[str] = []
    metadata: dict[str, Any] = {}
```

### 5.2 StrongReferenceContinuationPlan

```python
class StrongReferenceContinuationPlan(V3BaseModel):
    plan_id: str
    project_id: str | None = None
    job_id: str | None = None
    applies: bool = False
    anchor_ids: list[str] = []
    provider_reference_asset_ids: list[str] = []
    prompt_reference_rules: list[str] = []
    lock_rules: list[str] = []
    allowed_variation_rules: list[str] = []
    negative_rules: list[str] = []
    degraded_reason: str | None = None
    user_visible_summary: list[str] = []
    metadata: dict[str, Any] = {}
```

### 5.3 GeneralSuiteRolePlan

```python
class GeneralSuiteRolePlan(V3BaseModel):
    plan_id: str
    variation_mode: str
    requested_image_count: int
    applies: bool = False
    roles: list[dict[str, Any]] = []
    prompt_additions: list[str] = []
    negative_additions: list[str] = []
    user_visible_summary: list[str] = []
    metadata: dict[str, Any] = {}
```

Each role item:

```python
{
    "role_id": "cover_hero",
    "role_label": "Cover hero",
    "purpose": "strong first impression",
    "composition": "large subject, cover-safe crop, clean negative space",
    "identity_rule": "same recognizable identity direction",
    "allowed_variation": ["expression", "head angle", "crop"],
    "forbidden": ["different person", "same cloned pose as previous role"],
}
```

### 5.4 BatchIdentityDiversityReview

```python
class BatchIdentityDiversityReview(V3BaseModel):
    review_id: str
    project_id: str | None = None
    job_id: str | None = None
    applies: bool = False
    status: str = "not_applicable"  # pass | warning | fail_retryable | manual_review
    identity_status: str = "unknown"  # too_loose | balanced | too_cloned | unknown
    issue_codes: list[str] = []
    preserved_identity_notes: list[str] = []
    diversity_notes: list[str] = []
    role_fit_notes: list[str] = []
    retry_patch: dict[str, Any] = {}
    user_visible_summary: list[str] = []
    metadata: dict[str, Any] = {}
```

## 6. Runtime Behavior

### 6.1 First generation without selected anchor

If the project has no selected anchor:

```text
1. V3 uses prompt-level identity direction.
2. V3 may generate multiple candidates, but must not claim exact same identity.
3. UI should encourage selecting the best image if the user wants continuation.
4. Once selected, the selected output becomes the strong identity/style anchor.
```

Beginner wording:

```text
Pick the image closest to the direction you like. V3 will use it as the next
round's reference.
```

### 6.2 User selection creates or updates anchor

On output selection:

```text
1. Store selected output in ProjectContextPackage.
2. Create/activate ProjectIdentityAnchor.
3. If generated file exists, set provider_reference_required = true.
4. Mark unselected outputs as history only.
5. Do not update Brand Memory automatically.
6. Add project timeline item: identity_anchor_updated.
```

### 6.3 Continuation generation

Before generating a continuation job:

```text
1. Build StrongReferenceContinuationPlan from active anchors.
2. Pass selected output file path as provider reference when available.
3. Add prompt rules:
   preserve recognizable identity/body/hair/wardrobe direction
   allow planned expression/pose/head angle/camera/crop variation
4. Add negative rules:
   different person
   face swap
   major body-shape drift
   major hair/wardrobe drift
   same exact expression/pose/head angle/crop across all images
5. Build GeneralSuiteRolePlan if requested count >= 2 or continuation mode
   requires a suite.
```

### 6.4 Post-generation review

After outputs exist:

```text
1. Inspect each output with existing Doc55 image review.
2. If requested count >= 2, create a batch-level review.
3. Review both:
   identity drift
   over-cloned repetition
4. Review suite role fit:
   whether roles are meaningfully different
   whether outputs are still coherent as one project
5. Trigger retry only when the issue is clear and retry budget allows it.
```

Retry patch examples:

```text
If too loose:
  strengthen reference image usage
  restate stable face/body/hair/wardrobe/product traits
  reduce creative exploration radius

If too cloned:
  keep identity but vary expression, head angle, body turn, camera angle, crop,
  or role
  explicitly avoid duplicating the same still

If role plan missing:
  assign roles again with stronger composition distinction
```

## 7. Variation Mode Mapping

### 7.1 selection_candidates

Purpose:

```text
Give similar options so the user can choose the best frame.
```

Suite Director behavior:

```text
Do not force a full suite.
Use near-neighbor candidate roles:
  candidate_best_frame
  candidate_expression_shift
  candidate_head_angle_shift
  candidate_crop_shift
```

Identity target:

```text
high identity consistency
subtle diversity
no cloned stills
```

Retry focus:

```text
too different person
same exact expression/pose/angle across candidates
```

### 7.2 delivery_suite

Purpose:

```text
Make a useful image set under one approved direction.
```

Suite Director behavior:

```text
Choose roles based on requested count:

1 image:
  cover_hero

2 images:
  cover_hero
  portrait_or_subject_focus or side_or_three_quarter_angle

3 images:
  cover_hero
  portrait_or_subject_focus
  wide_scene_or_context or detail_or_mood_closeup

4 images:
  cover_hero
  portrait_or_subject_focus
  side_or_three_quarter_angle
  wide_scene_or_context or layout_adaptation
```

Identity target:

```text
strong identity consistency
medium diversity
role differences should be visible
```

### 7.3 creative_exploration

Purpose:

```text
Explore broader creative directions for the same project.
```

Suite Director behavior:

```text
Use direction roles:
  concept_a
  concept_b
  concept_c
  layout_flexible_concept
```

Identity target:

```text
medium identity consistency unless user explicitly locks the person/product
broad visual diversity
avoid changing the subject into something unrelated
```

### 7.4 format_layout_adaptation

Purpose:

```text
Adapt the same visual direction into formats/layouts.
```

Suite Director behavior:

```text
Use layout roles:
  square_safe
  vertical_cover
  horizontal_banner
  tight_crop_or_detail
```

Identity target:

```text
strong identity consistency
subtle presentation diversity
layout/crop differences are the main variation
```

## 8. Prompt And Provider Rules

Provider prompt for human strong reference:

```text
Use the selected image as a strong identity and style anchor. Preserve the
recognizable person direction, body type, broad hair color/length, wardrobe
category, and lighting language. Do not copy the exact same expression, pose,
head angle, camera angle, or crop across the batch.
```

Provider prompt for suite roles:

```text
Create each output as one complete image with a distinct role in the same
project suite. Keep the same identity/style anchor, but vary the planned role,
camera distance, crop, pose, or scene according to the role plan.
```

Negative prompt additions:

```text
different person
face swap
major body-shape drift
major hair color or length drift unless requested
major wardrobe category drift unless requested
same exact expression in every image
same exact pose in every image
same exact head angle in every image
same crop repeated across every image
cloned stills
contact sheet
collage
visible text
watermark
```

Provider metadata must record:

```text
active_anchor_ids
reference_asset_ids
provider_reference_count
prompt_only_fallback
suite_role_plan
identity_similarity_policy
allowed_variation_axes
final_provider_prompt
```

## 9. Project Mode And UI Requirements

### 9.1 Beginner UI stays simple

Do not expose these terms in the normal UI:

```text
identity anchor
strong reference binding
cluster
provider reference
BatchIdentityDiversityReview
manifest
raw JSON
job id
```

Beginner-facing wording:

```text
V3 will use your chosen image as the reference for the next images.
V3 will keep the person/product/design direction.
V3 will change pose, angle, scene, or layout naturally when needed.
```

### 9.2 Selected image affordance

In the project output viewer:

```text
1. The user can mark an image as the project reference.
2. The chosen reference is visually marked in plain language:
   "Used as next reference"
3. If a different image is chosen later, V3 updates the active anchor.
4. The user can remove/deactivate the reference from the project.
```

### 9.3 Production composer

The four Doc54 modes remain available:

```text
Auto
Similar candidates
Suite expansion
Creative exploration
Size/layout adaptation
```

Add a small plain-language helper:

```text
Similar candidates:
  Several close options for choosing the best frame.

Suite expansion:
  A small set with different useful roles under the same direction.

Creative exploration:
  Broader ideas, still tied to the project.

Size/layout adaptation:
  Same direction, different crops and layouts.
```

### 9.4 Workflow detail card

Advanced folded card may show:

```text
Reference used:
  selected image / uploaded image / prompt only

V3 preserved:
  person direction, body type, hair direction, light, style

V3 changed:
  expression, pose, angle, crop, scene role

V3 checked:
  not a different person
  not copied stills
  no visible text/watermark
```

No raw engineering metadata should appear unless an explicit developer/debug
mode exists.

## 10. Implementation Plan

### Phase 1 - Contracts

Files:

```text
visual_cluster/contracts.py
visual_cluster/identity_anchor.py
visual_cluster/general_suite_director.py
```

Tasks:

```text
1. Add ProjectIdentityAnchor.
2. Add StrongReferenceContinuationPlan.
3. Add GeneralSuiteRolePlan.
4. Add BatchIdentityDiversityReview.
5. Extend VisualCapabilityClusterResult with these optional fields.
```

Tests:

```text
contract model validation
safe_metadata serialization
no forbidden V1/V2 imports
encoding guardrail passes
```

### Phase 2 - Selected Output Anchor Lifecycle

Files:

```text
project_mode/contracts.py
project_mode/service.py
product_api/service.py
visual_cluster/identity_anchor.py
```

Tasks:

```text
1. When user selects output, create or update active ProjectIdentityAnchor.
2. Store source output/candidate/asset/file path when available.
3. Ensure unselected candidates are excluded from positive context.
4. Add timeline item: reference direction updated.
5. Keep Brand Memory update explicit only.
```

Tests:

```text
selecting image creates active anchor
selecting second image updates active anchor
deleted/rejected image does not remain active anchor
brand memory is not automatically updated
project context exposes selected anchor to next job
```

### Phase 3 - Strong Reference Continuation

Files:

```text
visual_cluster/strong_reference_loop.py
generation_router/providers.py
llm_brain/fallback.py
llm_brain/prompts.py
agents/prompt_compiler_agent.py
```

Tasks:

```text
1. Build StrongReferenceContinuationPlan before generation.
2. Pass selected output file path as provider reference when available.
3. Add prompt guidance for stable traits and allowed variation.
4. Record degraded prompt-only mode when file path is missing.
5. Preserve existing provider fallback and retry behavior.
```

Tests:

```text
continuation job includes selected output reference file
provider metadata records active anchors
prompt includes stable identity plus allowed variation
prompt does not say to copy exact expression/pose/head angle
missing file degrades without crash
```

### Phase 4 - General Suite Director

Files:

```text
visual_cluster/general_suite_director.py
llm_brain/fallback.py
agents/series_planner_agent.py
agents/layout_agent.py
product_api/service.py
```

Tasks:

```text
1. Map Doc54 variation modes to suite role plans.
2. Respect requested_image_count.
3. For Similar Candidates, keep roles close and comparable.
4. For Suite Expansion, create purposeful roles.
5. For Creative Exploration, allow broader concept roles.
6. For Format/Layout Adaptation, focus on crop/layout roles.
7. Thread role plan into prompt compilation and provider metadata.
```

Tests:

```text
selection_candidates produces candidate role plan, not delivery suite roles
delivery_suite with count 4 produces four different useful roles
format_layout_adaptation produces layout roles
requested count controls role count
roles are visible in folded workflow metadata, not raw beginner UI
```

### Phase 5 - Batch Identity/Diversity Review

Files:

```text
visual_cluster/batch_identity_review.py
visual_cluster/vision_inspector.py
product_api/service.py
project_mode/service.py
```

Tasks:

```text
1. Review generated batch after outputs exist.
2. Detect too-loose identity drift.
3. Detect over-cloned expression/pose/head angle/crop.
4. Detect role duplication when Suite Director expected role variety.
5. Create retry_patch for clear retryable problems.
6. Do not retry on low-confidence review.
```

Possible implementation levels:

```text
metadata-only:
  role/plan checks only

vision-model:
  contact sheet or pairwise image review when configured

hybrid:
  metadata precheck plus vision-model review for real outputs
```

Tests:

```text
fake too_loose issue creates strengthen-reference retry patch
fake too_cloned issue creates variation retry patch
low-confidence review becomes manual_review
retry appends new outputs without overwriting old outputs
retry budget stops loops
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
1. Mark selected reference in beginner language.
2. Keep the project page image-first.
3. Add folded workflow detail:
   used reference, preserved traits, changed traits, checks.
4. Keep variation mode selector small and clear.
5. Do not show engineering terms in normal UI.
6. Mobile layout must remain clean.
```

Tests:

```text
frontend shell has mode selector labels
frontend shell does not expose forbidden engineering terms
selected reference marker appears
workflow details are folded
mobile static checks pass
```

## 11. Automatic Retry Rules

Retry only when:

```text
provider output exists
issue is clear and retryable
retry patch has concrete changes
retry attempt count is below budget
issue is not simply subjective taste
provider/rate-limit failure is not the cause
```

Do not retry when:

```text
vision confidence is low
the user explicitly requested exact copy
the output is usable but stylistically debatable
provider failed before image creation
retry patch would repeat the same prompt
max retry attempts reached
```

Retry patch policy:

```text
too_loose:
  stronger reference image usage
  tighter stable traits
  reduce creative exploration radius

too_cloned:
  keep identity but vary expression, pose, head angle, camera angle, crop, role

role_duplicate:
  restate role plan and require visibly different shot purpose

artifact:
  reuse Doc55/57 watermark/text/anatomy cleanup
```

Default retry budget:

```text
max one automatic visual retry per job unless later docs raise the budget
```

## 12. Acceptance Criteria

### 12.1 Same person, not cloned

Given:

```text
Create two same-model East Asian summer portrait alternatives.
Select the best one.
Continue the project with two more images in the same direction.
```

Pass:

```text
selected image becomes active project reference
continuation job uses selected output as provider reference when file exists
new outputs preserve recognizable person/body/hair/styling direction
new outputs vary expression, pose, head angle, crop, or camera angle
batch review does not pass cloned stills as ideal
batch review does not pass obvious person drift as ideal
old outputs remain visible and are not overwritten
```

### 12.2 Suite Director

Given:

```text
Use Suite Expansion mode, requested count 4.
```

Pass:

```text
role plan has four roles
roles are not all the same framing
final provider prompt contains role distinctions
generated metadata records suite_role_plan
beginner UI explains the set in plain language
```

### 12.3 Similar Candidates

Given:

```text
Use Similar Candidates mode, requested count 3.
```

Pass:

```text
role plan stays close/comparable
no full delivery-suite roles are forced
identity is stronger than creative exploration
outputs vary small but visible presentation details
```

### 12.4 Strong Reference Loop

Given:

```text
User selects one generated image.
User clicks continue.
```

Pass:

```text
selected output enters ProjectContextPackage
selected output source file path is passed to provider if available
provider metadata records reference count and anchor id
unselected candidates are not used as positive anchors
deleting/deactivating reference removes it from future positive context
```

### 12.5 Encoding Guardrail

Pass:

```text
no new source file contains repeated question-mark placeholder text
no mojibake Chinese appears in V3 recent source scope
Chinese tests use UTF-8 files or unicode escapes, not PowerShell inline text
```

## 13. Test Plan

Focused tests:

```powershell
$env:PYTHONPATH='.'
pytest alchemy_creative_agent_3_0/tests/test_v3_encoding_guardrails.py -q
pytest alchemy_creative_agent_3_0/tests/test_v3_shared_capability_modules.py -q
pytest alchemy_creative_agent_3_0/tests/test_v3_llm_brain_adapter.py -q
pytest alchemy_creative_agent_3_0/tests/test_v3_project_mode.py -q
pytest alchemy_creative_agent_3_0/tests/test_v3_post_generation_vision_review.py -q
pytest alchemy_creative_agent_3_0/tests/test_v3_visual_auto_retry.py -q
pytest tests/test_v3_commercial_frontend_shell.py -q
```

Compile and static checks:

```powershell
python -m compileall -q alchemy_creative_agent_3_0 src_skeleton
node --check src_skeleton/app/static/app.js
node --check src_skeleton/app/mobile_static/mobile.js
git diff --check
```

Real smoke:

```text
1. Create a General Template project:
   "Create two same-model East Asian summer cool portrait alternatives..."
2. Generate two images with real GPT image 2 when provider is available.
3. Select the best image.
4. Continue with Suite Expansion mode and count 3 or 4.
5. Confirm selected image is used as strong reference.
6. Confirm continuation is not a different person and not cloned stills.
7. Confirm no visible text/watermark.
```

Use `PYTHONPATH=src_skeleton;.;alchemy_creative_agent_3_0` for real provider
smoke when calling the current V3-to-provider compatibility path.

## 14. Implementation Handoff Prompt

Use this prompt when coding begins:

```text
Implement document 58.

Do not rewrite the V3 foundation. Keep Project Mode, Product API,
ScenarioRuntime, LLM Brain, provider layer, and the Visual Capability Cluster
ownership intact.

Add ProjectIdentityAnchor, StrongReferenceContinuationPlan,
GeneralSuiteRolePlan, and BatchIdentityDiversityReview under the V3-native
Visual Capability Cluster.

When a user selects an output, promote it to a project-scoped active identity or
style anchor. On continuation jobs, pass the selected output file as a strong
provider reference when available and add prompt rules that preserve identity
while varying expression, pose, angle, crop, or role.

Add General Suite Director role planning for Doc54 modes. Similar Candidates
must stay close/comparable. Suite Expansion must create purposeful roles such as
cover hero, subject focus, side/three-quarter angle, wide scene, mood/detail,
and layout adaptation according to requested count.

Add batch-level post-generation review that detects both identity drift and
over-cloned repetition. Retry only when the issue is clear, retryable, and under
budget. Append new outputs; never overwrite old outputs.

Keep UI beginner-facing and image-first. Fold workflow details. Do not expose
engineering terms in normal UI.

Maintain encoding safety: no source file may contain question-mark corruption or
mojibake Chinese. Chinese test strings must use UTF-8 files or unicode escapes,
not PowerShell inline text.

Run focused tests, compile checks, frontend static checks, and one real GPT
image 2 smoke when provider availability allows.
```
