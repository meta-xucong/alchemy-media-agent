# 65 V3 Human Photorealism And Anti-AI Face Layer Spec

Doc94 correction note:

```text
Doc65 remains the foundation for photographed-human realism and anti-AI-face
quality. Any named demographic, season, wardrobe, or historical validation case
in this document is test evidence only. It must not create a shared runtime
profile or prompt branch. Doc94 owns universal rendering variables.
```

Doc93 compatibility note:

```text
Doc65 remains a Human Realism foundation. Doc93 owns reference inheritance.
Photorealism and anti-AI-face guidance must not convert an ordinary portrait
identity reference into hair, wardrobe, lighting, scene, camera, or style truth.
```

## 1. Status And Authority

Doc65 is the human portrait realism layer after Doc64.

Authority chain:

```text
Doc50:
  Reusable visual enhancement belongs in the V3 native Visual Capability
  Cluster.

Doc54:
  Owns the four user-facing General Template modes.

Doc55:
  Owns post-generation vision inspection.

Doc56:
  Owns human identity consistency with natural variation.

Doc58:
  Owns selected-output identity anchors and strong reference continuation.

Doc61:
  Owns portrait commercial consistency validation and Lovart benchmark wording.

Doc62:
  Owns stronger portrait-suite role direction.

Doc64:
  Owns real-output commercial quality review, suite coverage audit, and
  issue-specific retry planning.

Doc65:
  Owns human photorealism, anti-AI-face rendering pressure, realistic skin and
  expression rules, and future reuse by the Photography Special-Tuning template.
```

Doc65 must be implemented as an independent V3-owned visual capability submodule
under the Visual Capability Cluster. It must not become hard-coded central-brain
logic, and it must not be embedded directly into General Template, E-Commerce,
or future Photography Template code.

Doc65 is a reusable human/portrait capability:

```text
General Template can call it for photoreal human outputs.
Future Photography Special-Tuning can call it as a core realism module.
Other future templates can call it only when they generate photoreal people.
```

## 2. Problem

Current V3 portrait outputs can be attractive and commercially polished, but
experienced viewers may still notice an AI-generated face quality.

Observed symptoms:

```text
skin is too smooth and too even
pores and natural skin texture are missing
face symmetry is too perfect
smile and eye expression feel template-like
cheeks, nose bridge, forehead, and shoulder highlights look too glossy
beauty retouching feels synthetic rather than photographic
the same idealized face language repeats across a set
strong-reference continuation preserves the AI-face quality as well as identity
```

This is not a provider-capability limitation. GPT image 2 can produce more
photoreal human portraits. The issue is that V3 currently applies strong
commercial polish language too broadly:

```text
polished
high-end
refined
beauty
commercial editorial
perfect lighting
clean finish
```

Those words improve composition and marketability, but they also push human
faces toward idealized AI beauty rendering unless balanced by explicit
photographic realism constraints.

## 3. Goal

Beginner-facing goal:

```text
When the user asks for realistic portraits, models, lifestyle photos, personal
photos, commercial photography, or people in real scenes, V3 should produce
faces that feel like real camera captures, not AI beauty-filter portraits.
```

Commercial goal:

```text
Preserve commercial appeal while adding real human texture, natural expression,
minor asymmetry, realistic skin response to light, and less synthetic perfection.
```

The goal is not to make people look worse. The goal is to make attractive people
look photographed instead of generated.

## 4. Module Boundary

Module name:

```text
HumanPhotorealismLayer
```

Suggested files:

```text
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/human_photorealism.py
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/anti_ai_face_review.py
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/photorealism_retry_planner.py
```

Allowed responsibilities:

```text
detect whether a generation is human/portrait/lifestyle-photography oriented
choose a photorealism intensity
add provider-facing realism guidance
add anti-AI-face negative constraints
review generated faces for synthetic beauty artifacts
produce issue-specific retry patches
expose a clean module contract for future Photography Special-Tuning
```

Not allowed:

```text
replace Doc56 identity policy
replace Doc58 strong-reference policy
replace Doc64 commercial quality review
force photorealism onto illustration/anime/fantasy/stylized requests
call V1/V2 runtime code
modify provider routing
auto-write Brand Memory
show raw AI-face diagnostic scores in beginner UI
```

