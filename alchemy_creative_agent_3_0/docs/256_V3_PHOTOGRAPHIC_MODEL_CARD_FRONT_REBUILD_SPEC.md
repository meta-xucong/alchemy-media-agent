# Doc256 — V3 Photographic Model-Card Front Rebuild Spec

## Purpose

The latest comparison exposed a product-definition error rather than a small
prompt or threshold defect.

The system optimized `standard_front` toward a clean identity-verification
headshot. The user goal is different:

```text
a close professional child model-card front photograph,
not a half-body portrait,
not an ID-photo style AI headshot.
```

This document resets the design around that product goal. It is intentionally
simpler than the Doc248 / Doc252 / Doc253 stack, but it must not fork shared
foundation realism:

1. one close model-card framing contract;
2. one photographic standardization contract;
3. one Face adapter that reuses shared Human Realism foundation evidence and
   binds it to the model-card candidate.

The old Formal Core, three-candidate receipt authority, and per-slot activation
rules remain useful foundation. They were not wasted work and must not be
removed. The wrong part is the Face `standard_front` deliverable definition and
the over-layered Enhanced image-design stack around it.

Keep the production acceptance chain:

```text
three real candidates
-> shared review
-> Face-local Enhanced eligibility
-> explicit ranking
-> winner
-> per-slot FormalSlotReceipt
-> save / reload / public projection / activation
```

Replace only the image-design target that feeds this chain. The new target is a
photographer-shot close model-card front image, not an AI-standardized identity
headshot.

Doc256 does **not** create a second generic realism evaluator. Eye, skin, hair,
garment, ear/temple, and light/camera realism remain shared Human Realism /
shared Vision foundation evidence. The Face-local module owns only:

- close model-card framing;
- front-card photographic standardization;
- candidate/output/operation binding of shared realism evidence into one Face
  `standard_front` Enhanced eligibility summary.

## Observed mismatch

Two outputs made the mismatch obvious:

- the out-of-band Codex preview was invalid as Product API evidence, but visually
  read closer to a photographer-shot child model card;
- the professional MCP output followed the formal route more closely, but read
  more like a standardized AI headshot.

The preview won visually because it preserved the photographic context:

- hair volume and flyaways;
- shoulder and collar information;
- a natural camera distance;
- less ID-photo rigidity;
- a more believable child model-card mood.

The professional output lost realism because its crop was too headshot-like.
That crop amplified AI-prone details in the eyes, skin, bangs, ears, and facial
symmetry.

Therefore the fix is not to add more micro-realism rules on top of a headshot
contract. The fix is to redefine the `standard_front` target as a close
photographic model-card crop, then evaluate realism inside that crop.

## Keep / remove split

This rebuild is a surgical product-design correction, not a rollback of the
formal architecture.

### Keep

Keep these foundations as authoritative:

- `standard_three_candidate` as the official Face slot completion mode;
- real candidate 1 / 2 / 3 evidence, including rejected attempts;
- canonical shared Vision review as the generic review authority;
- external Face-local Enhanced eligibility before ranking;
- explicit ranking key / scoring policy;
- one winner;
- per-slot `FormalSlotReceipt`;
- activation only after save -> reload -> safe public projection proof;
- target-only and auxiliary history remaining non-formal.

These are infrastructure wins from the previous work. They make the final
result auditable and prevent old boolean/stage receipts from faking success.

### Remove or supersede

Remove these active design ideas from the Face `standard_front` image path:

- `standard_front` means identity-verification headshot;
- higher realism means adding Doc248 and Doc252 as separate stacked modules;
- close face crop is safer because it is easier to review;
- micro-defect proof can compensate for wrong crop or wrong photographic
  language;
- transport canvas size proves visual framing;
- a valid front card may vary noticeably in camera distance across candidates.

Short form:

```text
Keep the acceptance machine.
Replace the picture it is trying to accept.
```

## Supersession and deprecation plan

Doc256 supersedes the active image-design intent and active production gating
role of the following documents for two related scopes:

1. **Professional Character Card Face `standard_front` final deliverables**;
2. **Professional Character Card Expression Set deliverables that inherit the
   front-card framing baseline**.

