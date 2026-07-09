# 88 V3 Portrait Reference Balance And Prompt Mood Preservation Spec

## 1. Purpose

Doc88 is the latest authority for V3 portrait image-to-image balance after the
post-Doc87 VPS visual review.

Doc85, Doc86, and Doc87 correctly established that an uploaded portrait can be
used as a real image reference and that the person should remain recognizably
the same. However, the latest validation exposed a different failure:

```text
The first generated image could preserve the requested color tone, mood, and
even a reasonable amount of likeness better than later "stricter" attempts.

Later attempts made identity instructions harder, but they sometimes damaged
the prompt's atmosphere, color direction, and overall aesthetic intent without
meaningfully improving likeness.
```

Doc88 therefore changes the optimization target from:

```text
make identity rules harder
```

to:

```text
balance uploaded identity truth, user-approved visual direction, and the current
prompt's mood/art direction.
```

Short product rule:

```text
Keep the person, keep the user's intended atmosphere, and use accepted project
outputs as positive visual anchors. Do not fix one dimension by breaking the
other two.
```

This is a foundation-quality document. It applies to all V3 human / portrait /
person image-to-image paths that use a portrait identity reference. It is not a
scene-specific rule, not an industry-template rule, not a photography-template
package, and not a specialized vertical-template rule.

## 2. Compatibility And Authority

Doc88 extends and narrows:

```text
Doc76  Foundation vs specialized-template governance
Doc78  Long-term identity and beautiful realism
Doc83  Retry delivery layer and reference identity closure
Doc85  Image-to-image identity transfer and reference truth closure
Doc86  Portrait bone-structure identity lock
Doc87  Portrait reference identity and style separation
```

Doc85 remains the provider-reference truth-layer baseline.

Doc86 remains the implementation baseline for the portrait bone-structure lock,
identity issue codes, and identity-drift retry patches.

Doc87 remains the inheritance-boundary baseline:

```text
identity comes from the reference
direction comes from the prompt
```

Doc88 is the latest authority for:

```text
how hard identity guidance may become before it harms prompt mood
how approved generated outputs can guide color, lighting, composition, and tone
how retry should preserve both identity and the user's intended atmosphere
how to avoid turning one validation case into a scene-specific foundation rule
```

If Doc86 or Doc87 language encourages adding more and more negative identity
constraints until the image loses the user's requested tone, color, scene, or
mood, Doc88 wins.

If Doc86 or Doc87 examples mention any specific style family, scene type,
industry category, or photography language, those examples must be read as
examples only. They must not be copied into universal foundation prompts as
literal scenario-specific restrictions unless the user request or active
specialized template requires them.

If a previous output is user-approved or clearly selected as visually preferred,
it may become a positive style/tone anchor for future project generations. It
must not override the uploaded portrait identity truth, but it can protect the
color, lighting, mood, composition, and aesthetic direction that the user liked.

## 3. Three-Source Balance Model

V3 portrait image-to-image generation must distinguish three sources:

```text
1. Uploaded portrait reference
2. User-approved generated output / selected project image
3. Current natural-language prompt
```

### 3.1 Uploaded Portrait Reference

Primary responsibility:

```text
identity truth
```

It should preserve:

```text
recognizable same-person identity
face width / length direction
temple-cheek-jaw contour
cheek volume and cheekbone direction
eye shape and spacing
eyebrow-eye relationship
nose-mouth relationship
mouth / lip contour family
jaw and chin direction
age impression
body identity direction when visible
natural skin-tone direction
```

It should not automatically impose:

```text
source lighting
source color temperature
source background
source wardrobe
source camera mood
source whole-image style
```

### 3.2 User-Approved Generated Output

Primary responsibility:

```text
positive visual direction
```

It may preserve:

```text
color tone
lighting atmosphere
mood and emotional temperature
composition rhythm
camera distance family
lens / depth-of-field feeling
overall aesthetic direction the user liked
```

It must not override:

```text
uploaded portrait identity truth
explicit current prompt changes
template-specific constraints
```

Only positive / final / selected outputs can become this anchor.

Do not use:

```text
failed retry outputs
superseded outputs
process-only outputs
unselected candidates
outputs the user marked as disliked
```

