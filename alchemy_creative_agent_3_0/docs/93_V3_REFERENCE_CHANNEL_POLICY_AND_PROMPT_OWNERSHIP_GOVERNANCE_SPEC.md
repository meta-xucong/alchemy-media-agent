# 93 V3 Reference Channel Policy And Prompt Ownership Governance Spec

## 0. Status And Authority

This document is the current V3 foundation authority for deciding:

```text
what each reference asset is allowed to contribute
which visual channels are inherited
which visual channels remain owned by the current prompt
how explicit user instructions override reference continuity
how uploaded truth sources differ from selected generated outputs
how review and retry detect reference-style leakage
```

Doc93 is a foundation governance and implementation-closure document. It does
not create a new top-level framework, template runtime, project type, central
brain, or provider system.

Implementation status on 2026-07-10:

```text
LOCAL_IMPLEMENTATION_COMPLETE
FOCUSED_AND_FULL_REGRESSION_VERIFIED
VPS_REAL_IMAGE_ACCEPTANCE_PENDING
```

Doc93 extends and consolidates:

```text
Doc51  visual consistency and reference locks
Doc55  post-generation visual inspection
Doc56  human variation and identity balance
Doc58  identity anchor and strong reference
Doc61  portrait commercial consistency
Doc66  strong-reference closure and precise retry
Doc76  foundation versus specialized-template governance
Doc84  structured appearance identity
Doc85  image-to-image reference truth
Doc86  portrait bone-structure lock
Doc87  portrait identity/style separation
Doc88  prompt mood and reference balance
Doc90  advanced reference controls
Doc91  Human Realism Plugin governance
Doc92  style-aware Human Realism tuning
```

When an earlier document or implementation phrase implies that an ordinary
portrait identity reference should automatically preserve hair, wardrobe,
lighting, scene, camera, palette, or whole-image style, Doc93 wins.

When an earlier document describes a user-selected generated output as a
combined identity-and-style anchor, Doc93 narrows that rule:

```text
uploaded truth sources keep their truth ownership
selected generated outputs provide approved direction support
the current explicit prompt remains authoritative for the current image
```

Short governing rule:

```text
Reference role decides what may be inherited.
Reference channels decide how strongly it may be inherited.
Explicit prompt ownership resolves conflicts.
Human Realism improves rendering but never expands inheritance rights.
```

## 1. Problem Statement

V3 already has the correct architectural components:

```text
Project and Job context
Reference Role Analyzer
Strong Reference Binding
Portrait Identity modules
Structured Appearance modules
Human Realism Plugin
Visual Capability Cluster
Provider prompt compiler
Vision review and bounded retry
```

The current weakness is not missing architecture. It is contract drift between
those components.

Several legacy rules still combine these concepts:

```text
person identity
hair direction
wardrobe family
lighting language
camera language
whole-image style
```

That coarse lock was useful before V3 had separate truth, identity, appearance,
style, and review modules. It is now too broad.

Typical failure:

```text
User uploads a portrait to preserve the same person.
Current prompt asks for a different styling, wardrobe, light, color, and scene.
V3 preserves the face, but also carries source-photo warmth, hair, wardrobe,
or photographic atmosphere into the new image.
```

This is a reference inheritance boundary failure. It is not primarily a Human
Realism failure.

## 2. Product Principle

For an ordinary portrait identity reference:

```text
Identity comes from the reference.
Direction comes from the current prompt.
```

The ordinary portrait reference defaults are:

```text
hard inherit:
  underlying face geometry
  facial-feature relationships
  recognizable age direction
  recognizable person identity

medium inherit:
  body identity direction when visible and relevant
  natural complexion / ethnicity direction

soft inherit only when the prompt is silent:
  broad hair length or color direction

prompt owned by default:
  makeup
  hair styling and hair arrangement
  wardrobe
  accessories
  lighting
  color grade
  scene
  background
  camera and composition
  mood and art direction
```

The user must be able to request a new styling direction without losing the
person. The system must preserve the same person inside the requested image,
not preserve the old photograph around the person.

## 3. Scope

Doc93 applies to every V3 path that consumes reference assets, including:

```text
General Template
E-Commerce Template
future Photography Template
future Brand / IP Template
future New Media Template
project continuation
selected-output continuation
uploaded image-to-image generation
single image generation
multi-image suites
```