## 5. Runtime Position

Doc65 must sit inside the existing V3 pipeline:

```text
Project
  -> Template / Scenario Pack
      -> ScenarioRuntime
          -> V3 Brain
          -> Visual Capability Cluster
              -> HumanNaturalVariationPolicy
              -> ProjectIdentityAnchorBuilder
              -> StrongReferenceContinuationPlanner
              -> HumanPhotorealismLayer
              -> AntiAIFaceReview
              -> CommercialQualityReview
          -> Prompt Compiler / Provider Prompt
          -> Generation Provider
          -> Post-Generation Review
          -> Issue-Specific Retry Planner
```

Central Brain may decide that a request requires photoreal people. The actual
rules, prompt fragments, review issues, and retry patches must live inside the
Doc65 module.

## 6. Activation Rules

Enable Doc65 when the request is photoreal human-oriented.

Strong enable signals:

```text
portrait
photo
photography
real person
model
lifestyle photo
commercial portrait
fashion photo
beauty photo
personal image
social cover with a person
street photo
documentary editorial
camera capture
```

Weak enable signals:

```text
woman / man / person / people
human subject
same character in realistic style
influencer-style photo
```

Disable or reduce Doc65 when:

```text
anime
manga
illustration
3D render
CG
cartoon
fantasy portrait
beauty poster with intentionally unreal finish
cosmetic ad requiring porcelain-skin style
explicit "perfect retouched beauty" request
```

The module must support three intensity levels:

```text
natural_realism:
  default for human photos

commercial_realism:
  keeps polished commercial lighting but avoids synthetic AI skin

beauty_retouched:
  allows more retouching but still rejects plastic/CGI face artifacts
```

Beginner UI does not need to expose these levels initially. The Brain and Visual
Cluster can infer them. Future Photography Special-Tuning may expose a simple
"more realistic / more polished" control.

## 7. Prompt Strategy

Doc65 adds positive realism guidance.

Natural realism fragments:

```text
real camera photograph
natural human skin texture
subtle pores and fine skin detail
slight facial asymmetry
natural skin tone variation
real daylight skin response
soft imperfect smile
relaxed facial muscles
small expression irregularities
minor flyaway hair
realistic hairline and baby hairs
plausible eyes with natural catchlights
documentary editorial photography
unretouched but attractive commercial photo feel
```

Commercial realism fragments:

```text
commercial portrait photography with realistic skin texture
refined but not plastic retouching
natural pores retained
realistic facial micro-asymmetry
believable makeup and skin highlights
camera-captured skin and hair detail
premium editorial lighting without synthetic beauty-filter smoothing
```

Beauty-retouched realism fragments:

```text
professional beauty retouching that preserves real skin texture
clean commercial finish with subtle pores still visible
polished editorial face rendering without doll-like perfection
natural eyes, lips, and skin highlights
```

Doc65 adds negative anti-AI-face constraints:

```text
plastic skin
doll-like face
over-smoothed skin
AI beauty filter
synthetic influencer face
CGI face
porcelain mask skin
over-perfect symmetry
unreal glossy highlights
airbrushed face without texture
template smile
uncanny eyes
wax-like skin
fake skin sheen
```

Do not include all fragments blindly. The module must select a concise subset
based on the request, mode, and subject type. Overloading the prompt can make
the model defensive or ugly; the intent is controlled realism, not harsh flaws.

## 8. Strong Reference Behavior

Doc58 says selected images become strong references. Doc65 adds one important
correction:

```text
Do preserve:
  recognizable identity direction
  face shape direction
  hair length/color direction
  body/proportion direction
  wardrobe family
  lighting and color world

Do not blindly preserve:
  over-smoothed skin
  synthetic glossy highlights
  template smile
  doll-like eye rendering
  plastic beauty-filter finish
```

Provider-facing reference rule:

```text
Use the selected image as identity, styling, and color-world reference, but
rebuild the face with more realistic camera-captured skin texture, natural
micro-asymmetry, relaxed expression detail, and less synthetic beauty-filter
smoothing.
```

