# Doc186: V3 Reference-Led Character Card Slot Delta Prompt Contract

## Status and authority

```text
AUTHORITATIVE_PROFESSIONAL_CHARACTER_CARD_PROMPT_MINIMIZATION
REFERENCE_LED_SLOT_DELTA_CONTRACT
NO_LOCAL_PROMPT_REWRITE
NO_STANDARD_MODE_CHANGE
NO_PROVIDER_OR_MCP_FORK
FACE_FRONT_POSE_NORMALIZATION_REQUIRED
FACE_IDENTITY_FIXED_FRAMING_REQUIRED
COMMERCIAL_CLARITY_REVIEW_FLOOR_REQUIRED
```

This document supersedes older Character Card wording only where that wording
implies that every Face Identity, Expression Set, or Body Silhouette slot must
restate the full person definition inside the renderer prompt.

The new authority is:

```text
First identity-defining capture may carry rich person direction.
The first face.front capture must normalize the source into a true straight-on
standard front card; a slightly angled source pose is identity evidence only.
All Face Identity slots use the same fixed head-and-upper-shoulders framing.
Later slots are reference-led deltas.
Quality contracts remain typed and hidden from renderer prose unless the Brain
decides a short, positive renderer phrase is necessary.
Commercial-clean, translucent, no-smear pixels are a hard review gate for the
standard Face Identity base.
```

This document extends Docs178, 183, 184 and 185. It does not create a local
prompt filter, a second Brain, a second Provider, a second Vision reviewer, a
private retry loop, or a separate image store.

## 1. Problem corrected

The Character Card chain previously allowed each slot to ask the Remote Brain
for another full renderer-facing character description. For child or other
safety-sensitive people assets, this caused three concrete problems:

1. repeated age, body, complexion, skin and expression wording raised upstream
   moderation risk before any pixels existed;
2. long prompts made later slots slower and more expensive while repeating
   facts already fixed by the selected reference image;
3. prompt collisions appeared, such as an Expression Set slot requesting a
   smile while the same full prompt described a closed neutral mouth.

The fix is not to weaken quality review. The fix is to move stable person facts
out of repeated renderer prose and into active reference images plus typed
contracts.

## 2. Three-layer prompt ownership

### 2.1 Identity Definition Prompt

The first identity-defining stage may use a fuller Brain-authored prompt
because the system is still establishing the person.

For Character Card Face Identity, this applies to:

```text
face.front
```

It may carry richer direction about the intended identity capture, age stage,
commercial cleanliness, human materiality and neutral background. It still
goes through the existing Remote Brain finalizer, Provider/MCP parity,
shared Vision review and winner selection.

For `face.front`, the source portrait's face angle is not inherited as the
final card angle. The Brain must sign and materialize a true straight-on,
symmetric, camera-facing standard front capture: face midline vertical, eyes
level and nose centered. This is a reusable card standard, not an aesthetic
preference.

For every Face Identity view, the framing is fixed as a clean
head-and-upper-shoulders reference crop: head top margin, full face, neck and
upper shoulders visible. Big-head close-ups, half-body, chest-up, waist-up and
torso frames are out of slot.

### 2.2 Slot Delta Prompt

Every later Character Card slot must be generated as a delta from approved
reference evidence:

```text
face.front_three_quarter
face.profile
face.reverse_three_quarter
face.rear_head
expression.neutral
expression.smile
expression.anger
expression.sad
body.front_full
body.side_full
body.rear_full
```

The renderer prompt should focus on the one current slot variable:

- view angle for Face Identity continuation;
- expression state for Expression Set;
- body pose/view for Body Silhouette.

The prompt should not repeatedly restate stable person facts such as age,
height, body build, complexion, skin texture, face anatomy, lip/teeth details,
or long contrastive safety wording. Those remain owned by approved references
and typed review contracts.

### 2.3 Hidden Quality Contract

The system still keeps the full Professional quality contract:

- same-person continuity;
- age/developmental coherence;
- camera-observed human materiality;
- non-adult presentation for child assets;
- real skin and anti-AI-polish;
- prompt/reference parity;
- Provider/MCP equivalence;
- shared Vision review and bounded retry.
- commercial-clean translucent face-card pixels with no dirty cast, smear,
  waxy smoothing, plastic shine or beauty-filter haze.

These are typed planning/review obligations. They are not automatically copied
as renderer prompt prose for every slot.

## 3. Required typed receipt

When the frozen stage is a later Character Card slot, the Remote Brain must
return this receipt beside the canonical prompt:

```text
reference_led_slot_delta_decision:
  contract_version: v3_reference_led_slot_delta_decision_v1
  materialization_mode: reference_led_slot_delta
  stable_identity_source: approved_character_card_reference
  prompt_scope: slot_delta_only
  safety_sensitive_repetition_policy: avoid_repeating_stable_person_biology
  slot_delta_type: view_angle | expression | body_pose
  status: approved | rewritten
  owner: remote_v3_llm_brain
```

This receipt proves that the Brain signed the prompt as a reference-led delta.
It is not renderer text and cannot be supplied by the browser, MCP caller or
local code.

Missing, malformed or mismatched receipts fail closed before Provider or MCP
materialization.

## 4. Face Identity slot-scope gate

Doc186 also tightens a gap exposed during controlled validation: the Remote
Brain can structurally sign `character_card_face_identity` and still write a
renderer prompt that leaves the slot, for example a full-body outdoor fashion
scene. That is not a quality preference problem; it is a module-boundary
violation.

For `character_card_face_identity`, the adapter must therefore perform a
narrow post-signing slot-scope check before Provider or MCP materialization:

- Face Identity prompts must remain face/head or upper-shoulder identity
  evidence captures;
- Face Identity prompts must use the fixed head-and-upper-shoulders framing;
- `standard_front`, `three_quarter`, `profile`, `reverse_three_quarter` and
  `rear_head` must materially express the frozen view role;
- `standard_front` must materially express straight-on pose normalization and
  face-axis alignment rather than merely saying "front-facing";
- prompts must not turn the slot into full-body, head-to-toe, wardrobe,
  outdoor-location, cinematic lifestyle, body-proportion or height-estimation
  scenes;
- the adapter may reject an out-of-scope signed prompt, but it must not patch,
  shorten, translate or replace renderer wording locally.

This is a structural slot gate, not a child-specific beauty rule and not a
keyword recipe for good images. It protects the Character Card module boundary
so that Body Silhouette and later project scenes remain the only places where
full-body pose, wardrobe, location or lifestyle context may become primary.

The slot gate must be native-language aware. Chinese Brain-authored prompts
such as "真正直面镜头", "脸部中线垂直", "双眼水平", "鼻梁居中",
"头部、颈部和上肩" and equivalent phrasing satisfy the same typed contract as
English terms such as "straight-on" and "head-and-upper-shoulders". The adapter
must not reject a semantically valid Chinese prompt merely because it does not
use the English wording from the schema.

## 4.1 Commercial clarity gate

Controlled validation showed that ordinary shared Vision could score a
Face Identity result highly while human inspection still saw slight smear,
dirty softness or AI over-smoothing. For reusable character-card bases, that is
not acceptable: the base image becomes the source for later views, expressions,
body silhouette and project scenes.

Therefore `character_card_face_identity` review adds a stricter commercial
clarity floor after shared Vision verification:

```text
visual_quality >= 0.96
technical_finish >= 0.96
human_realism >= 0.92
```

Missing or lower scores fail the candidate with
`professional_face_card_commercial_clarity_below_bar`. This does not replace
shared Vision, loosen identity review or create a private reviewer. It is an
extra Character Card Face Identity acceptance floor on top of the same shared
review package.

## 5. Provider and MCP behavior

Provider and MCP remain transport choices after the same frozen Brain prompt:

```text
typed reference-led slot-delta requirement
  -> Remote Brain complete canonical prompt + receipt
  -> same canonical prompt hash and reference hashes
  -> Provider or MCP image call
  -> same output store
  -> same shared Vision review
  -> same Character Card slot writeback
```

MCP must not receive a locally shortened replacement prompt. If the Brain
returns a long unsafe prompt despite the typed contract, the adapter blocks or
requests the existing Brain re-sign path; local code does not patch it.

## 6. Stage mapping

| Stage | Prompt strategy | Reference authority | Slot delta type |
| --- | --- | --- | --- |
| `face.front` | Identity Definition Prompt + true straight-on normalization + fixed head-and-upper-shoulders framing | root source plus admitted supplementary source | not applicable |
| `face.front_three_quarter` | Slot Delta Prompt | approved front winner plus root/evidence budget | `view_angle` |
| `face.profile` | Slot Delta Prompt | approved prior winners plus root/evidence budget | `view_angle` |
| `face.reverse_three_quarter` | Slot Delta Prompt | approved prior winners plus root/evidence budget | `view_angle` |
| `face.rear_head` | Slot Delta Prompt | approved prior winners plus root/evidence budget | `view_angle` |
| Expression Set | Slot Delta Prompt | active `face.front` winner | `expression` |
| Body Silhouette | Slot Delta Prompt | active face module plus authorized body evidence or inferred body contract | `body_pose` |

## 7. Conflict markers for older documents

- Doc178 section 4 remains authoritative for slot order, candidate budget,
  review and activation. Its module generation wording must now be read as:
  later slots are reference-led deltas, not repeated full person-definition
  prompts.
- Doc183 remains authoritative for Provider/MCP parity. Its "same canonical
  prompt" rule is preserved, but the canonical prompt for later Character Card
  slots should be the Brain-signed slot delta prompt, not a local rewrite and
  not a repeated long identity description.
- Doc184 remains authoritative for `character_card_face_identity` geometry.
  Face/head capture scope still applies, but later view slots should express
  only the frozen view delta while references carry the established person.
  If older wording appears to tolerate full-body, half-body, big-head,
  inconsistent crop, inherited source-pose angle for `face.front`, or
  lifestyle scene language inside Face Identity captures, Doc186 supersedes it.
- Doc185 remains authoritative for provider admission. Provider-admission
  normalization now pairs with this reference-led delta contract for later
  Character Card slots. It must not become a child-specific local prompt
  recipe.
- Any historical validation evidence that used longer prompts remains readable
  as evidence for that run. New runs should follow this document.

## 8. Acceptance tests

Implementation is accepted only when tests prove:

1. `face.front` is not forced into reference-led delta mode;
2. later Character Card face slots carry the reference-led slot-delta contract;
3. Expression Set and Body Silhouette carry the same contract with the correct
   `slot_delta_type`;
4. the final Brain schema requires `reference_led_slot_delta_decision` for
   those stages and the adapter rejects missing receipts;
5. a signed `character_card_face_identity` prompt that becomes a full-body,
   outdoor, wardrobe or lifestyle scene is rejected before Provider/MCP;
6. a signed `standard_front` prompt that does not explicitly normalize a true
   straight-on front face is rejected before Provider/MCP;
7. Face Identity review rejects commercial-clarity scores below the stricter
   face-card floor even when ordinary shared Vision status is pass/warning;
8. Provider and MCP consume the same signed prompt/hash/reference contract;
9. Standard Mode, General, E-Commerce and Photography do not receive this
   Character Card-only receipt.

## 9. Expected product effect

The primary quality goal is unchanged: generated character-card images must
not become less beautiful, less realistic, less consistent, or less useful.

The expected secondary benefits are:

- fewer upstream false moderation blocks on child assets;
- lower token cost and faster Brain finalization;
- fewer prompt-internal contradictions;
- stronger cross-slot identity consistency;
- a more general asset-system architecture that will also support future
  Product and Scene assets without brittle prompt accumulation.