Doc93 is not tied to any one visual genre, culture, era, platform, wardrobe, or
prompt example.

It must work for:

```text
modern portrait restyling
studio portrait restyling
lifestyle portrait restyling
editorial portrait restyling
costume or fashion restyling
product-on-person scenes
same-person series generation
same-outfit series generation when explicitly requested
```

## 4. Non-Goals

Doc93 does not:

```text
move identity rules into Central Brain
move reference governance into Human Realism
create a second reference registry
replace Project Context
replace Strong Reference Binding
replace Portrait Identity
replace Product Identity
replace Structured Appearance
replace template-specific suite directors
add mandatory expert controls to the beginner UI
```

## 5. Architecture Decision

The existing V3 architecture remains:

```text
Central Brain
  -> Project / Job context
      -> Visual Capability Cluster
          -> Reference Role Analyzer
          -> Reference Channel Policy Module       [new child module]
          -> Portrait / Product / Appearance truth modules
          -> Human Realism Plugin
          -> Mode / Suite Director
          -> Provider Prompt Compiler
          -> Vision Review / Bounded Retry
```

The only new architectural unit is one V3-native child module under the
existing Visual Capability Cluster:

```text
shared_capabilities/visual_cluster/reference_channel_policy.py
```

Recommended module id:

```text
reference_channel_policy
```

This is a contract and policy resolver, not a second identity module.

## 6. Ownership Boundaries

### 6.1 Central Brain

Central Brain may infer structured intent such as:

```text
the prompt explicitly changes hair
the prompt explicitly changes wardrobe
the prompt explicitly changes light or color
the prompt explicitly preserves the same outfit
the prompt explicitly treats a reference as style guidance
```

Central Brain must not directly write final inheritance rules into provider
prompts. It emits structured intent only.

### 6.2 Reference Role Analyzer

The analyzer decides what an asset is:

```text
portrait_identity_reference
product_identity_reference
structured_appearance_reference
style_reference
scene_reference
composition_reference
brand_asset_reference
negative_reference
generic_reference
```

The role is an input to policy. A filename, upload order, or visual similarity
must not silently convert a portrait identity reference into a style reference.

### 6.3 Reference Channel Policy Module

This module decides:

```text
which channels each reference may influence
the maximum strength per channel
which channels are prompt owned
which channels are explicitly locked by the user
which inheritance channels are blocked
how multiple references are merged
```

It is the sole authority for channel inheritance.

### 6.4 Portrait Identity

Portrait Identity owns:

```text
same-person recognizability
underlying bone structure
face width / length relationship
temple-cheek-jaw contour
cheek volume
eye shape and spacing
eyebrow-eye relationship
nose-mouth relationship
mouth and lip scale
jaw / chin direction
age direction
body identity direction when relevant
```

Portrait Identity does not own source lighting, source wardrobe, source scene,
or source whole-image style.

### 6.5 Structured Appearance

Structured Appearance owns clothing or appearance structure only when one of
these conditions is true:

```text
the asset is explicitly classified as a structured appearance reference
the user explicitly requests the same outfit / garment / styling asset
the active specialized template requires product or garment truth
the user selects an output specifically to continue the same appearance asset
```

An ordinary portrait identity upload must not activate a hard structured
appearance lock by itself.

### 6.6 Human Realism Plugin

Human Realism owns:

```text
real-camera human rendering
skin texture and highlight response
anti-AI-face guidance
natural eyes and expression
age-appropriate child/model realism
beautiful realism balance
human proportion realism
```

Human Realism must not:

```text
promote source hair to hard identity truth
promote source wardrobe to identity truth
promote source lighting or color to identity truth
promote a portrait upload to style guidance
change reference-channel priority
```

Human Realism may contribute artifact-specific do-not-inherit guidance such as
plastic skin or synthetic highlights. That does not grant style inheritance.

### 6.7 Provider Prompt Compiler

The provider compiler consumes the resolved policy. It must not invent broader
inheritance rules with hard-coded prose.

### 6.8 Vision Review And Retry

Review decides whether the result respected:

```text
identity truth
product / appearance truth
prompt-owned channels
approved visual anchors
Human Realism quality
```

Retry is issue-specific. Identity repair must not automatically increase style
inheritance.

## 7. Core Contracts

### 7.1 ReferenceChannelStrength

Canonical values:

```text
hard
medium
soft
prompt_owned
off
```

Meaning:

| Value | Meaning |
|---|---|
| `hard` | Must remain recognizable and must survive generic prompt wording. |
| `medium` | Preserve direction unless an explicit prompt instruction conflicts. |
| `soft` | Use only when the prompt and stronger references are silent. |
| `prompt_owned` | The current prompt controls this channel by default. |
| `off` | This reference must not influence the channel. |

### 7.2 ReferenceChannelPolicy

Future code contract:

```python
class ReferenceChannelPolicy(BaseModel):
    policy_id: str
    project_id: str | None = None
    job_id: str | None = None
    source_asset_id: str
    source_role: str

    identity_geometry: str = "off"
    body_identity: str = "off"
    natural_complexion_direction: str = "off"
    hair_direction: str = "prompt_owned"
    makeup_style: str = "prompt_owned"
    wardrobe_structure: str = "prompt_owned"
    accessory_system: str = "prompt_owned"
    product_identity: str = "off"
    lighting_color: str = "prompt_owned"
    scene_background: str = "prompt_owned"
    camera_composition: str = "prompt_owned"
    mood_art_direction: str = "prompt_owned"
    style_finish: str = "prompt_owned"

    prompt_owned_channels: list[str] = []
    explicit_user_locks: list[str] = []
    blocked_inheritance_channels: list[str] = []
    allowed_reference_contributions: list[str] = []
    conflict_resolutions: list[dict] = []
    metadata: dict = {}
```

The exact model name may follow existing contract naming, but the channel
semantics are mandatory.

### 7.3 PromptOwnershipDecision

Future code contract:

```python
class PromptOwnershipDecision(BaseModel):
    explicit_channels: list[str] = []
    preserve_requests: list[str] = []
    change_requests: list[str] = []
    explicit_style_reference_ids: list[str] = []
    explicit_identity_reference_ids: list[str] = []
    explicit_appearance_reference_ids: list[str] = []
    confidence_by_channel: dict[str, float] = {}
    evidence_by_channel: dict[str, list[str]] = {}
```

Central Brain may produce this decision. The Visual Capability Cluster must
also provide deterministic fallback extraction when LLM output is unavailable.

### 7.4 ResolvedReferencePolicyPackage

The cluster should expose one merged package:

```python
class ResolvedReferencePolicyPackage(BaseModel):
    project_id: str | None = None
    job_id: str | None = None
    policies: list[ReferenceChannelPolicy] = []
    prompt_ownership: PromptOwnershipDecision
    effective_channel_owners: dict[str, str] = {}
    provider_prompt_rules: list[str] = []
    provider_negative_rules: list[str] = []
    review_targets: list[str] = []
    retry_issue_map: dict[str, list[str]] = {}
    user_visible_summary: list[str] = []
    metadata: dict = {}
```

Downstream modules consume this package rather than re-deriving ownership.

## 8. Default Profiles By Reference Role

### 8.1 Ordinary Portrait Identity Reference

```text
identity_geometry: hard
body_identity: medium when visible and relevant
natural_complexion_direction: medium
hair_direction: soft
makeup_style: prompt_owned
wardrobe_structure: prompt_owned
accessory_system: prompt_owned
lighting_color: prompt_owned
scene_background: prompt_owned
camera_composition: prompt_owned
mood_art_direction: prompt_owned
style_finish: prompt_owned
```

### 8.2 Product Identity Reference

```text
product_identity: hard
lighting_color: prompt_owned
scene_background: prompt_owned
camera_composition: prompt_owned
style_finish: prompt_owned
```

Product truth includes shape, proportions, material, surface, packaging,
pattern, label, and logo placement when visible. It does not include source
lighting or source background by default.

### 8.3 Structured Appearance Reference

```text
wardrobe_structure: hard or medium according to explicit user intent
accessory_system: medium or hard when part of the specified appearance asset
identity_geometry: off unless the same asset is also explicitly a portrait truth source
lighting_color: prompt_owned
scene_background: prompt_owned
camera_composition: prompt_owned
```

### 8.4 Explicit Style Reference

```text
style_finish: medium or hard according to explicit user intent
lighting_color: medium unless the user requests exact lighting
camera_composition: soft or medium
identity_geometry: off
wardrobe_structure: off
product_identity: off
```

### 8.5 Explicit Scene Reference