This matters because strong references can otherwise lock in AI-face artifacts
and propagate them through the whole project.

## 9. Four-Mode Behavior

Doc65 must adapt to the four Doc54 modes.

### 9.1 Similar Candidates

Goal:

```text
small variations while keeping the same realistic face direction
```

Doc65 emphasis:

```text
same person direction
realistic skin retained
minor expression and gaze changes
avoid repeating one template smile
```

### 9.2 Delivery Suite

Goal:

```text
commercial set that looks like one real photo shoot
```

Doc65 emphasis:

```text
consistent face direction across roles
different expression and angle by role
realistic skin and hair in every frame
avoid over-polished repeated AI beauty face
```

### 9.3 Creative Exploration

Goal:

```text
broader visual concepts without losing believable human rendering
```

Doc65 emphasis:

```text
photoreal human quality remains believable
styling and scene may vary more
do not let creative lighting turn skin into CGI
```

### 9.4 Format / Layout Adaptation

Goal:

```text
adapt the same person/image idea to different crops and ratios
```

Doc65 emphasis:

```text
same realistic face direction
crop changes do not create beauty-filter face drift
safe areas and layout remain usable
```

## 10. Review Taxonomy

Doc65 adds AI-face-specific issues into Doc64 quality review.

Issues:

```text
ai_face_render
plastic_skin
over_smoothed_skin
synthetic_beauty_filter
doll_like_face
uncanny_eye_expression
template_smile
over_perfect_symmetry
wax_skin_highlight
missing_skin_texture
same_ai_face_repetition
```

Severity:

```text
watch:
  image is usable but has mild AI beauty polish

retry_recommended:
  face is clearly synthetic or too beauty-filtered for photoreal intent

block:
  face or eyes are uncanny, melted, wax-like, or commercially unusable
```

The review should not punish intentionally stylized outputs. It applies only
when the intended output is photoreal human photography.

## 11. Retry Planning

Doc65 retry must be specific.

Retry examples:

```text
plastic_skin:
  add natural pores, fine skin texture, real daylight skin response
  reduce porcelain/airbrushed finish

template_smile:
  request relaxed facial muscles, less posed expression, subtle asymmetry
  vary mouth shape and eye tension naturally

uncanny_eye_expression:
  request natural catchlights, relaxed eyelids, imperfect gaze direction
  avoid doll-like symmetrical eyes

same_ai_face_repetition:
  preserve identity through reference image
  vary expression, head angle, camera distance, and face muscle tension
  keep wardrobe and color world stable

wax_skin_highlight:
  reduce glossy face highlights
  use realistic skin response to daylight
```

Retry guardrails:

```text
do not add age, scars, acne, or heavy blemishes unless the user asks
do not make the person unattractive as a proxy for realism
do not weaken identity lock while fixing AI-face texture
do not retry more than Doc53/Doc64 budgets allow
do not retry if the target style is illustration, anime, or stylized beauty
```

## 12. Photography Special-Tuning Reuse

Doc65 must expose a clean interface for future Photography Special-Tuning.

Suggested interface:

```text
HumanPhotorealismRequest
  subject_type
  intended_style
  realism_level
  retouch_level
  reference_mode
  selected_reference_quality_notes
  variation_mode
  role_key
  user_goal

HumanPhotorealismGuidance
  positive_prompt_fragments
  negative_prompt_fragments
  reference_preserve_rules
  reference_do_not_inherit_rules
  review_targets
  retry_patch_templates
  user_facing_summary
```

Photography Special-Tuning can later call the same module for:

```text
portrait studio photos
street photography
fashion lookbooks
commercial lifestyle photography
dating/profile photos
personal brand photos
same-model multi-shot sessions
```

This prevents duplication. Photography Special-Tuning should specialize scene,
lens, lighting, and shoot planning; Doc65 should remain the shared human
realism and anti-AI-face capability.

## 13. Frontend Behavior

Default beginner UI:

```text
no new controls required
```

Optional future advanced control:

```text
真人感
  自然真实
  商业精修
  风格美型
```

If shown, the labels must be beginner-friendly. Do not expose terms like
`HumanPhotorealismLayer`, `AI-face score`, `provider prompt`, or `taxonomy`.

