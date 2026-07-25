# Doc252 — V3 Micro Real-Human Fidelity Enhanced Module

## Purpose

Doc248 improved portrait realism while keeping Formal Core, receipt authority,
slot lifecycle, Provider/MCP routing, and generation budgets unchanged. The
controlled comparison still shows a clear remaining gap: close inspection can
identify AI portrait artifacts in eyes, hair, skin, ears, clothing texture, and
light/camera response.

This document defines the next optional Enhanced module:

```text
micro real-human fidelity, while preserving commercial beauty
```

It does not own crop, view angle, slot framing, winner selection, receipt
construction, activation, routing, retries, or Provider/MCP fallback. Those
remain in their existing owning layers.

## Layer ownership

| Concern | Owner | This module may do | This module must not do |
| --- | --- | --- | --- |
| Micro human realism | Doc252 Enhanced portrait quality module | Request and evaluate visible evidence of real photographed skin, eyes, hair, ears, garment, and camera response | Change framing, choose winner, write slot receipt, route Provider/MCP, or optimize for detector evasion |
| Commercial beauty preservation | Doc248/Doc252 Enhanced profile | Require clean model-card finish and high commercial attractiveness to remain intact | Add unattractive noise, dirt, blur, asymmetry, or rough documentary defects |
| Slot framing | Face/Character Card view-role framing profile | No authority | No crop or face-box envelope decisions |
| Winner/receipt/activation | FormalSlotAcceptanceCore/FormalSlotReceipt | No authority | No Core imports or lifecycle mutation |

Short form:

```text
Doc252 improves human micro-evidence only.
It does not own the frame.
```

## Non-goals

This module is not detector evasion. It must not optimize against a named AI
detector or add random noise, JPEG damage, dirt, blur, warping, or ugliness to
trick classifiers.

It is also not a new portrait template. It must not define which professional
views exist, how many candidates are generated, whether a slot is complete, or
which transport route should be used.

## Observed realism gap

The Doc248 comparison winner improved aggregate scores relative to the earlier
baseline, but external critique still identified believable residual AI
signals:

- eye highlights and eye geometry read too mirrored;
- sclera and iris texture are too clean and standardized;
- hairline, bangs, temple hair, and side hair look too orderly;
- skin has smooth ceramic transitions rather than camera-observed pores and
  tonal variation;
- ear cartilage is simplified or too symmetric;
- garment weave and collar tension are too regular;
- commercial finish is attractive, but too idealized.

These are not Formal Core failures. They are Enhanced quality evidence gaps.

## Module contract

### Profile name

```text
micro_real_human_fidelity_v1
```

Initial frozen profile floors:

```text
minimum_micro_dimension_score = 0.78
minimum_micro_beauty_score = 0.82
```

Callers may not lower these floors. Any future change must create a new
profile/version or an explicit reviewed calibration artifact; it must not be a
per-request override.

### Candidate-level proof

The module emits candidate-level Enhanced proof. It is consumed like any other
Enhanced eligibility proof and remains separate from the canonical generic
shared Vision receipt.

Required proof properties:

- `profile_id = micro_real_human_fidelity_v1`
- explicit `eligible` / `status`; no default eligible state;
- non-empty evidence codes;
- finite score dimensions;
- no prompt, provider, handoff, local path, artifact, raw model payload, or
  detector label leakage;
- no import or dependency on Formal Core.

### Default behavior

Doc252 is disabled by default. When disabled, the existing Doc248, Face,
Expression, Body, Formal Core, Provider, MCP, and public-projection behavior
must remain byte-for-byte equivalent except for explicit test fixtures that
inspect module availability.

Enabling the profile requires a trusted server/Host decision. A user payload,
ordinary job metadata, or public route field must not silently enable it.

### Required micro dimensions

| Group | Required dimensions |
| --- | --- |
| Eyes | non-mirrored catchlights; natural eyelid asymmetry; gaze-axis consistency; sclera micro-texture; non-plastic iris detail |
| Hair | strand-width variation; flyaway/baby-hair evidence; temple and ear-side hair integration; non-uniform edge silhouette |
| Skin | pore-scale texture; cheek and nose-wing tonal variation; non-ceramic highlight transition; lip/chin material transition |
| Ears | cartilage fold clarity when visible; left/right non-identity; natural hair/ear boundary |
| Garment | fabric weave irregularity; collar tension plausibility; seam/edge non-uniformity |
| Camera/light | natural microcontrast; plausible sensor/lens response; believable highlight rolloff and edge response |
| Beauty guard | commercial_beauty_preserved; clean model-card finish; age-appropriate attractiveness preserved |

Missing visible evidence must fail closed. A candidate may be beautiful but not
micro-real enough; it must not pass this module merely because the generic
Vision receipt passed.

