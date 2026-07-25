# Doc257 — V3 Photographic Model-Card Simplification and Old Route Removal Plan

## Purpose

The latest visual comparisons changed the diagnosis.

The problem is not that the Professional Character Card path lacks more
realism constraints. The problem is that the active image-design route has
become over-constrained in the wrong direction.

The user target is:

```text
photographer-shot child model-card images,
standardized enough for a character card,
but still beautiful, natural, and commercially photographic.
```

The old high-quality direction already had the right visual instinct: simple
photographic language, natural model-card composition, clean studio light, and
commercial polish. The newer Doc248 / Doc252 / Doc253 / Doc254 / Doc255 stack
added too many proof-oriented rules to the generation target and pushed the
image toward a strict identity-verification headshot.

This document defines the cleanup:

1. keep the formal three-candidate / winner / receipt chain;
2. remove the active image-design routes that make outputs look like AI
   headshots or ID photos;
3. rebuild Face and Expression image goals around one simple photographic
   model-card family;
4. limit the actual implementation to prompt / negative-prompt projection and
   the image-constraint source that feeds that prompt.

Final narrowed boundary:

```text
Doc257 changes image language only.
It does not add a new quality gate.
It does not add a new Enhanced proof requirement.
It does not alter winner, receipt, save/reload, slot write, or activation.
```

## What the earlier better route did right

Current durable evidence does not contain the original upstream prompt that
created the user's canonical source image `v3_asset_054b1c4728614187`; that
asset is recorded as a user-supplied reference. However, the earlier
Professional Character Card front winner shows the closest available product
route before the later over-layering.

The older winner used a compact prompt shape:

```text
Vertical 2:3 reference card composition.
Six-year-old Chinese girl.
Head, neck, and upper shoulders.
Straight-on front view.
Identity from uploaded reference.
Cool fair skin with subtle camera-observed texture.
Bright clean studio lighting.
Commercially clean white seamless background.
Natural child-like expression.
Crisp photographic detail.
No waxy or plastic smoothing.
Simple standard character reference card.
```

Important traits:

- the target was a photographic reference card, not a compliance artifact;
- realism was expressed as natural photographic rendering, not as a detector
  checklist;
- identity preservation existed, but it did not dominate the whole image;
- crop language included neck and upper shoulders, leaving room for hair,
  collar, light, and body context;
- the prompt was short enough that the renderer could make an image, not merely
  satisfy a list of constraints.

The accidental out-of-band Codex preview is not valid Product API evidence, but
it visually confirmed the same lesson: a simpler photographer-style model-card
direction produced better beauty, presence, and human feel than the later
formal route.

## What went wrong

The newer route layered useful audit concepts into the wrong layer.

### 1. `standard_front` drifted into ID-photo language

The active route increasingly emphasized:

- strict straight-on front;
- face midline vertical;
- eyes level;
- nose centered;
- close crop;
- no half-body;
- quality strictness.

These terms are individually reasonable, but together they bias the renderer
toward an identity capture / ID-photo / AI headshot. The output becomes easier
to validate, but less like a photographer-shot child model card.

### 2. Realism became a prompt checklist

Doc248 and Doc252 introduced useful diagnostic language, but their active
production role encouraged prompt language such as:

- micro texture;
- natural eyes;
- hair, skin, ears, neckline;
- light-camera response;
- over-perfection penalty;
- absolute realism.

These should not be stacked into the renderer prompt. When they become active
prompt or negative-prompt clauses, the image feels mechanically optimized and
can amplify AI tells instead of removing them.

### 3. Framing proof and transport proof got confused

Canvas size, transport quality, white background, or a single `standard_front`
boolean does not prove model-card framing.

The correct crop must be judged visually:

- complete hair outline;
- controlled top margin;
- natural camera distance;
- visible neck;
- collar / upper shoulder context;
- no large torso or hand area;
- no face-only biometric crop.

### 4. Too many quality modules competed for one product goal

The previous stack tried to combine Doc248, Doc252, Doc253, Doc254, and Doc255
into a composite proof path. That was overbuilt for the product objective.

The system needs one simple Face / Expression model-card prompt direction, not
several separate product targets stacked on top of one another.

### 5. Auxiliary route repairs were mixed into product quality work