```text
scene_background: medium or hard
camera_composition: medium when spatial continuity is requested
lighting_color: medium when scene light is part of the request
identity_geometry: off
wardrobe_structure: off
```

### 8.6 Selected Generated Output

A selected output is not automatically every kind of truth.

Default selected-output policy:

```text
approved composition / craft / tone support: medium
identity replacement: off when uploaded identity truth exists
product replacement: off when uploaded product truth exists
prompt conflict override: off
whole-image clone pressure: off
```

The user may explicitly select it as:

```text
same-person identity continuation
same-product continuation
same-appearance continuation
style continuation
scene continuation
```

That explicit selection changes only the named channels.

## 9. Prompt Ownership Resolution

### 9.1 Explicit Prompt Wins Its Channels

When the current prompt explicitly specifies a channel, that channel becomes
prompt owned unless the user also explicitly locks a conflicting reference.

Examples of explicit channels:

```text
hair style or hair color
makeup direction
wardrobe, garment, costume, or styling
lighting direction
color grade
background or location
camera angle, lens, crop, or composition
mood or art direction
```

Generic words such as `beautiful`, `premium`, `young`, `commercial`, or
`cinematic` must not replace identity geometry. They may control styling and
art direction only.

### 9.2 Explicit Preserve Request

If the user explicitly asks to keep a channel, the policy may strengthen it:

```text
keep the same hairstyle
keep the same outfit
keep this exact makeup
keep the same lighting setup
keep the same background
keep the same camera composition
```

The strengthening applies only to the named channel.

### 9.3 Explicit Change Request

If the user explicitly asks to change a channel, source inheritance for that
channel is blocked:

```text
change hairstyle
replace clothing
use a different scene
use colder light
change makeup
use a new camera angle
```

The result must still preserve any independent hard truth, such as person or
product identity.

### 9.4 Prompt Silence

When the prompt is silent:

```text
hard truth remains hard
medium truth may continue
soft direction may guide continuity
prompt-owned channels may use current project goal and template defaults
```

Prompt silence must not convert an ordinary portrait upload into whole-image
style guidance.

## 10. Conflict Resolution Order

Canonical order by channel:

```text
1. explicit user instruction for the current job
2. explicit user lock for the named channel
3. uploaded truth source for its allowed truth channel
4. selected output explicitly assigned to that channel
5. current Project confirmed direction
6. Brand Memory confirmed direction
7. template / mode defaults
8. generic fallback
```

Identity-specific clarification:

```text
explicit prompt style words do not outrank uploaded identity geometry
explicit prompt hair / wardrobe / light / scene instructions do outrank soft
or blocked inheritance from an ordinary portrait reference
```

Product-specific clarification:

```text
explicit scene and lighting requests do not outrank product identity truth
explicit redesign requests require explicit user intent and must not be inferred
```

## 11. Advanced Controls Semantics

Existing beginner-facing controls remain. No new mandatory UI is required.

### 11.1 Preserve Person Identity

`preserve_person_identity=true` means:

```text
identity_geometry = hard
body_identity = medium when relevant
natural_complexion_direction = medium
```

It must not implicitly mean:

```text
hair = hard
makeup = hard
wardrobe = hard
lighting = hard
scene = hard
style = hard
```

Recommended user copy:

```text
Prioritize the same person's appearance.
Keep the recognizable face and identity while styling and scene follow the
current request.
```

### 11.2 Preserve Product Appearance

This control strengthens product identity only. It does not preserve source
background, lighting, or composition unless separately requested.

### 11.3 Preserve Scene Consistency

This control strengthens scene and spatial continuity. It does not strengthen
person or product identity by itself.

### 11.4 Future Optional Controls

Future specialized templates may expose optional controls such as:

```text
keep the same outfit
keep the same hair styling
keep the same lighting setup
```

These controls must map to separate channels. They must not be folded back into
person identity.

## 12. Project Context And Memory Rules

### 12.1 Uploaded Reference Assets

Persist:

```text
asset role
truth layers
channel policy
explicit user purpose
active / inactive state
```

Do not persist an inferred whole-image style lock for an ordinary portrait
identity upload.

### 12.2 Selected Outputs

Only selected outputs may become positive continuation anchors.

Selection alone provides medium approved visual support. It does not erase
uploaded truth-source priority and does not override a new explicit prompt.