### Visibility and applicability

Some micro-realism evidence is view-dependent. Ears, garment weave, collar
tension, and side hair may be partially or fully invisible in a tight headshot
or a crop where the approved Face framing profile does not expose them. Doc252
must not force the prompt or the crop to reveal those regions just to satisfy
the realism module.

Each dimension therefore carries an applicability receipt:

```text
applicability = applicable | not_applicable
visibility = visible_and_reviewable | occluded | outside_frame | insufficient_resolution
status = pass | fail | not_applicable
```

Rules:

1. If a region is visible and reviewable, its required dimension must be
   evaluated and may pass or fail.
2. If a region is not visible because the owning Face framing/profile does not
   expose it, the dimension may be `not_applicable`, but the proof must include
   a safe visibility reason.
3. `not_applicable` is not a pass. It only removes that dimension from the
   denominator for this crop/profile.
4. Missing applicability is a failure.
5. A profile may set minimum applicable groups. For example, eyes, skin, hair,
   and light/camera response are expected for a standard-front portrait;
   garment and both-ear evidence may be not applicable when not visible.
6. Doc252 must not alter the Face framing profile to manufacture visibility.

This resolves the tight-headshot conflict: invisible ears or garment details do
not automatically fail the portrait, but neither are they silently credited.

## Architecture

Doc252 is a hot-pluggable Enhanced profile. It is invoked only when a trusted
professional Host enables the profile for a portrait-facing candidate. The
module has no independent lifecycle.

```text
candidate image
  -> canonical shared Vision review
  -> Doc248 absolute realism proof
  -> Doc252 micro real-human fidelity proof
  -> candidate Enhanced eligibility
  -> Formal Core may rank eligible candidates
```

Doc252 does not create a second winner path. It only contributes an eligibility
proof that can be included in a candidate summary.

### Runtime shape

The preferred implementation shape is:

1. A module-local evaluator that accepts already-safe visual evidence and emits
   a Doc252 proof.
2. A module-local prompt guidance adapter that can add micro-realism
   instructions when the trusted Host explicitly enables the profile.
3. A candidate-proof projection adapter that converts the module proof into the
   existing module-neutral Enhanced proof shape.
4. Tests proving that the module remains detachable.

### Activation condition

The module may be enabled only by a server-owned/trusted professional path. A
normal user payload must not be able to enable it as a hidden route switch or
as a way to bypass normal review.

Recommended activation metadata:

```text
profile_id = micro_real_human_fidelity_v1
enabled_by = server_feature_flag_v1
scope = character_card_face_identity / standard_front or another explicitly
        approved portrait-facing candidate scope
```

This is separate from transport route. Enabling Doc252 must not imply MCP,
Provider, retry, budget, or Brain-plan reuse.

The trusted Host remains the single prompt author. Doc252 may provide an
additive guidance fragment to that Host, but it must not create a second prompt
author, second Brain decision, or competing prompt rewrite.

## Prompt-side guidance boundary

The module may add prompt-side Enhanced guidance only through the trusted
professional Host path. Guidance must be phrased as photographic evidence, not
as defect injection:

Allowed:

- real photographed skin micro-texture without roughness;
- natural child/model-card hair randomness without messiness;
- subtle human eye and catchlight non-uniformity;
- clear but non-synthetic ear and garment detail;
- clean commercial retouch that preserves material realism.

Forbidden:

- "make it undetectable as AI";
- "add random noise";
- "make the face asymmetric";
- "add blemishes/dirt";
- "lower beauty or polish";
- route, budget, retry, or provider changes.

## Evaluation model

Doc252 proof should be produced from visible evidence, not from the prompt
alone. Valid evidence sources:

1. canonical shared Vision review dimensions;
2. Doc248 absolute realism review dimensions;
3. Doc252 micro-realism reviewer output;
4. optional ephemeral local measurements, if they are safe and non-biometric.

Invalid evidence sources:

- generic pass alone;
- prompt text alone;
- provider route choice;
- historical slot receipt;
- target-only collection;
- detector label or named-detector score.

## Commercial beauty preservation model

The module must preserve the current "beautiful commercial model card" target.
It should add natural photographic evidence, not reduce attractiveness.

Positive examples:

- clean luminous skin with visible pore-scale materiality;
- neat hair with naturally varied strand boundaries;
- attractive eyes with slightly non-mechanical catchlights;
- clear ears and garment texture that remain polished;
- high-key commercial lighting with believable tonal micro-variation.

Negative examples:

- rough documentary skin;
- obvious blemish injection;
- dirty hair or frizz that reads unstyled;
- harsh under-eye texture;
- noisy or compressed image texture;
- asymmetry that changes identity or beauty.

