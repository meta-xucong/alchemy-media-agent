# 90 V3 General Template Advanced Reference Priority Controls Spec

## 1. Purpose

Doc90 adds a beginner-friendly advanced control layer for the V3 General
Template when uploaded or selected reference images conflict with the user's new
prompt.

This document exists because recent portrait image-to-image validation exposed a
subtle but important product problem:

```text
The user uploads a reference image that already contains a person.
The new prompt also describes a person, scene, outfit, pose, and mood.
When the prompt's person wording conflicts with the uploaded face, V3 must know
which source wins.
```

Doc90 defines the General Template answer:

```text
Default to preserving the uploaded person's recognizable identity when a human
face reference is present, but keep this control inside a folded Advanced menu
so beginner users do not have to understand reference weights.
```

Short product rule:

```text
Small users see "keep the uploaded person looking like themselves".
The system sees explicit priority controls for person, product, and scene
consistency.
```

## 2. Scope

Doc90 applies only to:

```text
V3 General Template
general_creative Scenario Pack jobs
General Template project continuation jobs
General Template image-to-image / reference-image generation
```

Doc90 does not define final logic for:

```text
E-Commerce Template
Photography Template
future specialized templates
V1 / V2 / Alchemy Lab
Brand Memory automatic updates
provider routing
```

Future specialized templates may reuse the same backend field names, but their
default values and stronger template-specific behavior must be specified in
their own documents.

## 3. Compatibility And Authority

Doc90 extends:

```text
Doc36  General Template project flow
Doc50  V3-native Visual Capability Cluster
Doc66  Strong reference closure
Doc76  Foundation vs specialized-template governance
Doc85  Image-to-image reference truth
Doc86  Portrait bone-structure identity lock
Doc87  Portrait identity/style separation
Doc88  Portrait reference balance and prompt mood preservation
Doc89  Portrait photography stability test protocol
```

Doc88 remains the highest authority for portrait balance:

```text
Keep the person, keep the user's intended atmosphere, and do not fix one
dimension by breaking the other two.
```

Doc90 adds user-facing control over which dimension has priority when the
sources genuinely conflict.

If older documents imply that all uploaded references have the same kind of
influence, Doc90 wins for General Template jobs.

If older UI documents hide all reference-priority controls, Doc90 wins for the
General Template workspace only.

## 4. User-Facing Advanced Controls

The General Template workspace must expose a folded `Advanced` area.

Normal users should see only simple language. The UI must not expose terms such
as:

```text
provider
identity lock
reference weight
truth layer
prompt compiler
visual cluster
```

The Advanced area contains three options:

```text
1. 保持人物长相
2. 保持产品外观
3. 保持原图场景
```

### 4.1 保持人物长相

Default:

```text
on when the General Template job has an uploaded or selected human/person
reference image.
off when no reference image exists.
```

Beginner-facing copy:

```text
优先保留上传图里的人物长相
```

Meaning:

```text
The uploaded or selected person's bone structure and feature relationships have
priority over prompt wording that describes a generic or different-looking
person.
```

### 4.2 保持产品外观

Default:

```text
off in the General Template.
```

Beginner-facing copy:

```text
优先保留上传图里的物品外观
```

Meaning:

```text
When enabled in General Template, preserve the referenced object's silhouette,
major shape, material direction, visible pattern, label area, and distinctive
structure. This is a generic object/product preservation helper, not the
E-Commerce Template's dedicated product suite logic.
```

### 4.3 保持原图场景

Default:

```text
off in the General Template.
```

Beginner-facing copy:

```text
优先保留上传图里的背景和空间
```

Meaning:

```text
When enabled, the reference image's background, spatial layout, camera mood, and
scene continuity have priority. The new prompt can refine the same world, but
should not replace it with a new environment.
```

This must remain off by default because many General Template users upload a
person reference and then explicitly want to change the scene.

## 5. Backend Contract

General Template job creation may include:

```json
{
  "advanced_reference_controls": {
    "preserve_person_identity": true,
    "preserve_product_appearance": false,
    "preserve_scene_consistency": false
  }
}
```

Rules:

```text
Missing field means "use General Template defaults".
Unknown keys are ignored.
The field is stored in job metadata for auditability.
The field is only interpreted by the General Template path in this phase.
```

Default resolver:

```text
preserve_person_identity:
  true if at least one active uploaded/selected human-like reference exists
  false otherwise

preserve_product_appearance:
  false

preserve_scene_consistency:
  false
```

The frontend may optimistically default `preserve_person_identity=true` when any
reference file is uploaded because reliable face detection may not be available
in the browser. The backend remains the source of truth and should apply the
same default safely.

## 6. Conflict Rules

### 6.1 Person Identity On

When `preserve_person_identity=true`, priority order is:

```text
uploaded/selected person bone structure
  > prompt wording about face shape, age direction, beauty archetype, and facial
    feature relationships
  > makeup, hair styling, wardrobe, pose, lighting, scene, mood
```