Expression Set does not become a Face module. Its affect / expression proof
remains Expression-owned. However, its visual card baseline must no longer
inherit an ID-photo-like front crop. It must consume the same neutral,
versioned close model-card framing-family evidence established by Doc256.

Expression must not import or call a Face-local
`photographic_model_card_front` implementation. The shared boundary between
Face and Expression is a neutral `card_family_framing` contract / proof emitted
by shared Vision or a shared framing adapter, then consumed by the owning slot
adapter.

| Document | New status for `standard_front` deliverable | What remains useful |
| --- | --- | --- |
| Doc248 Absolute Portrait Realism | Deprecated as the main product target. Its eight realism dimensions may be mined as evidence vocabulary only. | Beauty-preserving realism rule; prohibition on detector evasion. |
| Doc252 Micro Real-Human Fidelity | Deprecated as a standalone production module for `standard_front`. It must not remain a second prompt author or second Enhanced proof layer. | The insight that eyes, skin, hair, ears, garment, and light need visible evidence. |
| Doc253 Standard-Front Framing Diagnosis | Superseded by the close model-card framing redesign. Its diagnosis that framing belongs to Face, not Doc252, remains correct. | The separation between framing and realism; round-level scale variance concern. |
| Doc254 Doc252 Production Seam Plan | Frozen. Its composite Doc248+Doc252 proof approach is too complex for the corrected product goal. | The warning not to add a second winner/receipt authority. |
| Doc255 Doc252 Review Evidence Seam | Frozen. It should not be extended until the new model-card module decides which evidence it needs. | The provenance discipline for shared review evidence. |

Deprecation here does not mean immediate file deletion and does not invalidate
the formal slot-acceptance chain. It means:

- no new implementation should extend Doc248/252/254/255 for Face
  `standard_front`;
- tests that assert those documents as the production target must be rewritten
  under Doc256;
- old modules may remain as compatibility or historical evidence until a
  cleanup task removes their active imports safely;
- no old image-design proof may be promoted into Formal Core, slot receipts,
  public activation, or route selection.
- old Doc248 / Doc252 receipts and comparison summaries remain readable as
  their original profile versions only;
- the new Doc256 profile must not retroactively upgrade an old winner,
  target-only record, auxiliary record, or legacy receipt into Doc256
  completion.

Short form:

```text
Doc248/252 were useful experiments.
Doc256 becomes the product authority for Face standard_front.
```

## What to delete or disable from the old image design

The following old image-design ideas should be removed from the active Face
`standard_front` path after Doc256 tests exist. Do not remove the formal
candidate/winner/receipt chain.

1. **`standard_front` as an identity-verification close headshot**

   Delete any wording, prompt guidance, or review expectation that makes the
   official front card a big-face ID-photo crop. Identity evidence remains
   required, but the deliverable is a photographer-shot close model-card crop.

2. **Separate “absolute realism” and “micro fidelity” production gates**

   Do not keep two independent Face-front Enhanced modules that can override,
   duplicate, or shadow each other. The new path emits one Face-local
   `photographic_model_card_front` eligibility summary.

3. **Micro-realism as a prompt patch**

   Do not append long technical micro-defect language to a prompt that still
   asks for a rigid headshot. The photographic model-card framing and realism
   must be authored as one coherent photo direction.

4. **Detector-evasion framing**

   Delete any acceptance language that treats “not detected as AI” as the goal.
   The goal is visible photographic evidence and commercial believability. No
   noise, blur, compression, dirt, ugliness, random asymmetry injection, or
   classifier-specific evasion.

5. **Doc253 numeric envelope as a standalone production default**

   Do not hard-code old numeric bands from a failed comparison. Numeric
   constraints may be introduced only through a new Doc256 calibration artifact
   that describes the close model-card crop.

6. **Route/Brain/MCP recovery as part of the realism feature**

   Professional route repairs remain Auxiliary. They cannot be mixed into the
   photographic model-card module and cannot be used to explain visual quality.

7. **Formal Core awareness of beauty, realism, or crop details**

   Formal Core still sees only reviewed candidates, shared review, external
   eligibility, and ranking. It must not know Doc256-specific eye, skin, hair,
   garment, or framing variables.