Brain, Provider, MCP continuation, and exact-bound recovery issues are real
engineering concerns. They are not part of the photographic model-card product
definition.

They must remain Auxiliary route/recovery tasks and must not drive realism or
framing design.

## Keep

The following work remains correct and must not be deleted, redesigned, or used
as the excuse for Doc257 changes:

- `standard_three_candidate` for official slot completion;
- real candidate evidence, including rejected candidates;
- canonical shared review as it already exists;
- existing external eligibility before ranking, where already required by the
  current slot flow;
- explicit ranking;
- one winner;
- per-slot `FormalSlotReceipt`;
- save -> reload -> safe public projection -> activation;
- fail-closed handling of target-only / legacy / auxiliary artifacts;
- historical compatibility reading without promotion.

This machinery is valuable. The wrong layer is the image-design target feeding
it.

## Phase 0 active-route inventory

This inventory is the authority for deciding what gets removed from active
production and what remains as compatibility. It is intentionally route-level,
not file-deletion-level.

| Layer | Current active / durable route observed | Current behavior | Classification | Doc257 disposition |
| --- | --- | --- | --- | --- |
| Public route payload | Character-card public routes do not expose ordinary user switches for Doc248 / Doc252 / Doc256. | Ordinary users cannot directly turn on the old realism prompt stack through the public request body. | Keep. | Preserve this boundary. Do not add a new public realism toggle. |
| Product API server metadata | Server-owned metadata can still carry `professional_absolute_portrait_realism_required`, `professional_micro_real_human_fidelity_required`, and `professional_photographic_model_card_front_required`. | Trusted internal paths can still activate old or mixed image-language routes. | Must narrow. | New Face / Expression production may only activate the Doc257 model-card prompt direction. Old metadata is compatibility readback only. |
| Library / Host Face preparation | Internal Face preparation can still accept `absolute_portrait_realism_required`, `micro_real_human_fidelity_required`, and `photographic_model_card_front_required`. | A trusted caller can still route new `standard_front` work into the old Doc248 / Doc252 prompt stack. | Must replace as one prompt model. | Keep signatures only if needed for compatibility, but prevent old flags from authoring new Face / Expression prompt or negative-prompt text. |
| Vision contract | Vision can request and return Doc248 / Doc252-specific score dimensions when old metadata is present. | Review can still be shaped by deprecated prompt/gate flags. | Must narrow. | New Doc257 work should not request old Doc248 / Doc252 product dimensions as active generation gates. AI-detectability remains post-generation observation only. |
| Face prompt projection | Face `standard_front` can still be driven by Doc248 / Doc252 / Doc256-oriented language. | Product language is over-layered and can prefer proof-oriented headshot behavior over photographer-shot model-card quality. | Must replace. | Face prompt language becomes the simplified photographer-shot model-card baseline + standard angle/crop wording only. Old proofs remain readable by profile version only. |
| Expression prompt projection | Expression delivery can inherit the same over-strict headshot language. | Expression can become an affect-on-ID-photo instead of a photographer-shot model-card expression. | Must narrow. | Expression prompt language inherits the same model-card family crop and adds only Expression-owned affect wording. It must not import Face-local implementation or upgrade legacy receipts. |
| Doc253 framing module | Standalone numeric framing envelope exists without approved production calibration. | Useful diagnosis, unsafe as a production numeric gate. | Freeze / diagnostic. | Keep as documentation/test history until a versioned calibration artifact is approved. Do not enable as default production gate. |
| Formal Core / receipt lifecycle | Formal Core only sees module-neutral eligibility and ranking; receipt lifecycle remains per-slot. | This is the correct acceptance machine. | Keep. | No Doc257, Doc248, Doc252, Face, Expression, or Body-specific branches may enter Formal Core. |
| Persistence / public projection / UI | Formal receipts and public summaries are the delivery authority; UI already hides 25-degree auxiliary Face views. | Correct direction. | Keep. | Do not promote historical / target-only / auxiliary artifacts. Public summaries must stay sanitized. |
| Tests | Doc248 / Doc252 tests still prove old modules and old gates; Doc256 tests prove the new contract modules. | Some tests will need migration from "active product gate" to "compatibility / not promoted." | Update by phase. | Red tests first: old flags no longer activate new production; old receipts remain readable but cannot upgrade. |

Inventory conclusion:

```text
The old switches are not mainly a public API problem.
They are an internal trusted-route prompt-projection problem.
Doc257 must remove their ability to author new Face / Expression image language.
```

## Delete from active production behavior

In this document, "delete" means remove from the active Face / Expression
generation prompt / negative-prompt path. It does not mean erasing historical files,
receipts, or evidence.

### Delete active Face `standard_front` headshot target

Remove any active prompt or profile wording that makes the front slot a
face-dominant identity-verification headshot.

Replacement:

```text
photographer-shot close child model-card front portrait
```

### Delete Doc248 / Doc252 as active Face product targets

Doc248 and Doc252 may remain as historical documents and possible evidence
vocabulary, but they must not remain active production gates for the new
model-card front target.

Replacement:

```text
existing shared Human Realism / photographic vocabulary
-> short positive model-card prompt language
-> no new Formal gate
```

### Delete detector-evasion language

Do not optimize for "unable to identify as AI." Do not add noise, blur,
compression, dirt, random asymmetry, or ugliness to defeat a classifier.

Replacement:

```text
visible human photographic language while preserving commercial beauty
```

AI-detectability boundary:

```text
"Could a viewer or detector call this AI?" is a post-generation observation.
It is not a generation prompt.
It is not a negative prompt.
It is not a retry condition.
It is not a Formal acceptance or activation condition.
```

Allowed use:

- after generation, record visible AI-looking artifacts in the comparison
  report;
- compare whether one output reads more photographic than another;
- use the observation to revise future product language after theory review.

Forbidden use:

- "make it undetectable as AI" in prompt or negative prompt;
- adding noise, compression, blur, fake pores, random defects, or ugliness;
- rejecting or retrying a candidate because of an AI detector score;
- changing Core / receipt / activation because a detector score changed.

### Delete prompt-level micro-defect patches

Do not append long eye / pore / hair / ear / fabric defect lists to the
renderer prompt.

Replacement:

```text
short positive photographer-language prompt;
no micro-defect checklist in the renderer prompt
```

### Delete transport-derived framing proof

Do not treat 1024x1536, quality mode, white background, or transport fingerprint
as crop proof.

Replacement:

```text
positive model-card angle / crop / distance wording in the prompt;
review may later observe framing, but Doc257 does not create a new Formal gate
```

### Delete production default numeric framing bands without calibration

No hard-coded crop bands may become production gates until a calibration
artifact exists.

Replacement:

```text
approved versioned model-card crop calibration,
with positive/negative examples and measurement definition
```

### Delete cross-module leakage

Face front framing is not Body. Expression can consume a neutral model-card
framing-family proof, but it must not import Face-local implementation.

Replacement:

```text
shared card-family framing language
Face owns front prompt wording
Expression owns affect prompt wording plus the same card-family crop language
```

## New product target

The new product target is not a new "absolute realism" module. It is a simpler
photographic direction:

```text
mature photographer-style model-card baseline
+ standard model-card angle / crop wording
+ existing shared quality vocabulary
```

The mature baseline is the useful part of the earlier successful output: the
image reads as a commercial photographer's child model card. Doc257 should
standardize that look, not replace it with compliance capture.

### Face standard front

The new Face front deliverable is:

```text
professional child model-card close front portrait
```

Required visual result:

- white or near-white studio background;
- child faces camera naturally;
- recognizable identity from reference;
- photographer-style commercial polish;
- complete hair outline;
- small but natural headroom;
- visible neck;
- visible collar / upper shoulders;
- no large torso or hand area;
- not a face-only crop;
- not a passport / ID / biometric capture;
- not an accidental half-body.

### Expression delivery slots

Expression slots inherit the same close model-card family crop:

```text
same photographic card family
+ Expression-owned affect delta
```

Expression prompt/review intent must keep two independent things clear:

1. card-family framing is still the visual family;
2. the requested affect is Expression-owned.

They cannot compensate for each other:

- affect pass cannot fix framing fail;
- framing pass cannot fix affect fail.

Face / Expression boundary:

| Responsibility | Face `standard_front` | Expression delivery |
| --- | --- | --- |
| Product visual family | Owns the close front model-card target for Face. | Inherits the same card-family crop language, but does not become a Face slot. |
| Affect | Neutral / natural child model-card expression unless the Face profile says otherwise. | Owned by Expression profile: laugh / anger / sad wording remains independent. |
| Framing wording | Uses card-family prompt wording for front angle, camera distance, headroom, neck, collar, and upper shoulders. | Uses the same card-family prompt wording, then adds only the requested affect. |
| Human realism wording | Uses mature photographic language already aligned with shared Human Realism principles. | Uses the same photographic baseline; affect remains Expression-owned. |
| Formal behavior | Unchanged; Doc257 does not create a new summary, gate, winner, or receipt. | Unchanged; Doc257 does not create a new summary, gate, winner, or receipt. |
| Forbidden | Importing Expression affect logic, activating 25-degree auxiliary views, or resurrecting Doc248 / Doc252 gates. | Importing Face-local implementation, using affect to repair framing, or upgrading legacy / target-only receipts. |

### Body slots

Body slots are not part of this simplification. Body keeps its own full-body
formal contracts and source/consent/reference rules.

### Card-family framing responsibility

Card-family framing is the only retained new positive prompt constraint. It
standardizes angle and crop without turning into a new Formal gate.

Renderer-facing Face / Expression prompt wording may include:

- full hair outline;
- headroom balance;
- visible neck;
- collar / upper-shoulder context;
- camera distance;
- no face-only biometric crop;
- no accidental half-body framing;
- round-level scale consistency across three candidates.

It must not include:

- biometric / ID-photo language;
- excessive face-midline / eye-level / symmetry instructions;
- micro-defect checklists;
- detector-evasion wording;
- fake-randomness, noise, blur, compression, or ugliness;
- a new pass/fail gate outside the existing review and FormalSlotReceipt chain.

Implementation rule:

```text
Use card-family framing to write better prompt language.
Do not use it to add a new Formal eligibility requirement.
```

Canvas size, transport quality, white background, and output dimensions may
support rendering, but they are not themselves the product target. The product
target is the visible photographer-shot model-card crop.

### Mature baseline responsibility

The mature photographic baseline owns the aesthetic direction:

- a real photographer could have shot it;
- the child looks naturally present rather than rendered as a symmetric icon;
- skin, hair, eyes, ears, wardrobe, and light feel photographic;
- beauty and commercial polish are preserved;
- the image remains a child model card, not an ID photo.

This baseline should be expressed through the existing Brain / Host prompt
authority as compact positive art direction. It should not be implemented as a
second realism evaluator, a long negative prompt, a detector-evasion module, or
extra Formal Core logic.

## New minimal architecture

Doc257 is deliberately smaller than the previous plan. It changes only the
prompt / negative-prompt projection layer and the source of those image
constraints. It does not change the acceptance machine and it does not
introduce a new review gate.

```text
Existing Brain / Host prompt authority
    -> removes old ID-photo / headshot / micro-defect / detector-evasion language
    -> keeps mature photographer-shot model-card language
    -> adds only positive card-family angle / crop / distance wording

Face standard_front prompt projection
    -> close front model-card portrait
    -> consistent headroom, full hair outline, neck, collar, upper shoulders

Expression delivery prompt projection
    -> same card-family crop language
    -> Expression-owned affect wording

Existing Formal chain
    -> unchanged
```

There is no new quality gate, no second winner, no second receipt, no route
selection, no retry condition, no activation path, and no special MCP/Provider
behavior inside Doc257.

Non-negotiable preservation boundary:

- `standard_three_candidate` stays exactly the official completion mode;
- winner selection stays in the existing Formal Core;
- `FormalSlotReceipt` remains the only formal slot authority;
- save -> reload -> public projection -> activation is not redesigned;
- old target-only / auxiliary / historical artifacts remain non-formal;
- no code in Core, receipt lifecycle, persistence, activation, or slot writing
  may be changed merely to adopt Doc257.

Review score / Doc256 evidence boundary:

```text
If review score or Doc256-specific evidence is missing, Doc257 does not
backfill it, synthesize it, or infer it from prompt text.
Prompt migration is allowed to improve the generation target only.
It must not forge review proof or alter formal eligibility.
```

Runtime boundary:

```text
Brain, Provider, MCP, and harness failures are validation/runtime issues.
They must be diagnosed separately.
They must not be mixed into Doc257 prompt migration.
```

## Prompt strategy

The renderer-facing prompt should be short, positive, and photographic.

