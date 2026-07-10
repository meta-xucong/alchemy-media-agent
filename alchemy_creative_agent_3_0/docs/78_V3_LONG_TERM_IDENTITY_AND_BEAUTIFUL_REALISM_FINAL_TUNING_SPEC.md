# 78 V3 Long-Term Identity And Beautiful Realism Final Tuning

Doc93 compatibility note:

```text
Long-term identity and beautiful realism remain foundation goals. Doc93
separates their channels: same-person geometry remains stable, Human Realism
keeps the person attractive and photographed, and prompt-directed styling
changes must not be misclassified as identity drift.
```

## 1. Purpose

Doc78 is the final foundation-quality tuning plan before moving to the next
specialized-template development phase.

It focuses on the two remaining foundation gaps:

```text
1. Long-term character / subject identity consistency.
2. Beautiful but realistic human-photo quality.
```

The target is not merely "more real." The target is:

```text
recognizably the same person across a project
beautiful enough for commercial/social use
real enough to avoid obvious AI-beauty artifacts
natural enough to allow expression, pose, angle, and scene changes
```

Acceptance goal:

```text
V3 General Template foundation quality should reach 85%+ on:
identity continuity
single-image beauty
human photorealism
anti-AI-feel
skin/lighting realism
facial-feature aesthetic integrity
```

## 2. Compatibility

Doc78 extends:

```text
Doc53 bounded retry guardrails
Doc56 human natural variation
Doc58 identity anchor / strong reference loop
Doc65 human photorealism
Doc70 AI-feel reduction
Doc71 attractive-realism balance
Doc72 East Asian fair-complexion and proportion guard
Doc73 first-output identity anchor
Doc75 identity hero and strict review closure
Doc76 foundation vs specialized-template governance
Doc77 real visual review and aesthetic stability
```

Doc78 does not replace:

```text
Project Mode
ScenarioRuntime
Scenario Packs
CentralCreativeBrain
LLM Brain adapter
General Template four-mode selector
E-Commerce / Photography / Brand specialized template ownership
```

## 3. Boundary Rule

Doc78 belongs to the V3 foundation because identity continuity and beautiful
photoreal human rendering improve almost every visual project.

Allowed implementation locations:

```text
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/
alchemy_creative_agent_3_0/app/generation_router/
alchemy_creative_agent_3_0/app/product_api/ review and retry paths
alchemy_creative_agent_3_0/app/project_mode/ selected-output context packaging
```

Forbidden changes:

```text
do not add professional photography package roles to General Template
do not add ecommerce listing slots to General Template
do not put Doc78 child logic inside CentralCreativeBrain
do not bypass the Visual Capability Cluster
do not increase retry loops beyond Doc53
do not enforce one rigid beauty template across all people
```

Doc76 remains the placement authority. Doc78 only tunes foundation identity and
human visual quality.

## 4. Core Design Principle

The correct balance is:

```text
Beauty is the visual goal.
Realism is the rendering method.
Identity is the continuity contract.
Variation is allowed only outside identity-critical traits.
```

Do not treat "realistic" as:

```text
dark skin by default
tired face
unflattering expression
rough documentary harshness
random facial-feature drift
bad eyebrow or eye-shape deformation
less attractive facial proportions
```

Treat "realistic" as:

```text
real skin texture
natural light and shadow
subtle complexion variation
believable hair strands
real fabric folds
non-plastic highlights
natural facial asymmetry
camera-captured detail
```

## 5. Long-Term Subject Identity Card

Doc78 introduces the implementation target `SubjectIdentityCard`.

It is a V3 foundation object derived from:

```text
1. User-selected reference image.
2. User-uploaded face / subject reference.
3. Existing project identity anchor.
4. First high-quality generated human output only when no user anchor exists.
```

Priority:

```text
user-selected image always wins
uploaded reference wins over auto-generated anchor
project identity card wins over old unselected candidates
auto first-output anchor is only a fallback
```

The card should preserve:

```text
broad face shape
eye shape and spacing
eyebrow direction and visual temperament
nose-mouth relationship
jawline / chin direction
age impression
body type and head-body proportion
hair length / color / broad style
wardrobe category when it defines the project
overall temperament and commercial beauty direction
```

The card should allow variation in:

```text
expression
gaze
head angle
pose
gesture
camera distance
camera angle
scene
lighting micro-variation
hair movement
minor styling details
```

The card must not preserve:

```text
bad anatomy
unflattering facial drift
skin defects caused by generation
AI face artifacts
watermarks
text artifacts
over-smoothed skin
bad crop
bad expression
```

## 6. Facial-Feature Aesthetic Integrity

This section is mandatory.

The system must not sacrifice facial beauty to chase realism.

For human-photo generation, the following are identity/beauty-sensitive traits:

```text
eye shape
eye spacing
eyelid direction
eyebrow shape
eyebrow thickness and arc
nose bridge / tip relationship
mouth shape
lip fullness and natural color
jawline direction
chin scale
cheek volume
forehead-to-face proportion
face width / length ratio
neck and shoulder balance
```

The system should preserve or improve these traits toward:

```text
harmonious facial proportions
clean attractive eyebrow design
clear awake eyes
natural but flattering eyelid detail
soft facial contour without face-slimming distortion
balanced nose-mouth relationship
pleasant lip shape without plastic gloss
attractive jaw/chin direction without V-line filter
fresh expression without template smile
```