### 12.3 Project Confirmed Direction

Confirmed project direction may guide prompt-silent channels. It must yield to
new explicit current-job instructions.

### 12.4 Brand Memory

Brand Memory remains soft or medium confirmed guidance. It must not silently
change person identity or product truth.

## 13. Provider Prompt Ordering

Canonical provider prompt order:

```text
1. current user goal and explicit prompt-owned channels
2. hard uploaded truth sources for their allowed channels
3. explicit user locks
4. selected approved output guidance for assigned channels
5. project / brand continuity guidance
6. Human Realism rendering guidance
7. mode / suite role guidance
8. compact negative guidance
9. retry patch, only on retry
```

Provider wording for an ordinary portrait identity reference should remain
compact:

```text
Use the uploaded portrait as same-person identity truth.
Preserve underlying face geometry and facial-feature relationships.
Follow the current prompt for hair styling, makeup, wardrobe, lighting, color,
scene, camera, mood, and art direction unless the user explicitly locks one of
those channels to a reference.
```

Forbidden provider behavior:

```text
adding source light to identity truth
adding source wardrobe category to identity truth
adding source whole-image mood to identity truth
describing an identity-only reference as an identity-and-style anchor
re-deriving channel ownership from filename or role after policy resolution
```

### 13.1 Provider Reference Evidence

Prompt ownership must also govern which pixels are sent upstream. Text rules
alone are insufficient when an identity-only reference contains a strong old
hairstyle, wardrobe, palette, lighting setup, or background.

For an ordinary portrait identity reference:

```text
deduplicate byte-identical references after normalizing identity-role aliases
create a tight provider-only head-and-face identity crop
neutralize most color in that identity crop
reduce old-scene context through the tight crop without synthesizing a matte
send the focused identity crop instead of the full old frame
record suppressed full-frame identity source ids in provider metadata
```

Do not place identity evidence on an artificial feathered or flat-color
background. Live gateway acceptance proved that such synthetic identity cards
can be rejected even when an ordinary JPEG crop succeeds. Compatibility takes
priority: preserve valid image geometry, use the tighter crop and near-neutral
color only, and let channel policy prevent old-scene inheritance.

The focused crop must remain gateway-valid. If its short edge falls below 512
pixels, upscale that same tight crop proportionally to a 512-pixel short edge
before encoding. Do not widen the crop or restore old-scene pixels. This keeps
identity evidence narrow while satisfying gateways that reject smaller edit
inputs with only a generic `400 / openai_error` wrapper.

Semantic routing must also remain subject-aware. A portrait detail such as
manicure, makeup, hair, or skin must not activate a local beauty-service lane
unless the request also carries explicit service intent such as a salon,
booking, store opening, offer, package, price, or treatment. Provider failure
metadata records the exact final provider-prompt character count so gateway
rejections can be distinguished from image-input failures without logging the
private prompt itself.

Provider prompt normalization is not user-prompt compression. Preserve the
complete user/LLM visual direction and every unique user constraint. Remove
only framework-generated copies already owned by the role director, Doc93
reference policy, identity contract, or negative section. Review priorities
and pass conditions stay in the post-generation reviewer; only generation
guidance enters the image provider. Exact duplicate lines are normalized once,
and no default character cap or arbitrary truncation is introduced.

If an OpenAI-compatible gateway wraps a reference-image upstream rejection as
`400 / bad_response_status_code / openai_error`, classify only that generic
wrapper as transient and allow one fresh provider request. Explicit malformed
input, unsupported media, authentication, policy, and configuration failures
remain non-retryable. The retry budget stays bounded and never becomes a loop.

The full original remains available in project history and is never modified.
It returns to provider input when the resolved policy explicitly assigns hair,
wardrobe, appearance, lighting, scene, camera, mood, or style channels to that
reference. Product truth and structured appearance truth continue to receive
their appropriate full or focused evidence.

This rule prevents duplicate visual weighting and prevents full-frame pixels
from silently defeating a correct textual channel policy.

For real reference-conditioned jobs in `standard` or `strict` quality mode,
post-generation inspection defaults to the configured multimodal reviewer when
real images are required. A detected prompt-owned channel leak enters the
existing bounded retry loop. Standard mode retries at most once; strict mode
retries at most twice. Explicit disable or inspection-mode metadata still wins.

## 14. Review Contract