## New product definition

The official Face `standard_front` deliverable is:

```text
professional_child_close_model_card_front_v1
```

Human-readable definition:

```text
A close professional child model-card front photograph on a clean studio
background. The child faces the camera directly. The crop is close but not
ID-photo-like: full hair silhouette, face, ears/temple region where visible,
neck, collar, and upper shoulder line are present. The lower crop lands around
the collarbone / upper-chest entrance, not at the chin and not at half-body.
The image is commercially polished while preserving visible real-photographic
skin, hair, eye, garment, and light behavior.
```

Non-goals:

- not a half-body portrait;
- not a full-body image;
- not a passport / school-ID / database headshot;
- not a beauty retouch that erases real materiality;
- not an anti-detector or noise-based realism trick.

## Expression Set impact

The Expression Set was also affected by the old mistake because anger, sad,
laugh, and any future explicit expression slot use the front card as their
visual baseline. If `face.front` is an ID-photo-like AI headshot, expression
candidates tend to preserve that rigid crop and become "emotion variants of a
certificate photo" instead of photographer-shot model-card expression plates.

Doc256 therefore changes the baseline evidence that Expression inherits:

```text
expression slot = same close model-card photographic card family
                + Expression-owned affect / facial-performance delta
```

Expression Set must keep these boundaries:

- it consumes the close model-card crop as neutral versioned
  `card_family_framing` evidence;
- it does not define its own Face framing envelope;
- it does not import or call Face-local `photographic_model_card_front` code;
- it does not own the framing calibration artifact;
- it does not call Doc256 to judge affect quality;
- anger / sad / laugh affect evidence remains Expression Enhanced proof;
- Expression candidates must keep the same camera distance, head scale, collar
  visibility, background, and commercial photography language as the accepted
  front-card family;
- Expression must not regress into an ID-photo crop merely because the face is
  easier to compare;
- Expression must not expand into half-body or editorial portraits unless a
  separate Expression-specific deliverable says so;
- `expression.smile` remains explicit / legacy according to its existing
  contract and is not silently promoted by Doc256.

Neutral framing-contract rules for Expression:

- the calibration artifact may be shared only as
  `close_model_card_framing_family_calibration_v1`;
- applicability is limited to Face `standard_front` and Professional
  Expression delivery slots that explicitly inherit the same card-family
  baseline;
- Expression remains `expression_set`, not a Face slot;
- Body, 25-degree auxiliary bridges, target-only history, and generic
  non-professional outputs must not consume this artifact;
- old Expression receipts keep their old profile/version and cannot be upgraded
  into Doc256 card-family framing completion;
- new Expression candidates must bind framing proof to `candidate_id`,
  `output_id`, `operation_id`, `slot_key`, and `round_id`.

The Expression acceptance chain remains unchanged:

```text
three expression candidates
-> canonical shared Vision
-> Expression affect Enhanced eligibility
-> inherited Doc256 card-family framing eligibility
-> explicit ranking
-> per-slot FormalSlotReceipt
```

Formal Core still receives only one module-neutral enhanced summary for each
Expression candidate. The Expression adapter may compose affect proof and
card-family framing proof before calling Formal Core, but it must not create a
second winner, receipt, slot state, or activation authority.

Expression-specific red tests must prove:

1. anger / sad / laugh do not inherit an ID-photo front crop;
2. expression candidates keep the close model-card crop and same-round scale
   consistency;
3. Expression affect pass cannot compensate for a wrong crop;
4. Doc256 framing pass cannot compensate for failed affect proof;
5. Face `standard_front` and Expression slots use the same card-family framing
   calibration artifact, but different Enhanced profile ids;
6. Expression cannot import Face-local photographic model-card implementation;
7. Expression adapter fails if framing proof lacks candidate/output/operation/
   slot/round binding;
8. Expression does not import Doc256 realism as a second generic evaluator;
9. old target-only / legacy expression material remains compatibility-only and
   is not upgraded to Doc256 completion.

## New module shape

Create one Face-local Enhanced module:

```text
photographic_model_card_front_v1
```

