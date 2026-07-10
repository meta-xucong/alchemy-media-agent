# 62 V3 Portrait Suite Director And Natural Role Separation Spec

Doc93 compatibility note:

```text
Portrait suite roles remain valid. Broad hair or wardrobe continuity is not a
default identity requirement; it applies only when those channels are explicit
suite constraints. Prompt-directed styling changes must remain available while
the same person's identity geometry stays recognizable.
```

## 1. Status And Authority

Doc62 is the implementation optimization layer after Doc61.

Authority chain:

```text
Doc50:
  Reusable visual enhancement belongs in the V3 native Visual Capability
  Cluster.

Doc54:
  Owns the four user-facing generation modes.

Doc56:
  Owns human identity consistency with natural variation.

Doc58:
  Owns selected-output identity anchors and strong reference continuation.

Doc59:
  Owns mode-aware role differentiation.

Doc60:
  Owns E-Commerce product-suite slot fidelity and label/logo QA.

Doc61:
  Owns portrait real-validation protocol and Lovart benchmark wording.

Doc62:
  Owns stronger portrait-suite art direction inside the General Template.
```

Doc62 does not replace the V3 central brain, Project Mode, ScenarioRuntime,
Product API, or provider layer. It must be implemented inside the V3 native
Visual Capability Cluster, primarily through the mode-aware role director and
provider-facing role prompts.

Doc62 must not change E-Commerce behavior. Doc60 remains the authority for
product suites.

## 2. Problem To Fix

Doc61 proved that V3 can:

```text
create a project
generate a portrait anchor
select the anchor
use it as a hard identity reference
continue the project into a four-image portrait suite
```

The remaining gap is visual art direction:

```text
identity continuity is good
commercial finish is good
role metadata is present
but several portrait outputs still look like very similar smile/head-angle
variants instead of a fully directed commercial shoot
```

Lovart-grade portrait suites need a stronger balance:

```text
same person, same styling world, same color and lighting language
different expression lane, gaze lane, pose lane, crop lane, and scene duty
```

## 3. Scope

Allowed:

```text
strengthen General Template portrait delivery-suite role recipes
add role-specific expression, gaze, pose, hand, crop, camera, and scene rules
add provider-facing prompt guidance for those role rules
add regression tests proving role prompts are more differentiated
run real portrait generation and compare against Doc61
```

Not allowed:

```text
call V1/V2 runtime code
replace the central brain
add portrait-only logic directly into the central framework
weaken selected-output strong references
weaken Doc56 identity consistency
change Doc60 E-Commerce slot contracts
raise retry budgets
auto-write Brand Memory
```

## 4. Runtime Design

Doc62 stays under this existing path:

```text
Project
  -> General Template
      -> ScenarioRuntime
          -> Shared Capability Registry
              -> Visual Capability Cluster
                  -> ModeAwareRoleDirector
                  -> HumanNaturalVariationPolicy
                  -> ProjectIdentityAnchorBuilder
                  -> StrongReferenceContinuationPlanner
          -> Product API generation
              -> ProductionImageGenerationProvider
```

The central brain may consume the enriched visual cluster facts, but the new
portrait role specialization must live in the visual cluster.

## 5. Portrait Delivery-Suite Contract

For `mode = delivery_suite` and `subject_type = character`, the first four
roles must behave as a directed commercial portrait shoot.

### 5.1 Cover Hero

Purpose:

```text
main cover image with the clearest first impression
```

Expected difference:

```text
direct or near-camera gaze
open shoulders or clean hero posture
medium portrait or medium-close crop
bright confident expression
clean cover-safe negative space
```

Must avoid:

```text
same tight face crop as subject focus
same side profile as angle role
same wide environmental distance as scene role
```

### 5.2 Subject Focus

Purpose:

```text
closer identity and beauty detail frame
```

Expected difference:

```text
closer face and upper-body crop
softer expression or slightly off-camera gaze
shallow depth of field
hair texture, skin light, styling detail, or hand near hair
```

Must avoid:

```text
same cover posture
same wide context crop
same front-facing smile as every other image
```

### 5.3 Side Or Three-Quarter Angle

Purpose:

```text
clear angle variation from the same shoot
```

Expected difference:

```text
visible body turn
side or three-quarter head angle
gaze away from camera or toward scene
hair movement and different shoulder line
medium crop with a different face plane
```

Must avoid:

```text
front-facing duplicate
same smile/head angle as the anchor
identity drift caused by excessive profile change
```

### 5.4 Wide Scene Or Context

Purpose:

```text
wider lifestyle/context frame that proves the visual world
```

Expected difference:

```text
more environment
full-body or three-quarter body scale when possible
walking, seated, leaning, or interacting with the scene
clear seaside or lifestyle context
same person direction but less headshot dominance
```

Must avoid:

```text
another close headshot
same studio-like crop
unrelated props or product objects
```

## 6. Prompt Implementation Rules

Each portrait role recipe must carry a Doc62 art-direction payload in metadata:

```text
expression_lane
gaze_lane
pose_lane
gesture_lane
subject_scale_lane
scene_depth_lane
clone_avoidance_rule
```

The production provider must expose these lanes in the final provider prompt
inside the role-specific generation contract. The wording must be positive and
actionable:

```text
Role expression lane: ...
Role gaze lane: ...
Role pose lane: ...
Role gesture lane: ...
Role subject scale: ...
Role scene depth: ...
Clone avoidance: ...
```

The role recipe must still include identity-preservation rules:

```text
same recognizable person direction
same body type and broad hair or wardrobe direction
same lighting language
```

For selected-output continuations, provider reference rules remain stronger than
prompt-only guidance.

## 7. Review And Retry Rules

Doc62 does not add pixel-level identity recognition by itself. It improves the
pre-generation role contract and gives post-generation review clearer evidence
to evaluate.

If post-generation review or mode differentiation review later detects:

```text
mode_role_duplication
delivery_suite_role_collapse
over_cloned_portrait_suite
same_face_angle_repetition
```

the retry patch should reinforce:

```text
separate expression, gaze, pose, camera distance, and scene duty by role
do not repeat the same smile/head angle/crop across most images
preserve identity through the selected reference, not by cloning the still
```

Doc62 does not raise retry attempts. Retry remains governed by Doc53.

## 8. Frontend Behavior

No new frontend controls are required.

The user still sees the existing four modes:

```text
similar candidates
delivery suite
creative exploration
format/layout adaptation
```

Doc62 only makes the default `delivery_suite` portrait output smarter.

## 9. Acceptance Tests

Focused tests must prove:

```text
General Template character delivery-suite roles include Doc62 metadata
cover, subject-focus, angle, and wide-scene roles have different expression,
gaze, pose, scale, and scene-depth lanes
provider prompt includes those lanes
identity keep rules are still present
E-Commerce Doc60 recipe roles are unchanged
```

Real validation must:

```text
run the Doc61 real portrait chain again
inspect the contact sheet
compare against the previous Doc61 run
record whether role separation improved
record remaining Lovart-grade gaps
```

## 10. Completion Criteria

Doc62 is complete when:

```text
documentation exists and is compatible with Docs 50-61
code changes stay inside the V3 visual/provider path
focused tests pass
full regression passes
real portrait generation succeeds when provider is available
new results show stronger expression/pose/crop/scene role separation than Doc61
ServerChan review notification is sent
```