Review must score independent dimensions:

```text
identity fidelity
product / appearance fidelity
prompt-owned channel obedience
reference-role correctness
style-anchor compliance
Human Realism quality
commercial finish
```

An image may fail even when it is attractive and identity-consistent if the
reference source polluted prompt-owned styling.

### 14.1 Required Issue Codes

Add or normalize:

```text
source_hair_overinherited
source_makeup_overinherited
source_wardrobe_overinherited
source_lighting_overinherited
source_color_grade_overinherited
source_scene_overinherited
source_camera_overinherited
source_whole_style_overinherited
reference_used_as_style_when_identity_only
prompt_owned_channel_ignored
selected_anchor_overrode_current_prompt
structured_appearance_lock_misapplied
```

Existing identity issue codes remain independent:

```text
identity_drift
same_type_not_same_person
bone_structure_drift
eye_shape_or_spacing_drift
nose_mouth_relationship_drift
jaw_chin_direction_drift
```

Existing Human Realism issue codes remain independent:

```text
ai_face_render
plastic_skin
over_smoothed_skin
doll_like_face
template_smile
wax_skin_highlight
```

## 15. Retry Contract

Retry must repair only the failing channels.

### 15.1 Identity Drift

```text
strengthen identity geometry
preserve current prompt-owned styling
do not copy source lighting or wardrobe
do not turn the retry into a face-only restoration frame
```

### 15.2 Source Style Leakage

```text
keep the current identity strength
block the leaked source channels
restore current prompt hair / makeup / wardrobe / light / scene / camera
do not increase whole-image reference strength
```

### 15.3 Appearance Drift

```text
strengthen structured appearance only when that truth source is valid
do not strengthen person identity, source light, or source scene unnecessarily
```

### 15.4 Human Realism Failure

```text
repair skin, eyes, expression, light response, and real-camera quality
do not change channel ownership
do not make the reference more stylistically dominant
```

### 15.5 Retry Guardrail

If identity repair and prompt-owned style obedience alternate in failure:

```text
stop bounded retry at the configured limit
preserve all attempts internally
surface only final-delivery outputs to beginner UI
record the conflict for advanced workflow review
```

## 16. Implementation Placement

### 16.1 New File

```text
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/reference_channel_policy.py
```

Owns:

```text
ReferenceChannelPolicyModule
PromptOwnershipResolver
reference-role default profiles
channel conflict resolution
merged policy package
```

### 16.2 Contracts

Extend:

```text
shared_capabilities/visual_cluster/contracts.py
```

Add the contracts from Section 7 using existing Pydantic conventions.

### 16.3 Visual Cluster Orchestration

Update:

```text
shared_capabilities/visual_cluster/module.py
```

Required order:

```text
resolve reference roles
build prompt ownership decision
resolve channel policies
build truth / identity / appearance modules under those policies
build Human Realism independently
compile closure and role plans from the resolved package
build review contract
```

### 16.4 Portrait Identity

Update:

```text
shared_capabilities/visual_cluster/portrait_identity.py
```

Keep bone-structure identity logic. Remove responsibility for deciding whether
lighting, wardrobe, scene, or whole-image style should continue.

### 16.5 Strong Reference Closure

Update:

```text
shared_capabilities/visual_cluster/doc66_closure.py
```

Closure must consume `ResolvedReferencePolicyPackage`. It must not synthesize
coarse person rules such as face + hair + wardrobe + light from subject type
alone.

### 16.6 Provider Compiler

Update:

```text
generation_router/providers.py
```

Remove or replace hard-coded person inheritance phrases. Provider prompt text
must come from resolved policy rules.

### 16.7 Project Mode

Update:

```text
project_mode/service.py
```

Persist and expose channel policy metadata. Keep selected-output style anchors
separate from uploaded truth sources.

### 16.8 Review And Product API

Update:

```text
shared_capabilities/visual_cluster/vision_inspector.py
product_api/service.py
```

Add channel-specific issue handling and retry patches. Product API may route
issue data but must not become the policy owner.

### 16.9 Human Realism

Audit:

```text
shared_capabilities/visual_cluster/human_photorealism.py
shared_capabilities/visual_cluster/casebook_recipes.py
```

Remove any wording that grants broad style inheritance to identity references.
Keep anti-AI rendering and artifact do-not-inherit behavior.