It owns three subcontracts. The third subcontract is an adapter over shared
Human Realism evidence, not a copied evaluator.

### 1. Close model-card framing

Owner: Face `standard_front` view-role profile.

Purpose: keep every candidate in the same close model-card crop.

Required visible structure:

- 1024 x 1536 vertical canvas remains the transport size;
- face is front-facing and centered;
- full head and hair silhouette are visible;
- no crown or primary hair volume is cropped;
- eyes are level enough for a professional model card;
- neck and collar are visible;
- shoulder line / upper shoulder entry is visible;
- lower frame lands around collarbone / upper-chest entrance;
- crop is closer than a half-body portrait but wider than an ID headshot;
- three candidates in the same round have near-identical subject scale.

This subcontract must reject:

- ID-photo-like big head crop;
- chin-to-forehead face crop;
- missing shoulders or collar;
- half-body expansion;
- inconsistent candidate-to-candidate camera distance;
- using canvas size alone as proof of framing.

Calibration:

- numeric bands must come from `close_model_card_framing_family_calibration_v1`;
- no production default may hard-code unreviewed thresholds;
- the calibration artifact must include positive and negative examples, human
  labels, target face / head / upper-shoulder ratios, and allowed variance.
- pass/fail must be proven by canonical shared Vision / Face adapter dimensions,
  not by prompt text, 1024 x 1536 canvas size, or a single boolean flag;
- round-level variance must bind `candidate_id`, `output_id`, `operation_id`,
  and `round_id` so candidates from different operations cannot be stitched into
  a fake consistent round.

### 2. Photographic standardization

Owner: Face `standard_front` prompt/review adapter.

Purpose: make the result look like one photographer and one studio setup, not
three unrelated AI interpretations.

Required consistency:

- same clean background family;
- same camera distance and lens feel;
- same high-key commercial lighting family;
- same neutral front-facing attention;
- same age-appropriate simple clothing role unless user asks otherwise;
- reference identity remains source-owned;
- hair, clothing, scene, and lighting remain prompt-owned unless explicitly
  locked by the user.

This subcontract must reject:

- a candidate that changes from close model-card crop to portrait crop;
- fashion/editorial pose replacing model-card front;
- expression performance replacing neutral child model-card attention;
- copying full-frame source style when only identity was source-owned.

### 3. Shared Human Realism evidence binding

Owner: shared Human Realism / shared Vision foundation produces the evidence;
Face-local Doc256 adapter binds that evidence to the `standard_front` model-card
candidate.

Purpose: make the image read like a refined real photograph without sacrificing
commercial beauty, while avoiding a second generic realism implementation.

Required shared foundation evidence, bound through the Face adapter:

- eyes: non-mechanical gaze, plausible catchlights, non-mirrored eyelid/iris
  detail, natural sclera materiality;
- skin: child-appropriate fine texture, tonal variation, subtle redness or
  shadow where natural, no ceramic smoothing;
- hair: varied strand width, flyaways, temple/ear-side growth continuity, no
  pasted wig-sheet edges;
- ears / temple region: believable anatomy when visible; if partially hidden,
  visibility must be recorded rather than treated as pass;
- garment: collar or shirt fabric has real weave/tension, not smooth plastic;
- lighting: studio polish with real falloff, no flat AI airbrush;
- commercial beauty: clean, appealing, bright, gentle, and premium.

The Face-local adapter must reject:

- ugly realism;
- random noise or artificial dirt;
- blur as realism;
- forced asymmetry that changes identity;
- skin roughening that makes the child look tired, older, dirty, or less
  commercially usable.

The adapter must not:

- implement a second eye / skin / hair / ear / garment / light evaluator;
- invent missing visibility or applicability evidence;
- convert shared Human Realism failure into pass;
- use "AI detector says real" as evidence;
- promise that an image is impossible to identify as AI.

## Single eligibility output

The new module emits one candidate-level summary:

```text
profile_id = photographic_model_card_front_v1
requirement_id = close_model_card_front_beautiful_real_photo_v1
```

It may internally keep separate proof blocks:

- `framing_proof`;
- `standardization_proof`;
- `shared_human_realism_binding_proof`;
- `commercial_beauty_proof`.

