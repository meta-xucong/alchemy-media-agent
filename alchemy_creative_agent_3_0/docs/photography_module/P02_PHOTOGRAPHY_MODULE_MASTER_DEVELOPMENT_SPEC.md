# Photography Module Master Development Specification

## 1. Product Goal

The Photography Module produces image-grade commercial photography through two
input paths:

```text
text description -> professional photograph
ordinary uploaded photograph -> professional AI reshoot
```

The quality target is not achieved by a larger prompt alone. It requires
professional task interpretation, pre-production choices, camera and light
direction, scene-specific subject direction, structured shot planning,
reference ownership, real-output review, bounded rerender and best-result
selection.

## 2. Four-Axis Task Model

### 2.1 Subject And Scene: What Is Photographed

First-wave scene domains:

```text
portrait
landscape
still_life
animal
```

Later domains:

```text
fashion_beauty
food
architecture_interior
automotive
street_documentary
wedding_event
sports_action
macro
travel
```

Scene domains should compose with capture intents. Do not create one hard-coded
module for every combination.

### 2.2 Commission Intent: Why It Is Photographed

Initial commission types:

```text
single_hero
professional_session
editorial_story
commercial_image
environmental_portrait
documentary_moment
fine_art_study
reference_reshoot
```

The commission type owns the output purpose and shot-list structure. A portrait
session, magazine portrait and documentary portrait are not interchangeable.

### 2.3 Photographic Language: How It Is Photographed

The photographic language is decomposed into observable technique axes:

```text
composition geometry and visual rhythm
camera height, distance and angle
perspective compression or expansion
depth-of-field behavior
focus placement and falloff
motion freeze, blur or long-exposure behavior
lighting topology, softness, direction and ratio
exposure key and highlight/shadow treatment
color response, contrast curve and palette
texture, grain and microcontrast
subject direction and decisive-moment behavior
retouch finish and restraint
```

Equipment names may be used as planning shorthand, but the provider instruction
must express visible effects rather than relying on camera or lens tokens as
magic words.

### 2.4 Preservation Contract: What Must Not Change

Reference-owned and prompt-owned channels remain separate:

```text
person identity
non-human subject identity
product/object truth
scene/landmark truth
composition
hair and makeup
wardrobe and props
weather and time
lighting
color and finish
whole-image style
```

The default depends on the reference role, not merely on the presence of an
uploaded image.

## 3. Product Modes

### 3.1 Input Modes

```text
text_to_photo
reference_to_professional_reshoot
```

### 3.2 Reference Reshoot Strength

```text
faithful
  Preserve subject, scene and composition unless the user changes them.

professional_reshoot
  Preserve declared truth; redesign camera, light, staging and finish.

creative_reinterpretation
  Preserve only explicitly selected truth channels.
```

### 3.3 Delivery Modes

```text
single_hero
professional_set
```

The first production release should not include channel packaging, social
carousels, posters, E-Commerce listing sets or brand systems. Those belong to
their owning templates.

## 4. User Controls

Beginner-facing controls should remain limited to:

```text
scene or photography type
single image or professional set
optional uploaded references
reshoot strength when a reference is present
what must be preserved
General Photography or one manually selected named photographer profile
output count and aspect ratio
```

Advanced camera, lighting and finish controls may be optional. The default
experience uses the Brain to determine technical modules, but never to choose a
named photographer.

## 5. Named Photographer Frontend Contract

The UI must show an explicit selector with a neutral default:

```text
摄影风格：通用专业摄影（默认）
知名摄影师：未选择
```

When the user opens the named-photographer catalog, the UI may provide search,
filter, profile description, suitable scenes and availability information. A
profile activates only after a deliberate click/confirmation.

Proposed product-level request fields:

```python
photographer_profile_id: str | None = None
photographer_profile_selection_source: Literal["user_explicit_ui"] | None = None
```

The client selects a catalog ID only. The server resolves and pins the exact
profile version, catalog version, availability decision and technique checksum;
the client must not choose or override those execution versions.

