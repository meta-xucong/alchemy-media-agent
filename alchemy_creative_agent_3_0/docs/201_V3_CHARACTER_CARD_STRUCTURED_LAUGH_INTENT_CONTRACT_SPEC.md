# Doc201 — Character Card Structured Laugh Intent Contract

Date: 2026-07-24

## 1. Why Doc200 was not enough

Doc200 correctly identified that the `expression.laugh` candidates were failing
because they looked like polished open-mouth smiles rather than reliable laugh
keyframes. However, the first implementation was mostly a wording change in
the materializer prompt. That is not enough for a durable Professional
Character Card contract.

For Character Card, prompt text must be a projection of shared structured
intent. It must not be the authority itself. Otherwise Provider, MCP, Remote
Brain recovery, review, and future UI resumability can drift into slightly
different interpretations of the same slot.

## 2. Foundation-owned source of truth

The shared Visual Cluster now owns a structured `laugh` intent contract:

- `contract_version=v3_affective_laugh_intent_v2`;
- `owner=v3_shared_visual_cluster`;
- `emotion=laugh`;
- `intensity_band=medium_to_medium_high`;
- `arousal_band=medium_to_medium_high`;
- `phase=onset_to_peak_static_keyframe`;
- `static_keyframe_policy=single_still_may_hint_motion_but_must_not_claim_time_sequence`;
- `style_channel_policy=inherit_prompt_owned_face_front_channels_without_lighting_or_complexion_override`;
- `framing_policy=inherit_face_front_visual_skeleton`;
- participation channels include mouth-eye coherence, engaged/lively gaze,
  lower-lid/periocular participation, upper-cheek lift, relaxed jaw opening,
  age-appropriate teeth visibility, spontaneous asymmetry, identity
  preservation, and age coherence.

This contract is general expression infrastructure. It is not a child-specific
recipe, not a cold-white complexion rule, and not a commercial lighting default.

## 3. Prompt projection rule

Renderer prompt language is generated from the structured contract. The prompt
may say the image should show a clearly readable joyful laugh keyframe, but that
wording is only a materializer projection of the typed intensity/phase/channel
contract.

The phrase "engaged, lively gaze" means expression participation only. It must
not imply brighter lighting, cool/fair skin, lifted exposure, or any other
style/complexion change. Style, lighting, white balance, complexion, wardrobe,
background, and visual finish remain inherited from the approved `face.front`
card unless the current request owns those channels.

## 4. Routing

The same structured contract feeds:

- `ProfessionalModeRuntimeBridge.character_card_stage_metadata()`;
- Remote Brain `canonical_prompt_context.character_card_laugh_intent_contract`;
- Remote Brain response-contract guidance;
- bounded slot-delta recovery after Brain timeout;
- Product API Host default `expression.laugh` intent;
- Provider and MCP canonical prompt generation.

Provider and MCP are materialization channels only. They must receive equivalent
canonical prompt/reference contracts and must be judged by the same shared
Vision/affective-expression receipt.

## 5. Non-goals

This change does not:

- relax shared expression score floors;
- increase candidate or repair budgets;
- add a private Character Card reviewer;
- add a child-only branch;
- change General, E-Commerce, Photography, ordinary Face Identity, or Body
  Silhouette behavior;
- promote any previous failed candidate.

## 6. Validation

Tests must prove:

- the structured laugh contract contains versioned intensity, arousal, phase,
  participation, style-channel, and framing fields;
- Host and slot-delta recovery prompts project from the same foundation
  directive;
- Remote Brain response contracts receive the structured fields rather than
  the old weak natural-language phrase;
- Provider and MCP recovery prompts are identical for the same slot/reference
  contract;
- optional `expression.smile` remains low intensity and cannot satisfy
  `expression.laugh`;
- shared Vision floors and issue gates from Doc196/Doc199 stay active.