However, only one module-neutral enhanced eligibility summary is passed to
Formal Core.

Formal Core remains unchanged:

```text
candidate(s) -> generic shared review -> external eligibility -> ranking -> winner -> receipt
```

No Doc256 code may import Formal Core for evaluation, and Formal Core must not
contain Doc256 tokens.

Profile compatibility rules:

- `photographic_model_card_front_v1` produces only new candidate-level Enhanced
  proof;
- old Doc248 / Doc252 profile ids remain old profile ids;
- a candidate may carry historical Doc248 / Doc252 evidence for audit, but the
  active Doc256 eligibility summary must say which profile/version owns the
  current decision;
- Formal Core still receives exactly one module-neutral enhanced summary per
  candidate;
- Doc256 must not create a second winner, receipt, slot state, or activation
  authority.

## Prompt strategy

The prompt should become simpler, not longer.

The Brain / trusted Host should author one coherent photographer instruction:

```text
professional child close model-card front photograph, clean white studio
background, direct front gaze, full hair silhouette, face, neck, collar and
upper shoulder line visible, close crop but not ID-photo big-head crop, bright
commercial studio finish, real photographed skin and hair materiality,
age-appropriate simple clothing, natural child presence
```

Negative guidance should also be short:

```text
no ID-photo crop, no oversized head crop, no half-body expansion, no plastic
skin, no mirrored eyes, no wig-like hair sheet, no fake noise or dirty realism
```

The prompt must not:

- add a second prompt author;
- override source identity;
- lock source hair / outfit / lighting unless the user did;
- change route, retry, budget, or Provider/MCP transport.

## Ranking policy

When three candidates exist, ranking should be simple and product-facing:

1. close model-card framing fit;
2. same-round framing consistency;
3. identity fidelity to the canonical original;
4. beauty-preserving photographic realism;
5. commercial model-card usability;
6. absence of visible AI portrait artifacts.

A candidate cannot win when:

- it is the most realistic but has the wrong crop;
- it has the correct crop but reads as a synthetic ID headshot;
- it is beautiful but loses the source identity;
- it uses ugliness, noise, blur, or texture damage to appear real.

## Public and persistence boundaries

Doc256 is an Enhanced quality/profile contract. It does not change:

- `FormalSlotAcceptanceCore`;
- `FormalSlotReceipt`;
- save / reload / public projection lifecycle;
- activation validation;
- Expression Set;
- Body Silhouette;
- 25-degree auxiliary bridge semantics;
- target-only historical collection;
- Provider/MCP recovery.

Public summaries may expose safe status, dimensions, profile version, and issue
codes such as:

- `close_model_card_framing_passed`;
- `id_photo_crop_rejected`;
- `candidate_scale_variance_failed`;
- `photographic_realism_passed`;
- `plastic_skin_rejected`;
- `commercial_beauty_preserved`.

They must not expose:

- prompts;
- provider payloads;
- MCP handoff ids;
- filesystem paths;
- private reference hashes;
- raw model output payloads.

## Implementation plan

### Phase 0 — Document supersession

1. Add Doc256 as the new authority.
2. Mark Doc248 / Doc252 / Doc253 / Doc254 / Doc255 as historical or
   superseded for Face `standard_front` production intent.
3. Do not delete old files until tests prove their active imports are no longer
   used by the new path.

### Phase 1 — Red tests

Add tests before production code:

1. old Doc252 / Doc248 flags no longer define the Face `standard_front`
   product target;
2. old Doc248 / Doc252 receipts are compatibility-readable but do not become
   Doc256 completion;
3. new and old profile versions cannot be mixed into one fake proof;
4. shared Human Realism evidence is consumed through an adapter; Doc256 does not
   duplicate generic eye / skin / hair / light evaluator logic;
5. `standard_front` rejects ID-photo-like crop even when shared realism passes;
6. `standard_front` rejects half-body expansion even when identity passes;
7. three candidates with visible subject-scale drift fail round consistency;
8. variance proof fails when candidate/output/operation/round binding is
   missing or mismatched;
9. prompt wording, canvas size, and booleans cannot satisfy framing proof;
10. close model-card crop passes only when hair, face, neck, collar, and upper
   shoulder line are visible;