These are proposed contracts, not authorization for the Photography branch to
change shared public schemas. If existing extension metadata cannot safely carry
them, submit a mainline integration request and pause that implementation point.

Activation semantics:

```python
if photographer_profile_id is None:
    selected_profile = general_photography
elif selection_source != "user_explicit_ui":
    reject_activation("named_profile_requires_explicit_ui_selection")
else:
    selected_profile = catalog.validate_and_pin(photographer_profile_id)
```

The Brain receives the resolved immutable binding. It does not receive authority
to change it.

## 6. Runtime Architecture

```text
Photography Scenario Pack
  -> Photography input and user controls
  -> minimal task/reference understanding
  -> named-profile binding validation
  -> Central Brain Photography checkpoint
  -> VisualTaskProfile and CapabilityActivationIntent
  -> Photography TemplateCapabilityPolicy
  -> frozen CapabilityActivationPlan
  -> scene, commission and technique contributions
  -> PhotoShotSpec
  -> existing Generation Router
  -> GPT Image 2
  -> photography-aware real-output review
  -> bounded issue-specific rerender
  -> best reviewed delivery
```

Named-profile validation occurs before the Brain's photographic planning stage.
This prevents an LLM-generated profile name from becoming activation evidence.

## 7. Hot-Pluggable Module Inventory

### 7.1 Photography Template Modules

| Capability ID | Responsibility | Initial activation |
| --- | --- | --- |
| `photography_brief_direction` | Resolve scene, commission and delivery intent | Required |
| `photography_shot_list_direction` | Build differentiated image roles | Required for sets |
| `photography_camera_optics` | Camera relation, perspective, depth and motion | Required |
| `photography_lighting_direction` | Lighting topology, ratio and exposure key | Required |
| `photography_composition_direction` | Composition, crop, hierarchy and rhythm | Required |
| `photography_subject_direction` | Pose, expression, interaction and placement | Evidence-gated |
| `photography_color_finish` | Color response, contrast, grain and finish | Required |
| `photography_retouch_direction` | Scene-aware retouch restraint | Required |
| `photographer_profile_binding` | Apply one pinned named profile or General | Required |
| `photography_professional_review` | Photography issue codes and score profile | Required |

### 7.2 First-Wave Scene Directors

```text
portrait_photography_direction
landscape_photography_direction
still_life_photography_direction
animal_photography_direction
```

Exactly the evidenced scene directors activate. Mixed scenes may activate more
than one compatible director when the plan records why.

### 7.3 Shared Foundation Capabilities

Existing capabilities should be reused:

```text
reference_channel_policy
universal_visual_quality
human_realism
portrait_identity
product_identity
scene_continuity
suite_direction
commercial_quality
```

Proposed reusable gaps:

```text
photographic_capture_realism
nonhuman_subject_identity
```

They require separate foundation ownership review and proof across at least
three materially different scenes before becoming shared behavior.

## 8. Core Contracts

### 8.1 PhotographyUserControls

```text
input_mode
delivery_mode
reshoot_strength
explicit_scene_id
preservation_controls
photographer_profile_id
photographer_profile_selection_source
output_count
aspect_ratio
advanced_controls
```

### 8.2 PhotographyBrief

```text
subject_entities
scene_domain
commission_intent
audience_and_use
story_or_emotional_goal
location_and_environment
wardrobe_prop_and_set_needs
moment_and_subject_direction
delivery_roles
reference_policy_summary
profile_binding_summary
unknown_requirements
```

### 8.3 PhotoShotSpec

Each planned output has one structured specification:

```text
shot_id and role
subject and decisive moment
framing and crop
camera position and perspective effect
depth and focus behavior
motion behavior
lighting map and exposure key
palette and tone curve
surface, texture and grain
subject direction
retouch direction
immutable reference truth
allowed changes
negative constraints
review profile
```

### 8.4 PhotographerProfileBinding