Provider prompt must say, in concise language:

```text
Use the uploaded person as the exact identity source. Preserve face shape,
eye spacing, eye shape direction, nose-mouth relationship, cheek/jaw/chin
direction, age direction, and recognizable same-person impression. Prompt words
such as "oval face", "sweet East Asian style", "young woman", or other beauty
archetypes should guide makeup, styling, expression, and mood only; they must
not replace the reference person's facial geometry.
```

Allowed changes:

```text
makeup
expression
pose
gaze
head angle
hair styling when requested
wardrobe
lighting
scene
camera mood
```

Forbidden changes:

```text
turning the person into a similar-looking new model
changing face width/length relationship
changing eye spacing or eye shape direction
changing nose-mouth-chin relationship
changing jaw/chin direction
overriding reference identity with a prompt beauty archetype
```

### 6.2 Product Appearance On

When `preserve_product_appearance=true`, priority order is:

```text
uploaded/selected object/product structure
  > prompt wording about generic product category or style
  > scene, props, lighting, camera, layout
```

Provider prompt must preserve:

```text
silhouette
proportions
main material direction
visible pattern family
label/logo area when present
distinctive trims, edges, closures, or accessories
```

This option must not automatically activate E-Commerce-specific suite slots or
marketplace rules.

### 6.3 Scene Consistency On

When `preserve_scene_consistency=true`, priority order is:

```text
reference background / space / camera mood
  > prompt wording that implies a different environment
  > minor styling and atmospheric refinements
```

Provider prompt must preserve:

```text
same broad environment
same spatial relationship
same camera mood
same background density direction
same lighting family unless the prompt asks for a compatible time shift
```

This option should be used only when the user wants to keep the same world.

## 7. General Template UI Requirements

Desktop and H5 workspaces must stay beginner-friendly:

```text
Advanced controls are folded by default.
The main workspace only shows a short status line when a control is active.
The copy uses "保持..." language, not technical language.
The controls must not visually compete with the prompt, upload area, image
count, aspect ratio, or generate button.
```

Recommended UI:

```text
高级设置
  [on]  保持人物长相  上传人物图时推荐开启
  [off] 保持产品外观  需要同一个物品时开启
  [off] 保持原图场景  需要延续同一背景时开启
```

Main workspace status when a person reference exists:

```text
已优先保留上传人物长相
```

If no reference exists:

```text
上传参考图后可保持人物、物品或场景一致
```

## 8. Review And Retry Requirements

When `preserve_person_identity=true`, visual review and retry metadata must
treat these as retryable:

```text
identity_drift
identity_feature_drift
eye_shape_or_spacing_drift
nose_mouth_relationship_drift
jaw_chin_direction_drift
beauty_archetype_overrode_reference
same_type_but_different_person
```

When `preserve_product_appearance=true`, retryable issue codes include:

```text
product_identity_drift
product_silhouette_drift
label_or_pattern_drift
material_structure_drift
```

When `preserve_scene_consistency=true`, retryable issue codes include:

```text
scene_identity_drift
background_space_drift
camera_mood_drift
reference_scene_replaced
```

If live image inspection is unavailable, the job metadata must still carry the
active controls and provider prompt rules so manual review can diagnose whether
the right priority was applied.

## 9. Tests

Focused tests must cover:

```text
1. General Template job without explicit advanced controls uses defaults.
2. General Template job with uploaded reference defaults person preservation on.
3. Person preservation adds prompt rules that demote prompt face archetypes.
4. Person preservation adds identity-drift review/retry issue codes.
5. Product preservation can be enabled but remains General Template generic,
   not E-Commerce suite behavior.
6. Scene preservation can be enabled and adds scene-continuity prompt rules.
7. Advanced controls are stored in output metadata.
8. Desktop and H5 frontend include folded beginner-friendly controls and submit
   the field.
```

Regression tests must ensure:

```text
E-Commerce Template behavior is not changed by this phase.
Existing Doc85-Doc88 tests continue to pass.
The V3 Product API remains compatible when the field is absent.
```

## 10. Acceptance Criteria

This phase is accepted when:

```text
Doc90 exists and is compatible with Doc85-Doc89.
General Template can receive advanced_reference_controls.
Uploading a human/person reference defaults to preserving person identity.
The final provider prompt clearly states that prompt face archetypes cannot
replace uploaded facial geometry.
Advanced controls are available in desktop and H5 inside a folded Advanced menu.
Existing V3 tests pass.
GitHub is updated.
VPS is deployed and smoke-tested.
```

## 11. Non-Goals

Do not implement:

```text
specialized E-Commerce defaults
Photography Template defaults
new provider routing
new face-recognition service
automatic legal/biometric identity verification
new Lovart-specific UI
V1/V2 runtime dependency
```

The goal is a clean General Template control bridge:

```text
simple for users, explicit for the system, compatible with the existing V3
visual module architecture.
```