Workflow artifact summary:

```text
V3 已按真人摄影质感优化脸部表现，尽量保留自然皮肤纹理、真实表情和同一人物方向。
```

Advanced folded details may show:

```text
真人感策略
保留了什么
避免继承什么
是否发现过度 AI 美颜感
是否做过定向重试
```

## 14. Development Plan

### Phase 1: Contracts

Add module contracts:

```text
HumanPhotorealismRequest
HumanPhotorealismGuidance
AntiAIFaceReviewResult
AntiAIFaceIssue
HumanPhotorealismRetryPatch
```

Acceptance:

```text
contracts serialize into existing workflow artifacts
contracts can be consumed by General Template now
contracts can be consumed by future Photography Special-Tuning later
```

### Phase 2: Prompt Guidance

Integrate Doc65 prompt fragments into provider-facing prompts only when enabled.

Acceptance:

```text
photoreal portrait prompts include concise skin/expression realism guidance
stylized/anime prompts do not receive photorealism pressure
strong-reference prompts include "do not inherit AI-face artifacts" rules
```

### Phase 3: Review Layer

Extend post-generation review with anti-AI-face issues.

Acceptance:

```text
review can flag plastic skin, over-smoothed face, template smile, and uncanny eyes
review is skipped or softened for stylized outputs
review writes plain-language workflow evidence
```

### Phase 4: Retry Layer

Connect anti-AI-face issues to Doc64 issue-specific retry planning.

Acceptance:

```text
retry patches target the exact realism issue
retry preserves selected identity direction
retry does not make the person unattractive or off-brief
retry obeys Doc53/Doc64 budgets
```

### Phase 5: Real Validation

Run A/B validation using the stable portrait prompt:

```text
current commercial portrait prompt
Doc65 human photorealism prompt
Doc65 strong-reference continuation prompt
```

Compare:

```text
skin texture realism
eye expression naturalness
smile naturalness
face asymmetry believability
commercial appeal
identity continuity
AI-face reduction
```

Save:

```text
contact sheets
result JSON
prompt audit
manual quality notes
```

## 15. Test Plan

Focused tests:

```text
test_v3_human_photorealism_layer.py
test_v3_anti_ai_face_review.py
test_v3_photorealism_retry_planner.py
test_v3_mode_aware_role_director.py
test_v3_project_mode.py
test_v3_post_generation_vision_review.py
```

Regression:

```text
python -m pytest alchemy_creative_agent_3_0/tests tests -q --tb=short
python -m compileall -q alchemy_creative_agent_3_0/app alchemy_creative_agent_3_0/tests tests src_skeleton/app
node --check src_skeleton/app/static/app.js
git diff --check
```

Real validation:

```text
run the East Asian summer portrait prompt with and without Doc65
run selected-reference continuation with Doc65 enabled
inspect contact sheet for AI-face reduction
confirm commercial appeal remains high
record remaining gaps against Lovart-grade human photography
```

## 16. Completion Criteria

Doc65 is complete when:

```text
HumanPhotorealismLayer exists as an independent visual-cluster submodule
General Template can use it without hard-coding portrait logic into the center
future Photography Special-Tuning has a reusable module contract
photoreal portrait prompts include realistic skin/expression guidance
strong-reference prompts avoid inheriting AI-face artifacts
post-generation review can flag AI-face issues
retry planner can target AI-face issues
stylized/anime outputs are not damaged by photoreal constraints
focused tests pass
broad regression passes
real A/B validation shows lower AI-face feel while preserving commercial quality
```

## 17. Compatibility Audit

Doc65 is compatible with existing V3 architecture because:

```text
it stays under the Visual Capability Cluster
it extends Doc56 instead of replacing identity balance
it extends Doc58 instead of replacing strong references
it feeds Doc64 issue-specific review/retry instead of creating a separate loop
it can be reused by future Photography Special-Tuning without duplicating code
it does not alter provider routing, Project Mode, or template registry rules
```

If Doc65 conflicts with a user-requested stylized look, the user request wins.
If Doc65 conflicts with identity preservation, preserve identity but reduce only
the synthetic rendering artifacts.