## 17. Migration Of Legacy Rules

The following legacy phrases are compatibility debt when applied to ordinary
portrait identity references:

```text
face / hair / outfit / camera / lens / lighting all locked by default
identity and style anchor
preserve broad hair or wardrobe direction, and light
keep wardrobe category coherent unless prompt asks otherwise
same appearance asset structure whenever a person reference exists
keep selected person's vibe, hair, outfit direction, camera, and lighting
```

Migration rule:

```text
identity terms -> Portrait Identity
product terms -> Product Identity
explicit garment terms -> Structured Appearance
explicit style terms -> Style Reference policy
explicit scene terms -> Scene Reference policy
real-camera rendering terms -> Human Realism
current-job direction -> Prompt Ownership
```

Do not delete older suite-continuity requirements where the user explicitly
selected a same-outfit or same-style continuation. Re-scope those requirements
to explicit channels.

## 18. Frontend Contract

No new mandatory form fields are required.

Desktop and H5 may keep the current Advanced controls. Update copy only where
needed so beginner users understand the result:

```text
Prioritize the same person's appearance
Keep the same recognizable person; styling and scene follow this request.
```

Do not expose:

```text
channel enum names
policy ids
truth layer ids
provider prompt rules
issue-code names
```

Advanced workflow detail may explain in beginner language:

```text
Kept: the same person's recognizable face.
Changed: styling, light, scene, and camera according to this request.
```

## 19. Compatibility Matrix

| Existing document / module | Doc93 compatibility decision |
|---|---|
| Doc51 / 55 legacy coarse locks | Retained only for explicitly assigned channels; ordinary portrait default is superseded. |
| Doc56 human variation | Natural variation remains; `identity and style anchor` wording is narrowed by source role and channel policy. |
| Doc58 strong reference | Strong identity remains; style / outfit / light require explicit channels. |
| Doc61 commercial consistency | Consistency remains goal-specific; prompt-directed changes are not drift. |
| Doc66 closure | Remains closure mechanism; channel ownership must come from Doc93. |
| Doc76 placement governance | Fully compatible. Doc93 is a shared foundation child module. |
| Doc84 structured appearance | Fully compatible when an explicit appearance truth source exists. Ordinary portraits must not activate it by default. |
| Doc85 truth layering | Extended with per-channel strength and ownership. |
| Doc86 bone lock | Fully compatible; bone lock remains hard identity geometry. |
| Doc87 identity/style separation | Preserved and operationalized. Doc93 is the current implementation authority. |
| Doc88 balance | Preserved; prompt ownership and selected anchors are now channel-specific. |
| Doc90 advanced controls | Preserved; person identity control semantics are narrowed to identity channels. |
| Doc91 Human Realism | Preserved; inheritance governance remains outside Human Realism. |
| Doc92 style-aware realism | Preserved; style-aware rendering cannot expand reference inheritance. |

## 20. Test Plan

### 20.1 Contract Tests

```text
ordinary portrait -> identity hard, styling prompt-owned
product reference -> product hard, scene/light prompt-owned
appearance reference -> garment hard only when explicit
style reference -> style channels active, identity off
scene reference -> scene active, identity off
```

### 20.2 Prompt Ownership Tests

```text
explicit new hairstyle overrides soft source hair
explicit new wardrobe blocks ordinary portrait wardrobe inheritance
explicit new lighting blocks source lighting
explicit same outfit strengthens structured appearance
generic beauty wording cannot replace identity geometry
prompt silence does not create whole-image style inheritance
```

### 20.3 Provider Prompt Tests

For an ordinary portrait identity reference, final provider prompts must:

```text
contain same-person identity truth
contain current-prompt styling ownership
not contain source-light inheritance
not contain default wardrobe-category lock
not call the portrait an identity-and-style anchor
```

### 20.4 Review And Retry Tests

```text
source lighting leakage -> source_lighting_overinherited
source wardrobe leakage -> source_wardrobe_overinherited
identity-only reference used as style -> reference_used_as_style_when_identity_only
identity drift retry preserves current prompt-owned channels
Human Realism retry does not change channel policy
```

### 20.5 Cross-Template Tests

```text
General portrait uses identity-only defaults
E-Commerce model scene keeps person and product truth independent
future Photography template may add explicit outfit / lighting channels
template-specific role planning does not rewrite foundation ownership
```