Preferred shape:

```text
Vertical 2:3 studio model-card close portrait of a six-year-old Chinese girl,
same identity as the uploaded reference. Photographer-shot front-facing child
model card, natural camera distance, full hair outline, small headroom, visible
neck, collar and upper shoulders, clean white studio background, soft commercial
lighting, beautiful natural child presence, realistic skin and hair rendered as
a real camera photograph.
```

Avoid:

- long defect lists;
- "absolute" realism language;
- classifier / AI detector language;
- excessive geometric alignment wording;
- repeated negative prompt clauses;
- "not ID photo" as the main instruction;
- "not half-body" as the main instruction.

If exclusions are needed, keep them secondary and minimal. The main direction
must be the positive photography target.

## Post-generation visual comparison dimensions

Doc257 does not redefine official ranking, retry, or slot acceptance. The
following dimensions are used to compare whether the prompt migration improved
the image-design direction.

Suggested human review weights for comparison reports:

| Dimension | Weight |
| --- | ---: |
| Photographer-shot model-card beauty | 30% |
| Human photographic realism | 25% |
| Identity continuity | 20% |
| Crop / framing consistency | 15% |
| Commercial delivery cleanliness | 10% |

Visible problems to record in the comparison report:

- wrong person;
- face-only biometric crop;
- accidental half-body / too much torso;
- missing collar / shoulder context when required;
- obvious AI plastic skin, fake hair patch, dead symmetric eyes, or broken ears;
- expression affect failure for Expression slots.

These observations may inform the next prompt-design correction model, but they
must not directly become detector-evasion prompt text, automatic retry logic,
or a new FormalSlotReceipt / activation condition.

## Supersession status

| Prior doc/module | Status after Doc257 |
| --- | --- |
| Doc248 Absolute Portrait Realism | Deprecated as active Face/Expression product target. Historical evidence only. |
| Doc252 Micro Real-Human Fidelity | Deprecated as active production module. Its useful insight becomes ordinary photographic wording only, not prompt/gate stack. |
| Doc253 Standard-Front Framing Diagnosis | Superseded by model-card crop framing. Calibration lesson remains. |
| Doc254 composite Doc248+252 seam | Frozen. Do not extend. |
| Doc255 Doc252 evidence seam | Frozen. Do not extend for Face/Expression production target. |
| Doc256 photographic rebuild | Retained but narrowed by Doc257: simpler, fewer modules, no extra active Doc248/252 gating. |

Old receipts, old images, old comparison reports, and target-only compatibility
records are not deleted and are not upgraded. They remain readable under their
original profile version only.

## Old gate disposition matrix

| Old gate / field | Current risk | New-write behavior | Read behavior | Rollback behavior |
| --- | --- | --- | --- | --- |
| `absolute_portrait_realism_required` | Internal trusted callers can still activate Doc248-style headshot wording and gate behavior. | New Face / Expression production must not let this flag write prompt text, negative prompt text, review requirements, or gate conditions. | Existing records may be read under old profile version only. | Re-enable only by reverting the dedicated old-prompt-disabling commit, not by partial flag patches. |
| `professional_absolute_portrait_realism_required` metadata | Server-owned old metadata can still cause Vision/prompt paths to request old absolute realism dimensions. | Do not write it for new Doc257 Face / Expression jobs. | Existing durable metadata remains historical evidence. | Revert old-prompt-disabling commit if an emergency legacy run is required. |
| `micro_real_human_fidelity_required` | Can turn micro-defect checklist into active prompt, negative prompt, or pseudo-realism gate. | Do not activate for new Doc257 production. Do not replace it with a new micro-defect gate. | Keep old vocabulary readable; do not promote to new profile. | Revert only the bounded disable commit. |
| `professional_micro_real_human_fidelity_*` metadata / guidance | Can append checklist prompt guidance and request micro dimensions. | Do not write prompt guidance or dimension requests for new Doc257 Face / Expression jobs. | Historical records remain visible to internal compatibility readers only. | Revert bounded disable commit. |
| Doc253 numeric framing envelope | Could become hard-coded crop gate without approved calibration. | Do not enable as production gate. Keep only positive prompt wording for angle / crop / distance. | Diagnostic tests and documents remain. | No runtime rollback needed if never activated. |
| Doc254 Doc248+252 composite | Can stack two old product goals into one eligibility proof. | Freeze; no new active Face / Expression prompt/gate path. | Old profile receipts remain old profile receipts. | Revert only if the whole Doc257 direction is abandoned. |
| Doc255 evidence seam | Can encourage adding missing evidence plumbing to deprecated product goals. | Freeze for Face / Expression production. Do not backfill missing review evidence in this prompt migration. | Historical development evidence remains. | Revert only via dedicated compatibility task. |
| `photographic_model_card_front_required` | Correct direction, but can become over-layered if it stacks Doc248/252 or creates a new gate. | Retain only as Doc257 simplified prompt direction: mature photographic baseline + card-family angle/crop wording. | Old attempts under earlier Doc256 profile stay old profile. | Revert Doc257 prompt-projection commit if the new route fails visual acceptance. |

