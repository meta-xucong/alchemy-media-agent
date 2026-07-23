# Doc188: V3 Character Card Face Evidence-Grade Capture Optimization

## Status and authority

```text
AUTHORITATIVE_CHARACTER_CARD_FACE_EVIDENCE_CAPTURE
COMMERCIAL_CLEAN_DOES_NOT_MEAN_BEAUTY_PORTRAIT
NO_CHILD_SPECIFIC_PROMPT_RECIPE
NO_PROVIDER_OR_MCP_FORK
NO_VISION_GATE_RELAXATION
```

This document extends Docs178, 180, 182, 183, 184, 185, 186 and 187. It
supersedes only wording that could be read as telling Face Identity to produce
a polished portfolio, fashion, social-media, pageant or beauty portrait.
Doc189 supersedes any narrow reading of this document that treats commercial
refinement itself as a failure: a clean, cool-white, commercially retouched
studio finish is allowed when identity, developmental age, materiality,
fixed crop and prompt-owned channels remain intact.

The new interpretation is:

```text
Face Identity images are reusable identity evidence.
They must be clean enough for commercial use, but not beautified into a
generic model portrait.
MCP and Provider receive the same canonical prompt and enter the same review,
winner, storage and resume path.
```

## 1. Problem found in validation

After Doc187, the fresh MCP run correctly resumed candidate indices and stopped
after the bounded `face.front` budget. The three submitted pixels were real
MCP materializations, but shared Vision rejected all of them. The repeated
failure pattern was not a transport failure:

- Brain produced prompts;
- MCP produced pixels;
- review ran and returned structured failures;
- resume/failure budget stopped safely.

The visual problem was objective drift. The candidates read as pleasant,
polished commercial children’s portraits, not standardized reusable Face
Identity evidence. In practice this produced several defects:

1. front pose remained slightly flattering or source-like rather than truly
   standardized;
2. expression/gaze leaned toward model performance instead of ordinary neutral
   identity attention;
3. skin and surface finish became too polished or synthetic;
4. framing could feel like a portrait crop rather than a consistent card slot.

## 2. Correct target

Face Identity must be an evidence-grade standardized capture:

- fixed head, full face, neck and upper-shoulders framing;
- plain white matte reference field;
- for `face.front`, observable straight-on symmetry through balanced ears,
  cheeks, eye line, nose axis and shoulders;
- stage-appropriate relaxed attention, not a model persona;
- camera-observed skin, hair and facial materiality with small real variation;
- fair, cold-white or commercial-clean skin language interpreted as neutral
  white balance, clean exposure and natural fair complexion, not whitening or
  beauty-retouch polish;
- commercial cleanliness, crispness and translucency without dirty noise,
  smear, waxy smoothing, plastic shine or beauty-filter haze.

This is not a child-specific morphology recipe. If the user asks for a
six-year-old, the age comes from the user-owned developmental-age contract and
the source evidence. If the user asks for a fifteen-year-old or an adult, the
same evidence-grade capture standard applies without importing six-year-old
features.

## 3. Implementation contract

The shared runtime adds a typed contract only for
`capture_scope=character_card_face_identity`:

```text
face_card_evidence_capture_contract
  contract_version: v3_character_card_face_evidence_capture_v1
  capture_objective: standardized_identity_evidence_capture_not_portfolio_or_beauty_portrait
  pose_observability: balanced_ears_cheeks_shoulders_no_head_turn_or_tilt
  expression_standard: stage_appropriate_relaxed_neutral_attention_not_model_performance
  materiality_standard: camera_observed_skin_and_hair_detail_with_minor_real_variation
  complexion_semantics: fair_or_cool_white_means_neutral_white_balance_not_skin_whitening
  background_standard: plain_white_matte_reference_field_no_vignette_or_glamour_gradient
  aspect_ratio_standard: honor_frozen_rendering_size_as_reference_card_aspect_ratio
  lens_standard: low_distortion_portrait_lens_no_big_eye_or_beauty_perspective
```

The Remote Brain remains the only author of renderer prompts. Local code may
transport and validate the typed contract; it must not append a prompt suffix,
write a child-feature checklist, relax shared Vision, or branch MCP away from
Provider.

## 4. Prompt ownership

The Brain finalization contract must reconcile Character Card Face Identity as
evidence-grade capture. It may use concise positive renderer language such as:

```text
standardized identity evidence capture
straight-on front view with balanced ear and cheek visibility
plain white matte reference field
stage-appropriate relaxed neutral attention
camera-observed skin and hair detail
vertical 2:3 card when the frozen renderer size is 1024x1536
neutral white balance and natural fair skin instead of whitening
```

It must avoid turning the renderer prompt into:

- a portfolio beauty portrait;
- a fashion/social-media/pageant headshot;
- a fixed age-feature checklist;
- a list of forbidden anatomy or safety-sensitive negatives;
- a local repair phrase appended after the prompt.

The `professional_anchor_view_decision` receipt for
`character_card_face_identity` must also carry:

```text
aspect_ratio_standard: honor_frozen_rendering_size_as_reference_card_aspect_ratio
```

The adapter rejects a signed Face Identity prompt that has no visible vertical
card/aspect-ratio materialization language. This is a scope gate like the
existing head-and-upper-shoulders gate, not a creative prompt recipe.

When the Brain misses this signed field or omits the prompt-side vertical card
language, the existing one-shot anchor-view recovery must carry a short
required-field list and the required prompt materialization string:

```text
required_prompt_materialization: vertical_2_3_reference_card_aspect_language
```

Recovery re-asks the same frozen context; it must not invent a new asset plan
or append a local repair suffix.

## 5. MCP rendering-size parity

The MCP channel is only a transport outlet. It must not let a local ImageGen
artifact bypass the same rendering contract that Provider would have used.

For concrete handoff sizes such as `1024x1536`, the MCP handoff declares:

```text
size_normalization: white_matte_contain_to_contract_size
```

If the submitted artifact already matches the frozen size, it is stored as-is.
If the artifact is readable and has the correct output format but a different
size, the MCP store may perform one auditable transport normalization:

- scale the submitted image proportionally;
- fit it inside the frozen canvas;
- use a plain white matte field;
- do not crop, inpaint, retouch, beautify or change the subject;
- record original width/height, target width/height and result width/height.

If no normalization policy is present, a size mismatch must fail closed with
`mcp_materialization_output_size_mismatch`.

This makes MCP and Provider equivalent at the stored artifact boundary without
creating a second creative path.

## 6. Conflict resolution with older documents

- Doc184 still governs face/head capture scope and fixed framing.
- Doc186 still governs reference-led slot-delta minimization.
- Doc187 still governs MCP resume indices and bounded failure budget.
- Any older phrase that treats “commercial clean” as “beauty portrait polish”
  is superseded by this document.
- “Commercial clean” now means technically clean, bright, crisp, translucent
  and reviewable while preserving real camera materiality.

## 7. Acceptance checks

Implementation is acceptable only when:

1. Character Card Face Identity planning metadata carries the evidence-grade
   capture contract;
2. ordinary Anchor Pack, Standard Mode, General, E-Commerce and Photography do
   not receive the contract;
3. Brain finalization receives explicit evidence-grade capture language;
4. MCP and Provider still share one canonical prompt, review path, winner path,
   storage path and resume budget;
5. MCP handoff artifacts either match or are normalized to the frozen rendering
   size through an auditable white-matte contain operation;
6. tests pass without relaxing Vision thresholds or adding private fallbacks;
7. a fresh validation run is attempted from the authorized source image and
   either produces accepted slots or stops with bounded review evidence.