11. shared Human Realism failure on mirrored eyes, plastic skin, wig-like hair,
    garment plasticity, or light/camera evidence makes Doc256 ineligible when
    that evidence is required;
12. beauty degradation fails even when texture is high;
13. "AI detector passed" or classifier-evasion metadata is ignored / rejected;
14. Formal Core remains unaware of Doc256 tokens;
15. Expression / Body / 25-degree auxiliary paths remain unchanged.

### Phase 2 — New standalone contract module

Create a Face-local module, for example:

```text
visual_assets.photographic_model_card_front
```

It should implement:

- close model-card framing proof model;
- photographic standardization proof model;
- shared Human Realism evidence binding proof model;
- one composite candidate eligibility summary;
- safe public summary.

It must not import:

- Formal Core;
- Provider/MCP route code;
- Expression/Body modules;
- slot activation or receipt lifecycle.

### Phase 3A — Face trusted Host integration

Only after Phase 2 tests pass:

1. replace Doc248/Doc252 prompt fragments for Face `standard_front` with the
   unified Doc256 photographer instruction;
2. keep route selection explicit and unchanged;
3. project shared Vision evidence into Doc256 proof;
4. emit one module-neutral enhanced eligibility summary;
5. keep old Doc248/Doc252 compatibility tests only for historical records.

This phase must touch Face `standard_front` only. It must not modify Expression,
Body, Formal Core, Provider/MCP recovery, or old receipt lifecycle.

### Phase 3B — Expression delivery-slot seam

Only after Phase 3A passes:

1. expose the neutral `card_family_framing` proof from the shared framing owner;
2. let Expression adapters consume that proof without importing Face-local code;
3. compose `card_family_framing` proof with Expression-owned affect proof into
   one module-neutral Enhanced summary;
4. keep target-only and legacy Expression receipts compatibility-only;
5. keep Formal Core unchanged.

Phase 3B must be a separate task from Phase 3A. It must not modify Face
generation behavior, Doc256 Face prompt integration, Body, Provider/MCP
recovery, or receipt lifecycle.

### Phase 4 — Calibration

Create a reviewed calibration artifact:

```text
close_model_card_framing_family_calibration_v1
```

It must include:

- accepted close model-card examples;
- rejected ID-photo crops;
- rejected half-body crops;
- accepted and rejected candidate-scale variance examples;
- face/head/shoulder/collar measurement definitions;
- versioned numeric bands;
- reviewer notes explaining why the crop is not half-body.
- source of the examples;
- reviewer / approval metadata;
- calibration version;
- applicability scope: Face `standard_front` formal slot and Professional
  Expression delivery slots that explicitly inherit the same card-family
  baseline.

No numeric production threshold should be enabled before this artifact exists.

### Phase 5 — Controlled comparison

Only after Phases 1-4:

1. use the same canonical source;
2. generate exactly three `standard_front` candidates;
3. keep route fixed and explicit;
4. no retries, no fallback, no prompt tweaks mid-run;
5. compare the Doc256 winner against:
   - old formal winner;
   - invalid Codex preview as a visual reference only;
6. report whether the result preserves:
   - close crop consistency;
   - model-card photography feel;
   - identity;
   - commercial beauty;
   - reduced visible AI artifacts.

## Acceptance criteria

Doc256 is successful only when:

1. `standard_front` no longer reads as an ID-photo AI headshot;
2. it also does not drift into half-body portrait framing;
3. three candidates share the same close model-card crop;
4. the winning image has shared Human Realism evidence for real-photographic
   eye, skin, hair, garment, ear/temple, and lighting behavior where
   applicable;
5. commercial beauty is preserved or improved;
6. Formal Core and receipt authority remain unchanged;
7. public projection remains safe;
8. old Doc248/252 complexity is not extended.

The final human-facing report may discuss visible AI artifacts, but it must not
claim detector evasion, must not claim that the image is impossible to identify
as AI-generated, and must not promise that a classifier or reviewer cannot
identify the image as generated.

Short form:

```text
Stop building a better AI headshot.
Build a photographer-shot close child model card.
```