The beauty guard is not optional. A candidate with strong texture but reduced
commercial finish must be rejected by this profile.

## Same-person safety

Micro-realism must not redesign the person. It can increase material detail,
but identity-critical traits from the uploaded reference remain authoritative:

- eye shape relationship;
- nose/mouth relationship;
- face outline and cheek/jaw direction;
- age readability;
- complexion family;
- hairline/hair mass only when identity-relevant and prompt-compatible.

If a micro-realism change improves photographic feel but shifts identity, the
candidate fails.

## Public projection

Public summaries may expose only safe aggregate fields, for example:

- profile id;
- pass/fail status;
- safe dimension names and rounded scores;
- non-private issue codes;
- commercial beauty preserved true/false.

They must not expose:

- prompt text;
- provider or MCP route;
- handoff, artifact, or internal job IDs;
- local file paths;
- raw reviewer payloads;
- detector labels.

## Relationship to Doc248

Doc248 asks whether the portrait looks broadly photoreal and commercially
usable. Doc252 asks whether close inspection reveals real photographed
micro-evidence.

Doc252 may reuse Doc248 dimensions, but it must not collapse into Doc248:

- `human_realism` is not enough;
- `skin_micro_texture` must become more specific;
- hair, eyes, ears, garment, and camera response need their own visible proof;
- commercial beauty remains a hard guard.

## Development plan

### Phase 0 — document and evidence lock

- Preserve the Doc248 comparison evidence append-only.
- Record current winner and old baseline as comparable but non-strict A/B.
- Do not generate new pixels during documentation.

### Phase 1 — pure contract tests

Add module-only tests:

- missing micro proof fails closed;
- missing applicability/visibility receipt fails closed;
- invisible optional region with explicit safe `not_applicable` does not count
  as pass and does not block when profile minimums are satisfied;
- visible region marked `not_applicable` fails closed;
- empty evidence codes fail closed;
- NaN/infinite dimensions fail closed;
- beauty fail rejects even if texture passes;
- detector-evasion language is rejected;
- default disabled path leaves existing behavior unchanged;
- user payload or ordinary metadata cannot enable Doc252;
- trusted Host enablement creates only additive guidance, not a second prompt
  author;
- public summary leaks no prompt/path/provider/handoff/artifact IDs;
- module imports no Formal Core and changes no route/lifecycle code.

### Phase 2 — evaluator/proof adapter

Add the module evaluator and projection adapter, still without generating new
pixels:

- input is safe visual review evidence;
- output is candidate-bound Doc252 proof;
- missing evidence fails closed;
- proof can round-trip JSON;
- public projection is safe.

### Phase 3 — prompt guidance adapter

Add prompt-side guidance only after the proof contract is stable:

- guidance is enabled only by trusted Host;
- guidance is appended to the existing trusted Brain/Host prompt contract;
- guidance cannot become an independent prompt author or override current user
  intent;
- guidance cannot alter route, budget, retry, age, identity, or reference
  ownership;
- ordinary routes remain unchanged by default;
- no detector-evasion language is allowed.

### Phase 4 — controlled comparison

After pure tests pass and user approves:

- run one controlled standard-front comparison round;
- three candidates only;
- each candidate must receive shared Vision + Doc248 + Doc252 proof;
- Formal Core may select an ephemeral winner for comparison only;
- do not write Face slot or activation.

## Regression scope before controlled generation

Before any new image run, the following must remain green:

- Doc248 module boundary tests;
- Formal Core and receipt tests;
- Face formal-slot tests;
- Expression and Body formal receipt regressions;
- Provider/MCP contract tests proving the route did not change;
- public-projection sanitizer tests.

If any of these fail, do not generate images. Fix the owning layer first.

## Acceptance criteria

The upgraded module passes only if the selected candidate is:

- same person readable;
- commercially beautiful;
- clean model-card quality;
- visibly less synthetic in eyes, hair, skin, ears, garment, and light/camera
  response;
- not achieved through noise, ugliness, blur, or detector-specific tricks.

The correct product claim is:

```text
stronger visible evidence of real photographic capture while preserving
commercial beauty
```

not:

```text
undetectable AI
```

## Open decisions

1. Which profile minimums apply to tight headshots versus head-and-shoulders
   model-card crops.
2. Whether one visible ear is enough for ear-detail evaluation when both ears
   are not available.
3. Whether garment micro-texture is required only when garment/collar pixels
   are visible and reviewable.
4. Whether a local ephemeral micro-texture measurement is allowed as supporting
   evidence.
5. Whether Doc252 should apply only to `standard_front` first, then later to
   other portrait-facing views after separate calibration.