### 20.6 Project Continuation Tests

```text
uploaded identity truth remains highest identity source
selected output supplies medium approved direction only
new explicit prompt overrides selected-output style channels
unselected outputs never become positive anchors
project switching never leaks channel policies
```

### 20.7 Real Visual Acceptance

Use the same uploaded identity across multiple clearly different prompts:

```text
different hair styling
different makeup
different wardrobe
different light and color grade
different scene
different camera language
```

Acceptance:

```text
same person remains recognizable
bone structure and facial-feature scale remain stable
prompt-owned styling clearly changes
source lighting and wardrobe do not leak by default
Human Realism remains stable
commercial attractiveness does not regress
```

## 21. Audit Commands

Document audit:

```bash
rg -n "Doc93|Reference Channel Policy|prompt ownership" AGENTS.md alchemy_creative_agent_3_0/README.md alchemy_creative_agent_3_0/docs
rg -n "face/hair/outfit|identity and style anchor|broad hair.*wardrobe|wardrobe.*lighting|and light" alchemy_creative_agent_3_0/docs alchemy_creative_agent_3_0/app
git diff --check -- AGENTS.md alchemy_creative_agent_3_0/README.md alchemy_creative_agent_3_0/docs
```

Focused implementation verification:

```bash
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_doc93_reference_channel_policy.py -q
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_doc85_image_to_image_reference_truth.py -q
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_doc86_portrait_bone_identity_lock.py -q
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_doc87_portrait_reference_identity_style_separation.py -q
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_doc88_portrait_reference_balance.py -q
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_doc90_general_advanced_reference_controls.py -q
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_human_photorealism_layer.py -q
```

## 22. Implementation Sequence

Implement in this order:

```text
Phase 1  Add contracts and reference-channel child module
Phase 2  Resolve prompt ownership and role profiles
Phase 3  Integrate Portrait Identity / Product / Appearance truth
Phase 4  Replace coarse closure and provider hard-coded rules
Phase 5  Persist policy in Project Context
Phase 6  Add review issue codes and channel-specific retry
Phase 7  Audit Human Realism for inheritance leakage
Phase 8  Update beginner-facing copy without adding complexity
Phase 9  Run focused, full, cross-template, and real-image acceptance
```

Do not begin by changing provider prompt strings alone. The structured policy
must exist first so every downstream consumer uses the same decision.

## 23. Definition Of Done

Doc93 is implemented only when all are true:

```text
1. A reference asset has an explicit role and channel policy.
2. Ordinary portrait references default to identity truth only.
3. `preserve_person_identity` strengthens identity geometry only.
4. Prompt-owned hair, makeup, wardrobe, light, scene, camera, and mood are not
   overridden by ordinary portrait references.
5. Explicit style / appearance / scene references still work.
6. Selected outputs cannot replace uploaded truth or override a new prompt.
7. Provider prompts consume one resolved policy package.
8. Human Realism does not control reference inheritance.
9. Review detects source-style leakage independently from identity drift.
10. Retry repairs only failing channels.
11. General, E-Commerce, and future templates use the same foundation contract.
12. Focused and full regression tests pass.
13. Real visual tests show same-person identity under clearly different styling,
    lighting, scene, and camera directions.
```

Final architectural rule:

```text
Keep the V3 framework.
Add one native reference-channel policy child module.
Move inheritance ownership into structured contracts.
Keep identity, appearance, realism, style, and prompt direction separate.
```

## 24. Local Implementation Audit Record

The local implementation has completed Phases 1-8 and the automated portion
of Phase 9. The live VPS comparison remains the final acceptance gate.

Implemented placement:

```text
Visual Capability Cluster
  -> Reference Channel Policy child module
  -> Portrait Identity / Product Truth / Structured Appearance consumers
  -> Human Realism consumer with no inheritance authority
  -> Provider policy package consumer
  -> Real visual review with compressed reference evidence
  -> Channel-specific bounded retry

Project Context persists the resolved package.
Central Brain fallback is channel-safe and does not create a second policy.
Templates may request channels but do not own the foundation resolver.
```

Local verification on 2026-07-10:

```text
Doc93 focused tests: passed
V3 full suite: 370 passed
frontend/API shell: 89 passed
root suite: 138 passed
desktop/mobile JavaScript syntax: passed
Python compile audit: passed
git diff check: passed
```