The system must avoid:

```text
ugly eyebrow shape
drooping or mismatched brows
random eyebrow thickness drift
asymmetric eyes caused by rendering failure
sleepy or dull eye expression
unflattering nose or mouth drift
flattened facial attractiveness
face-slimming geometry
enlarged beauty-filter eyes
perfect V-shaped chin
overly symmetrical doll face
generic AI influencer face
```

Important nuance:

```text
Do not turn this into one fixed beauty face.
The goal is stable attractive facial design for the selected person.
Different people may have different beautiful eyebrow, eye, nose, mouth,
jawline, and facial temperament directions.
```

## 7. Beautiful Realism Balance

Doc78 strengthens the distinction between beauty target and realism evidence.

Positive target:

```text
beautiful real-camera face
clean fair luminous East Asian complexion when appropriate
healthy clear skin tone
soft natural bounce light
visible but subtle skin texture
natural pores without roughness
real hair strands
natural eye moisture
pleasant lip texture
flattering but not fake facial shadow
polished commercial/social portrait finish
```

Negative target:

```text
plastic skin
beauty-app face
poreless mask
oily glass skin
silicone face
AI influencer template
forced tan / bronze / gray-brown cast unless requested
muddy or tired complexion
harsh unflattering documentary shadow
skin whitening mask
bleached skin
ugly realism
roughness used as realism
facial feature degradation used as realism
```

Prompt logic:

```text
If a rule says "realistic," interpret it as real camera rendering,
not lower attractiveness.

If a rule says "beautiful," interpret it as harmonious real-person beauty,
not face reshaping, beauty-app geometry, or over-smoothed skin.
```

## 8. Review And Retry Additions

Doc78 requires two foundation review families:

```text
identity_continuity_review
beautiful_realism_balance_review
```

New issue-code targets:

```text
identity_card_missing
identity_card_not_applied
identity_feature_drift
eyebrow_shape_drift
eye_shape_or_spacing_drift
nose_mouth_relationship_drift
jaw_chin_direction_drift
unflattering_feature_degradation
beautiful_realism_balance_failure
realism_made_subject_less_attractive
pretty_but_too_ai_filtered
real_but_unflattering
skin_texture_beauty_balance_failure
```

Retry patch behavior:

```text
identity drift:
  strengthen SubjectIdentityCard and selected reference usage

features changed badly:
  preserve eye/eyebrow/nose/mouth/jaw relationship from identity card

realism made the person less attractive:
  restore flattering light, clean complexion, harmonious facial proportions,
  awake eyes, relaxed expression, and pleasant eyebrow/lip design

pretty but too AI:
  keep beauty target but add real skin, hair, fabric, light, and camera detail

too cloned:
  keep identity-critical traits but vary expression, gaze, head angle, pose,
  crop, camera angle, and scene depth
```

Retry must stay bounded by Doc53.

## 9. Provider Prompt Consumption

The image provider prompt must receive a compact identity and beauty contract.

Required provider prompt sections:

```text
Subject identity card:
  keep identity-critical traits
  allow non-identity variation

Facial-feature aesthetic integrity:
  preserve attractive eyes, brows, nose-mouth relationship, jaw/chin direction
  avoid ugly feature drift or beauty-filter reshaping

Beautiful realism balance:
  pretty face, real light, real skin texture, no AI beauty mask, no ugly realism
```

The provider prompt must stay compact. Do not dump long internal JSON.

## 10. Frontend / UX Rule

No new complex UI is required for Doc78.

The existing user-facing model remains:

```text
select a favorite image
continue this project
generate more in the same direction
```

If shown later, the beginner-friendly wording should be:

```text
V3 will keep this person's look consistent.
V3 will allow new poses, angles, and scenes.
V3 will keep the face attractive and realistic.
```

Do not show engineering terms such as:

```text
SubjectIdentityCard
identity_continuity_review
retry patch
issue code
provider prompt
```

## 11. Acceptance Tests

Required coding-stage tests:

```text
1. User-selected output creates / updates the SubjectIdentityCard.
2. No selected output falls back to first high-quality generated human anchor.
3. Provider prompt includes compact identity-card rules.
4. Provider prompt includes facial-feature aesthetic integrity rules.
5. Provider prompt preserves beauty target while adding realism evidence.
6. Review issue codes create actionable bounded retry patches.
7. Clone-avoidance still allows pose/expression/camera variation.
8. General Template does not gain specialized photography/ecommerce packages.
9. Existing Doc70-77 tests still pass.
```

Required real-output validation:

```text
Generate a 4-image East Asian summer portrait project.
Select the best identity image.
Continue generation with different camera angle / pose / scene.
Evaluate:
  same-person recognizability >= 85%
  beauty / facial-feature integrity >= 85%
  photoreal skin-lighting texture >= 85%
  anti-AI-face feel >= 85%
  natural variation without clone face >= 80%
```

## 12. Current Status

```text
DOC78 IS THE FINAL FOUNDATION TUNING PLAN BEFORE NEXT SPECIALIZED TEMPLATE WORK.
It targets long-term identity and beautiful realism balance.
It does not supersede Doc76 placement governance.
It extends Doc77 aesthetic stability rather than adding a new vertical workflow.
```