```text
binding_mode: general | named
profile_id
profile_version
selection_source
catalog_version
availability_decision
technique_package_checksum
pinned_at
```

### 8.5 PhotographyReviewReport

```text
brief fidelity
composition
lighting plausibility and exposure
perspective, depth and focus
moment and subject direction
color and tonal finish
scene-specific material realism
retouch restraint
AI artifact severity
reference truth fidelity
named-profile technique compliance when active
series coherence and differentiation
professional direct-use readiness
issue codes and retryability
```

## 9. Text-To-Photo Flow

1. Preserve the complete user request.
2. Resolve scene, commission, delivery mode and constraints.
3. Resolve General Photography or validate the explicit named profile.
4. Plan scene and technique capabilities.
5. Produce one PhotoShotSpec per output role.
6. Generate candidates through GPT Image 2.
7. Review real outputs under active universal, scene and profile contracts.
8. Perform only bounded issue-specific rerenders.
9. Compare all reviewed candidates and deliver the best eligible set.

## 10. Ordinary-Photo Reshoot Flow

1. Analyze uploaded asset roles and technical condition.
2. Resolve the preservation contract channel by channel.
3. Select faithful, professional-reshoot or creative-reinterpretation mode.
4. Validate General or explicit named profile binding.
5. Keep hard identity, product or scene truth in provider input images.
6. Redesign only allowed camera, light, staging and finish channels.
7. Review reference fidelity separately from photographic quality.
8. Retry the specific failing dimension without widening reference inheritance.
9. Deliver the best reviewed full-image rerender.

## 11. Scene Director Responsibilities

### 11.1 Portrait

Owns portrait/session roles, expression and pose direction, face/body framing,
environmental relation and portrait-specific photography acceptance. It reuses
Human Realism and Portrait Identity rather than duplicating them.

### 11.2 Landscape

Owns foreground/midground/background structure, scale, atmosphere, weather,
light window, viewpoint and landscape material realism. A scene reference may
activate Scene Continuity without forcing source color or weather inheritance.

### 11.3 Still Life

Owns object grouping, surface and background relation, material emphasis,
negative space, set lighting and controlled retouch. Marketplace listing roles
remain E-Commerce-owned.

### 11.4 Animal

Owns animal behavior, gaze, body language, motion, habitat relation, safe
framing and fur/feather/scale realism. A specific pet or animal reference
requires non-human identity support rather than generic similarity wording.

## 12. Professional Set Direction

A professional set must not be the same image with superficial focal-length or
crop changes. Each role changes at least two meaningful dimensions:

```text
framing
camera relation
subject action or expression
environmental context
lighting behavior
moment or narrative purpose
```

The selected named profile, reference truth and color system remain coherent
across the set.

## 13. Cross-Template Boundaries

Photography owns photographs and photographic sessions. It does not own:

```text
E-Commerce listing and A+ packages
Brand identity systems
New Media carousels, thumbnails or content calendars
poster typography and channel layout systems
storyboard or video campaign sequences
```

Those templates may consume selected Photography outputs or activate reusable
photo capabilities through formal manifests. They must not call Photography
internals directly.

## 14. Planned File Placement

Module-owned implementation should normally live under:

```text
app/scenario_packs/photography/
  manifest.py
  contracts.py
  pack.py
  brief_director.py
  shot_list_director.py
  profile_catalog.py
  profile_binding.py
  scene_directors/
  technique_modules/
  review/
  export_packager.py

app/vertical_agents/photography_pack.py
```

Reusable foundation plugins, if accepted by mainline, belong under the existing
shared capability/plugin structure rather than inside the Scenario Pack.

## 15. UX Result Presentation

Beginner-facing results should show:

```text
final delivery images only
friendly shot-role names
General Photography or the user-selected profile name
preserved reference summary
optional folded workflow/review details
```

Do not expose capability graphs, evidence confidence, internal prompt atoms,
rights notes, retry internals or provider identifiers in the normal result view.