Disposition rule:

```text
Old gates may explain old records.
Old gates must not author new Face / Expression prompt, negative prompt, review
requirement, retry condition, or product success.
```

## Implementation phases

Each phase must be a separate, reviewable milestone. Do not mix documentation,
red tests, active-route removal, and visual validation in one commit.

The implementation is a minimal image-constraint migration, not a whole-system
refactor. The only active behavior to remove is the old image-design route:

```text
ID/headshot pressure
+ Doc248 absolute realism gate
+ Doc252 micro-defect gate/guidance
+ detector-evasion language
+ canvas/transport-as-framing proof
```

The active behavior to keep is:

```text
mature photographic model-card baseline
+ card-family angle/crop/framing prompt wording
+ existing three-candidate/winner/receipt chain
```

### Phase 0 — Active-route inventory and Doc257 finalization

Find every active call site that still treats Doc248 / Doc252 / Doc253 / Doc254
/ Doc255 as the Face `standard_front` or Expression delivery product target.

Output:

- file list;
- call-point list;
- whether it affects prompt, negative prompt, generation gate, review gate,
  retry, public summary, or tests;
- deletion / freeze recommendation.

No production behavior changes in this phase.

Expected commit:

```text
docs(doc257): finalize photographic model-card simplification plan
```

### Phase 1 — Red tests for deletion and replacement

Add only minimal tests proving:

- old ID/headshot, Doc248, Doc252, detector-evasion, and canvas-derived framing
  constraints no longer enter the active Face / Expression prompt or negative
  prompt route;
- new standard model-card angle / crop wording enters only the correct Face
  `standard_front` and Expression delivery prompt path;
- old Doc248 / Doc252 receipts remain compatibility-only and do not upgrade;
- existing Core / slot / receipt / save-reload / activation behavior is not
  modified.

Minimum test shape:

| Area | Required red-test intent |
| --- | --- |
| Old constraints removed | Old absolute realism / micro realism / detector-evasion / ID-headshot constraints cannot enter new Face or Expression prompt / negative prompt. |
| New framing enters correct paths | Face `standard_front` and Expression delivery receive standard model-card angle/crop prompt wording; Body, 25-degree auxiliary, target-only, and historical context do not. |
| Compatibility preserved | Old Doc248 / Doc252 profile records can be read but cannot become Doc257 prompt authority or new success proof. |
| Core regression smoke | Existing three-candidate winner, FormalSlotReceipt, save/reload, public projection, and activation narrow tests still pass without code changes in those layers. |

Expected commit:

```text
test(doc257): add active-route removal red tests
```

### Phase 2 — Remove active old route hooks

Disable or remove only active hooks that insert the old image-design stack into
new Face / Expression production.

Do not delete:

- historical docs;
- old receipts;
- evidence files;
- compatibility readers;
- test fixtures that prove old artifacts remain non-formal.

Minimum implementation boundary:

- stop new writes of old Face / Expression Doc248 / Doc252 metadata when those
  writes would affect prompt, negative prompt, generation gate, review gate, or
  retry;
- stop new prompt guidance from old micro-realism gates;
- stop ID/headshot and detector-evasion wording from entering the active
  model-card prompt contract;
- stop treating canvas size, transport quality, or white background as the
  source of crop/framing language;
- do not synthesize or backfill missing review score / Doc256 evidence;
- keep old modules importable for old-profile compatibility tests;
- keep old receipts and images untouched.

Do not change:

- Formal Core;
- winner selection;
- `FormalSlotReceipt`;
- catalog save/reload;
- public projection authority;
- activation validators;
- MCP / Provider routing;
- Brain / Provider / MCP / harness validation repairs;
- retry / budget / prompt-author ownership.

Expected commit:

```text
fix(doc257): disable deprecated Face Expression prompt hooks
```

### Phase 3 — Minimal model-card adapters

Keep the prompt projection changes small:

- one Face `standard_front` prompt projection;
- one Expression delivery prompt projection;
- one shared card-family wording source for angle, camera distance, headroom,
  neck, collar, and upper shoulders;
- unchanged common safety and quality negatives.

No new registry, no new route layer, no new receipt, no new Formal Core branch.
This phase only ensures the existing generation prompt can express the new
photographic model-card target.

Phase 3 must remain split:

| Subphase | Scope |
| --- | --- |
| 3A Face | Face `standard_front` receives mature model-card front prompt wording. |
| 3B Expression | Expression delivery receives the same card-family crop wording plus its own affect wording. |

Expected commits:

```text
fix(doc257): simplify Face model-card prompt projection
fix(doc257): simplify Expression model-card prompt projection
```

### Phase 4 — Controlled visual comparison

Before any broader rollout, run a controlled visual comparison:

- same canonical source;
- same provider / MCP route;
- same target view;
- one old route baseline;
- one new model-card route;
- no slot write, receipt, activation, retry, or route repair.

The evaluation must include human visual judgment, not only machine scores.
If the output becomes more compliant but less beautiful or less photographic,
the Doc257 image-constraint theory has failed even if machine checks pass.

Expected evidence:

- source hash;
- old baseline output id / hash;
- new output id / hash;
- route and prompt-authority summary;
- visible model-card crop / camera-distance observation;
- visible photographic realism / commercial beauty observation;
- post-generation AI-looking artifact observation;
- human visual comparison report.

AI-detectability is still only an observation field here. It must not become a
generation target, rejection rule, retry trigger, or Core/slot condition.

## Rollback and safety plan

Rollback must be boring.

| If this phase fails | Rollback action | What must not happen |
| --- | --- | --- |
| Phase 0 docs are wrong | Revert the doc commit only. | Do not touch code or receipts. |
| Phase 1 red tests are over-specified | Edit tests/docs before implementation. | Do not patch production to satisfy a bad theory. |
| Phase 2 old-prompt disabling breaks default behavior | Revert only the bounded disabling commit. | Do not restore old gates by adding hidden fallback flags. |
| Phase 3 Face prompt projection fails | Revert Face prompt-projection commit; Expression remains untouched. | Do not change Formal Core or Body to compensate. |
| Phase 3 Expression prompt projection fails | Revert Expression prompt-projection commit; Face remains untouched. | Do not promote target-only / legacy expression receipts. |
| Phase 4 visual output is worse | Keep formal chain, revise product prompt/model-card adapter theory. | Do not re-enable Doc248 / Doc252 checklist gates as a quick fix. |

Rollback invariants:

- never delete historical receipts, images, or evidence;
- never rewrite existing slot history;
- never make old target-only / auxiliary records formal;
- never change Formal Core semantics for image-quality rollback;
- never use AI-detectability as prompt text, negative prompt text, retry logic,
  or acceptance logic;
- never patch Brain / Provider / MCP / harness runtime issues inside Doc257;
- every code phase must be revertible without affecting previous durable
  assets.

## Acceptance criteria

Doc257 is complete only when:

1. the active Face/Expression image design no longer routes through Doc248 /
   Doc252 / Doc254 / Doc255 as production targets;
2. the generated front image reads like a photographer-shot child model card,
   not a standard ID headshot;
3. the crop is consistent: close model-card portrait, not half-body and not
   face-only;
4. commercial beauty is preserved or improved;
5. common safety and quality negatives are preserved while old micro-defect /
   detector-evasion negatives are removed;
6. Expression follows the same card-family visual baseline while keeping affect
   wording Expression-owned;
7. the three-candidate / winner / receipt / activation chain remains intact and
   unchanged in authority;
8. old compatibility records do not become new proof.

Short form:

```text
Use the old version's photographic simplicity.
Add only model-card crop standardization.
Keep the formal acceptance machine.
Delete the overbuilt image-design stack from active production.
```