### 3.3 Current Prompt

Primary responsibility:

```text
task truth and art direction
```

It controls:

```text
scene
lighting requirement
color grade
mood
camera
pose / expression / action
wardrobe / styling when requested
image purpose
aspect ratio and output mode
```

Current prompt wins over a previously approved output when the user explicitly
asks to change direction.

Example:

```text
Approved output: one accepted visual direction.
New prompt: a different color, light, scene, or mood direction.

The approved output can keep general craft / subject framing if useful, but the
new prompt controls the specific current color, light, scene, and mood.
```

## 4. Provider Prompt Ordering

Provider prompts for portrait image-to-image should be layered as:

```text
1. Current prompt's user goal and mood/art direction
2. Uploaded portrait identity truth
3. User-approved positive visual anchor, if present
4. Allowed variation budget
5. Compact negative guidance
6. Retry-specific patch, only when retrying
```

Why current prompt is first:

```text
Doc87 correctly separated identity from style, but later optimization showed
that identity guidance can become so verbose that the prompt mood is weakened.
The prompt's intended atmosphere must stay visible and early.
```

Why uploaded identity still remains hard:

```text
Putting prompt mood first does not mean replacing the person. It means the image
should be the same person inside the requested atmosphere, not a generic identity
repair frame.
```

### 4.1 Good Provider Wording

Use concise, positive guidance:

```text
Use the uploaded portrait as same-person identity truth.
Keep the person's underlying face structure and feature relationships.
Follow the current prompt for color, light, scene, camera, and mood.
If a selected project image is present, use it as positive tone/composition
guidance, not as a replacement identity.
```

### 4.2 Avoid Overloaded Provider Wording

Avoid long lists of scenario-specific negative phrases in foundation prompts.

Do not write universal prompt blocks like:

```text
avoid [specific scenario] beauty face
avoid [specific genre] face
avoid [specific industry] template face
avoid [specific season] template face
avoid [specific photography setup] template face
```

unless the current prompt or active template actually contains that scenario.

Foundation prompts should instead use general language:

```text
do not replace the reference person's facial identity with a generic stylized
template face
do not let target style remodel the face structure
do not make a similar-looking new model
```

## 5. Retry Strategy

Doc88 changes retry from "identity harder every time" to "issue-specific
balance repair".

### 5.1 Identity Drift Retry

Use when:

```text
the image follows prompt mood but the face is not the same person
```

Retry patch should:

```text
strengthen uploaded identity truth
keep current prompt color / lighting / scene / mood intact
reuse accepted project style anchor if it helped the mood
reduce generic template-face pressure
```

Retry patch must not:

```text
discard the prompt's atmosphere
make the image colder / warmer / flatter unless requested
copy the source reference lighting by accident
add scenario-specific negative words that are absent from the user prompt
```

### 5.2 Mood / Tone Regression Retry

Use when:

```text
the face may improve but the generated image loses the user's intended color,
light, scene, or emotional atmosphere
```

Retry patch should:

```text
restore the original prompt's color and atmosphere
use the best approved output as positive tone reference when available
keep identity lock at the previous level, not harder
remove excessive negative identity wording
```

Issue codes should include:

```text
prompt_mood_regression
prompt_color_tone_regression
approved_style_anchor_ignored
identity_repair_damaged_prompt_direction
overconstrained_identity_prompt
scenario_specific_negative_overfit
```

### 5.3 Over-Constrained Identity Retry

Use when:

```text
identity prompt rules are so long or restrictive that the result becomes stiff,
less aesthetic, less atmospheric, or less faithful to the user's prompt
```

Retry patch should:

```text
compress identity rules to the smallest effective set
prefer positive same-person wording over long negative lists
keep only the most important face-structure traits
restore prompt mood priority
```

### 5.4 Stop Condition

If two retries do not improve both identity and prompt mood, stop automatic
retry and present the best available candidates rather than continuing to spend
time or tokens.

Do not create an endless loop where every failure makes the next prompt longer.

## 6. Implementation Direction

Implement inside the existing V3 native visual capability cluster.

Do not:

```text
create a new portrait pipeline
move this logic into Central Brain
hardcode a single scene, culture, wardrobe, era, or platform
duplicate Doc86 / Doc87 modules
```

Preferred implementation:

```text
extend PortraitBoneStructureIdentityLayer with a balance policy, or
add one child module under visual_cluster only if the logic becomes large:
portrait_reference_balance_policy
```

Expected internal contract:

```text
PortraitReferenceBalancePolicy
  applies: bool
  identity_source: uploaded_portrait | selected_output | planned_anchor
  positive_style_anchor_ids: list[str]
  prompt_owned_channels: list[str]
  identity_truth_channels: list[str]
  style_anchor_channels: list[str]
  compact_provider_rules: list[str]
  retry_balance_rules: list[str]
  blocked_overfit_rules: list[str]
```

Provider metadata should expose:

```text
portrait_reference_balance_policy_id
uploaded_identity_truth_source_id
positive_style_anchor_output_ids
prompt_mood_preserved: bool
provider_prompt_identity_rule_count
provider_prompt_mood_rule_count
```

## 7. Frontend / UX Contract

Beginner UI must not show engineering terms.

When the user selects a generated image as preferred, UI language should be:

```text
Use this picture's feeling for the next group
Keep this visual direction
```

Not:

```text
style anchor
reference truth layer
identity source priority
provider prompt patch
```

The project detail page may show advanced information in a folded card:

```text
V3 used your uploaded portrait to keep the person recognizable.
V3 used your selected image to keep the color and atmosphere you liked.
V3 followed your new prompt for the next scene and action.
```

## 8. Test Plan

Focused tests:

```text
uploaded portrait remains identity truth
selected approved output becomes positive tone/style anchor
unselected / failed / superseded output does not become positive tone anchor
provider prompt keeps prompt mood before compacting long identity guidance
provider prompt does not contain scenario-specific negative words unless the
  user prompt or active template contains that scenario
identity drift retry preserves prompt mood lines
mood regression retry does not harden identity further
over-constrained identity retry shortens negative guidance
```

Regression tests:

```text
Doc85 reference truth layering
Doc86 bone-structure identity lock
Doc87 identity/style separation
Doc78 beautiful realism balance
Doc75 strict review closure
Doc66 strong reference closure
provider prompt compaction
project output final/superseded/process-only filtering
```

Manual visual validation:

```text
Use the same uploaded portrait and the same prompt as the latest VPS case.
Compare:
1. earliest preferred output
2. pre-Doc88 over-constrained output
3. post-Doc88 output

Pass only if:
same-person readability improves or at least does not regress
prompt color tone and mood are preserved
the image remains aesthetically strong
the result does not feel like a generic template face
```

## 9. Acceptance Criteria

Doc88 is implemented only when all are true:

```text
1. Uploaded portrait identity truth remains active.
2. User-approved generated outputs can guide tone / mood / composition.
3. Current prompt remains the source of task direction and atmosphere.
4. Retry patches can separately repair identity drift and mood regression.
5. Provider prompts do not accumulate scene-specific universal negatives.
6. Automatic retry is bounded and does not grow prompts indefinitely.
7. Tests prove Doc85 / Doc86 / Doc87 still pass.
8. Real visual validation shows better balance than the over-constrained runs.
```

## 10. Codex Implementation Prompt

```text
Implement Doc88.

Do not rewrite V3 and do not create a new portrait pipeline. Keep the work under
the existing V3 Visual Capability Cluster. Preserve Doc85 provider-reference
truth layering, Doc86 bone-structure identity lock, and Doc87 identity/style
separation, but add the missing balance rule: uploaded portrait identity truth,
user-approved visual direction, and current prompt mood must all be preserved.

Remove or soften any foundation-level provider wording that turns one validation
case into a universal scenario-specific negative rule. Add a compact balance
policy so selected approved outputs can protect color, lighting, atmosphere, and
composition without overriding uploaded identity truth. Add retry issue codes
for prompt mood regression and over-constrained identity prompts. Add tests that
prove identity repair cannot damage prompt mood and mood repair cannot replace
the person.

Run Doc85/86/87 regressions, full V3 tests, provider prompt compaction tests,
and one real image-to-image validation when the provider is available.
```
