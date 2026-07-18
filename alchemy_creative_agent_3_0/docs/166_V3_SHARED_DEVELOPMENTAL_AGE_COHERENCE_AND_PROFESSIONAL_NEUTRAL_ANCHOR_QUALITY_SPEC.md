# Doc166 — V3 Shared Developmental-Age Coherence and Professional Neutral-Anchor Quality Spec

## Status

```text
DEVELOPMENT_SPEC_READY
IMPLEMENTATION_NOT_STARTED
DOC165_TECHNICAL_M5_EXECUTION_EVIDENCE_REMAINS_VALID
APPROXIMATELY_SIX_YEAR_OLD_VISUAL_QUALITY_ACCEPTANCE_REOPENED
PRODUCTION_AND_BROWSER_GATE_UNCHANGED
```

## 1. Why this document exists

Doc165 completed the formal local Professional M5 execution sequence for one
People Asset:

```text
standard_front winner
  -> three_quarter winner
  -> profile winner
  -> shared real-pixel review
  -> explicit pack activation
```

That result remains valid evidence for lifecycle, serial reference admission,
canonical prompt/reference parity, view-role sign-off, shared review, bounded
repair, winner persistence and activation. A later human visual audit exposed a
different gap: the selected views did not consistently read as the requested
approximately-six-year-old person and did not meet the intended clean commercial
model-card presentation.

The audit compared the M5 winners with three user-supplied, real child-model
boards retained outside Git:

- two lively models aged a little under six;
- one neutral/cool-expression model at approximately six, used as the primary
  developmental-shape benchmark independently of expression;
- the previously accepted adult commercial complexion sample, used only for
  clean color/material direction rather than identity or age transfer.

No benchmark media, biometric vector, face embedding, full prompt, private path
or provider response is committed by this specification. The boards are a
controlled human-evaluation reference, not a runtime identity source, renderer
input, demographic template or fixed palette.

The observed M5 quality gap was:

1. insufficient age-appropriate cheek and lower-face volume;
2. an older, camera-trained gaze even when facial size was made younger;
3. adult-polished mouth, lip and tooth presentation;
4. yellow/grey/muddy complexion and synthetic grain or smearing;
5. mature neck/shoulder presentation and one adult-formal wardrobe result;
6. grey, inconsistent backgrounds rather than a clean high-key neutral capture;
7. apparent age drifting across front, three-quarter and profile views.

This is not evidence for a child module or a longer prompt word list. It is
evidence that the existing shared age-fidelity obligation and the Professional
anchor-capture quality objective need one coherent semantic closure.

## 2. Authority and compatibility

Doc166 extends, but does not replace:

```text
Doc91   Human Realism ownership
Doc93   reference-channel and current-prompt ownership
Doc94   anti-overfitting and no narrow runtime profile governance
Doc95   complementary portrait identity evidence and best result selection
Doc96   high-fidelity identity execution and bounded repair
Doc155  expression resolution and cross-age adaptation
Doc157  same-person age transition and source-age non-inheritance
Doc159  explicit commercial complexion preference and neutral white balance
Doc160  bounded review observations returned to Brain for whole-prompt repair
Doc161  Brain reference-ownership sign-off and identity-evidence isolation
Doc163  face-localized identity evidence
Doc164  viewpoint-aware identity evidence fusion
Doc165  Professional view sign-off, repair budget and technical M5 record
```

Precedence is explicit:

1. Doc165 remains the historical and technical execution acceptance record for
   its exact run.
2. Doc166 reopens only the clarified visual-quality claim for an approximately
   six-year-old clean commercial model-card anchor.
3. A Doc165 identity/view pass cannot by itself certify developmental age,
   age-consistent presence, commercial complexion, capture cleanliness or
   age-appropriate styling.
4. Doc157 remains the authority that target age may change while identity
   continuity remains. Doc166 strengthens how that decision is materialized and
   reviewed; it does not add another age state machine.
5. Doc159 remains the complexion authority. Doc166 applies it only when the
   user or selected Professional brief owns that commercial presentation.

Nothing in this document lowers the existing identity, Human Realism, pose,
visual-quality or review-certification gates.

## 3. Architectural decision

The framework does not change. The accepted path remains:

```text
user intent + reference ownership + selected Professional binding
  -> Remote Brain complete semantic resolution
  -> frozen CapabilityActivationPlan / execution envelope / ledger
  -> Remote Brain complete canonical Provider prompt and typed receipts
  -> GPT Image 2 or exact canonical Local MCP relay
  -> shared vision/hybrid pixel review
  -> existing bounded Brain-owned complete rewrite
  -> append-only winner selection and activation
```

Doc166 makes two refinements inside existing owners:

1. shared Human Realism must treat requested developmental age as a
   whole-person coherence obligation rather than a face-size adjustment;
2. Professional Face Identity preparation must declare a neutral evidence-
   capture presentation, so view changes are not confounded by adult wardrobe,
   grey low-key sets or inconsistent photographic treatment.

The Remote Brain remains the sole author of the final natural-language renderer
prompt. Runtime code may carry facts, ownership, obligations, hashes and typed
receipts. It may not append facial anatomy prose, age words, skin words,
wardrobe words, a negative list or a retry patch after Brain sign-off.

## 4. Benchmark interpretation

### 4.1 What the controlled child benchmarks establish

The under-six lively boards and the approximately-six neutral board show that
expression is not the definition of age. A smiling child and a cool-expression
child may both communicate the same developmental stage through a coherent
relationship among:

- upper-face and forehead presence;
- cheek and mid-face volume;
- lower-face length and jaw/chin softness;
- eye attention and degree of camera-performance awareness;
- mouth, lip and visible dentition presentation;
- head, neck, shoulder and visible-body relationship;
- skin color/material under clean photographic light.

These are human-evaluation dimensions, not a renderer checklist. The neutral
approximately-six board is especially useful because it demonstrates child
facial character without relying on a smile, enlarged eyes or exaggerated
roundness.

### 4.2 What the benchmarks do not authorize

The implementation must not:

- copy a benchmark person's identity, facial layout, hairstyle, expression,
  clothing or pose;
- infer that every child must have a round face, large eyes or visible teeth;
- introduce a fixed `baby fat`, tooth, gaze, smile or head-ratio recipe;
- classify age, ethnicity, beauty or skin color through keywords or regex;
- convert the adult complexion sample into a universal skin template;
- use fixed RGB/HSL/lightness values, whitening filters or local skin edits;
- send the benchmark boards to Provider/MCP as identity references unless a
  future, independently authorized workflow explicitly assigns that right.

The benchmark is used to judge developmental coherence and photographic finish,
not to define a demographic archetype.

## 5. Shared Human Realism refinement

### 5.1 Whole-person developmental-age coherence

The existing `identity_age_fidelity` obligation must be interpreted as a
whole-person requirement. When a target age is explicit, the Brain must
reconcile facial maturity, gaze, expression, visible mouth/teeth, skin response,
neck/shoulder relationship, body proportion and styling as one believable
person at that developmental stage.

The runtime does not decide how any individual feature should look. It carries
the target-age fact, source-age ownership decision and existing Human Realism
obligation to final sign-off. The Brain decides the complete image direction.

### 5.2 Same-person age transition

For an explicit same-person age transition:

```text
preserve identity-critical feature relationships
+ preserve recognizable individual character
+ re-express developmental age as owned by the current request
+ do not inherit source-age maturity by default
```

The source portrait may remain authoritative for identity geometry while being
non-authoritative for apparent age, body maturity, expression maturity,
wardrobe, scene, light and camera. The Brain must resolve that distinction
before signing the canonical prompt.

A same-person request without an explicit age change keeps the existing age
continuity semantics. A new person at a stated age uses the same shared Human
Realism path without entering an age-transition branch.

### 5.3 Gaze and expression

The existing Doc155 expression-resolution contract remains authoritative.
Doc166 clarifies that developmental-age coherence includes the person's degree
of deliberate camera performance. The result may smile, remain neutral, look
away or show a quiet expression according to user intent and scene. The Brain
must not equate commercial attractiveness with an adult-trained gaze or a
single polished tooth-showing expression.

No expression catalogue is introduced. Pixel review judges whether the visible
expression and attention belong to the requested person and moment, including
their requested age.

### 5.4 Skin material and commercial complexion

When the user or selected Professional brief explicitly owns a bright commercial
complexion direction, Doc159 applies. The desired reading is:

- bright, clean and naturally fair rather than yellow, orange, grey or muddy;
- neutral with restrained peach-pink vitality rather than bleached white;
- age-appropriate natural smoothness with subtle camera-resolved variation;
- clean shadow color around cheeks, nose, mouth, jaw and neck;
- restrained highlights that follow facial planes without oily sheen, waxiness
  or global glow;
- no synthetic grain, painterly smearing or fake pore texture added merely to
  signal realism.

This is a complete photographic-material decision by the Brain, not a local
skin treatment. It is active only when owned by the user/brief. Documentary,
low-key, tanned, moody, historical and other prompt-owned complexion directions
must remain unchanged.

## 6. Professional neutral anchor-capture refinement

### 6.1 Scope

This section applies only while preparing a Professional Face Identity anchor
pack. It does not change Standard Mode, General, E-Commerce, Photography or
ordinary Professional delivery imagery.

The existing Professional typed quality contract gains one semantic objective:

```text
neutral_identity_evidence_capture
```

This objective means that the capture should make identity and cross-view
comparison legible without introducing a new visual persona. It is not a local
prompt recipe.

### 6.2 Required presentation outcome

For the controlled approximately-six-year-old acceptance, the Brain should
resolve the neutral capture as:

- a genuinely white or near-white seamless background without a dirty grey
  vignette;
- bright, clean, high-key photographic light with enough modelling to preserve
  real facial form;
- neutral white balance and stable complexion across all views;
- simple, light, age-appropriate neutral clothing;
- no adult occupational suit, mature fashion styling, makeup or pageant finish;
- consistent hair presentation, crop, exposure and photographic finish across
  the required views;
- visible neck and shoulders that remain developmentally coherent;
- only the requested view changes between front, three-quarter and profile.

These are acceptance outcomes authored by the Brain from the typed objective.
The local runtime must not materialize them as a hard-coded prompt paragraph.

### 6.3 Identity versus capture continuity

The anchor pack continues to own only face-identity evidence. Neutral clothing,
white background and capture light make evidence comparable; they do not become
reusable identity channels in later Professional jobs. Hair, wardrobe, light,
scene, camera, mood and style remain current-prompt owned unless explicitly
assigned under Doc93.

Changing an anchor-stage shirt or background in a way that introduces adult
semantics, age drift or a materially different finish is a capture-consistency
failure, not a new identity truth.

## 7. Brain final sign-off

The finalizer must give the Remote Brain enough typed context to reconcile:

1. target age;
2. same-person continuity versus source-age non-inheritance;
3. current-request-owned expression and styling;
4. Human Realism developmental coherence;
5. Doc159 commercial complexion ownership when applicable;
6. Professional `neutral_identity_evidence_capture` when preparing anchors;
7. exact frozen anchor view from Doc165;
8. prior shared review observations during the one existing repair.

The Brain must return complete canonical prompt output plus schema-only receipts
showing that it resolved the applicable obligations. Receipt validation checks
shape, binding and exact typed-decision parity only. It must never scan prompt
text for child, age, cheek, eye, tooth, skin, white-background or clothing
words.

Missing, stale or contradictory sign-off blocks before image generation after
the existing bounded Brain contract-recovery attempt. It must not fall back to
local prompt prose or Standard Mode.

## 8. Shared pixel review and bounded repair

Shared vision/hybrid review remains the only pixel-certification authority. For
an explicit age target or age transition, review must independently distinguish:

- same-person identity continuity;
- requested developmental-age coherence;
- cross-view age stability;
- gaze/expression age coherence;
- mouth/visible dentition plausibility when visible;
- skin material, complexion ownership and color cleanliness;
- neck/shoulder and visible-body age coherence;
- Professional neutral-capture compliance;
- ordinary technical cleanliness, including smearing, artificial grain,
  edge contamination and painterly residue.

These are review dimensions, not fixed facial measurements. No biometric age
estimate, landmark storage or numeric child-proportion formula is introduced.

An identity pass cannot compensate for an age-coherence failure. A pose pass
cannot compensate for adult styling. A generic visual-quality pass cannot
compensate for yellow/muddy skin, synthetic texture or inconsistent neutral
capture. Conversely, a lean or cool-expression child must not fail merely for
not matching a round, smiling stereotype.

When review returns a retryable observation, Doc160 transports bounded,
provider-neutral evidence to the Brain. The Brain authors one complete
replacement direction through the existing shared repair budget. No local
`make younger`, `add baby fat`, `whiten skin`, tooth, gaze, clothing or
background patch is allowed.

## 9. Provider and Local MCP strategy

The previous Doc165 formal M5 images were produced through the normal GPT Image
2 Provider path. Doc166 visual iteration may use the Local MCP relay for speed
only when all of the following are true:

1. the same frozen intent, target age, Professional binding, anchor view and
   quality contract are used;
2. the canonical final prompt is the exact Brain-signed prompt used by the
   normal Provider materializer;
3. admitted reference files, order, hashes and 2/3/5 serial budgets are
   identical;
4. MCP does not re-plan, append language, change references or invent a retry;
5. prompt/reference parity is recorded before generation;
6. every output remains truthfully marked according to the MCP contract.

Local MCP is appropriate for rapid side-by-side visual diagnosis and user
approval. It must not fabricate Product API candidate, review, winner, lineage
or pack-activation records. After the visual target is approved, the formal
Professional lifecycle must still demonstrate the same result through its
normal preparation host before a new pack is activated.

## 10. Development phases

### Phase 0 — Red regression and evidence lock

Add failing tests that prove:

- explicit target age and source-age non-inheritance reach final Brain sign-off;
- same-age continuation is unchanged;
- Professional preparation carries the neutral-capture objective;
- anchor view, age decision and neutral-capture decision cannot disappear at
  the finalizer boundary;
- no local prompt fragment, regex or child-specific branch supplies the result;
- Doc165 technical evidence is preserved while the clarified quality state is
  represented separately.

### Phase 1 — Semantic transport closure

Reuse the existing Human Realism, age-fidelity, reference-ownership and
Professional quality contracts. Close only missing typed transport and receipt
validation. Do not add a capability ID, public route, second planner or local
age classifier.

### Phase 2 — Brain instruction and complete sign-off

Teach the existing Remote Brain contract to reconcile whole-person
developmental age, source-age non-inheritance, expression ownership, applicable
commercial complexion and neutral anchor capture. The Brain must rewrite the
whole direction; no prompt suffix is permitted.

### Phase 3 — Shared review evidence

Extend the existing shared review schema only as needed to keep age coherence,
cross-view age stability, capture cleanliness and complexion/material findings
separate from identity and pose. Keep findings generic and provider-neutral.

### Phase 4 — Fast MCP visual iteration

Using one authorized source and one frozen People Asset preparation plan:

```text
front: 3 candidates -> visual comparison -> one provisional winner
three-quarter: root + provisional front -> 3 candidates
profile: root + front + three-quarter -> 3 candidates
```

MCP generation must use exact canonical prompt/reference parity. The user-
supplied child-model boards remain external human-evaluation benchmarks, not
renderer references.

### Phase 5 — Formal M5 confirmation

After user visual approval, perform a fresh append-only Product API preparation:

```text
front: 3 candidates -> shared Vision -> at most one existing repair -> winner
three-quarter: root + front winner -> 3 candidates -> shared Vision -> winner
profile: root + front + three-quarter winner -> 3 candidates -> shared Vision -> winner
explicit complete-pack activation
```

No partial view, MCP-only provisional winner or metadata-only review may be
silently promoted.

## 11. Regression matrix

Code and visual acceptance must cover at least:

1. same person, explicit approximately-ten-to-six transition;
2. new approximately-six-year-old person without an identity source;
3. same person, same age continuation;
4. approximately-ten-year-old and adult controls;
5. lively and neutral/cool expression controls at the same target age;
6. commercial high-key complexion with an explicit ownership decision;
7. low-key or documentary adult control proving no commercial complexion leak;
8. full Professional front/three-quarter/profile neutral-capture continuity;
9. ordinary General, E-Commerce and Photography isolation;
10. non-person and stylized-person controls proving Human Realism does not
    self-activate incorrectly;
11. exact normal Provider/Local MCP prompt and reference hash parity;
12. append-only review/repair/winner history and unchanged stage budgets.

The child-model boards may be used for side-by-side human judgement only. They
must not become test fixtures containing personal media or fixed prompt text.

## 12. Acceptance criteria

Doc166 is code-accepted only when:

- all typed age, ownership, Professional capture and view decisions survive to
  final Brain sign-off;
- the Brain remains the sole final prompt author;
- no local keyword, regex, proportion recipe, complexion palette or prompt
  suffix exists;
- shared review keeps identity, age, pose, skin/material and capture cleanliness
  as distinct evidence;
- adult, same-age, low-key, product-only and specialized-template regressions
  remain unchanged;
- complete V3, Professional, canonical parity and static checks pass.

Visual acceptance for the controlled approximately-six-year-old anchor requires:

- all three views read consistently as approximately six rather than drifting
  into older-child or young-adult presentation;
- recognizable identity continuity without retaining source-age maturity;
- convincing child facial volume and lower-face maturity as a whole, without
  forcing a round-face stereotype;
- age-coherent gaze, expression, visible mouth/teeth, neck and shoulders;
- clean white high-key capture with consistent simple age-appropriate clothing;
- bright, clean, naturally fair commercial complexion when explicitly owned,
  with restrained peach vitality and no yellow/grey/muddy cast;
- no oily sheen, waxiness, synthetic pores, fake grain, painterly smearing or
  over-retouched AI polish;
- unchanged identity, Human Realism, pose and visual-quality thresholds;
- one explicit user approval after side-by-side inspection.

## 13. Stop conditions

Stop and classify rather than adding words when:

- Brain sign-off is missing or contradictory;
- source-age ownership is unresolved;
- canonical Provider/MCP parity fails;
- no real pixels exist;
- identity fails independently of age;
- age fails independently of identity;
- neutral capture or complexion fails while identity passes;
- shared review is unavailable or metadata-only;
- the bounded repair budget is exhausted.

None of these conditions authorizes a threshold reduction, a child-specific
module, a local prompt patch or a hidden Standard Mode fallback.

## 14. Final development decision

The required enhancement is deliberately narrow:

```text
same V3 architecture
+ stronger shared whole-person developmental-age coherence
+ explicit Professional neutral identity-evidence capture
+ existing Brain-owned canonical prompt
+ existing shared review and bounded repair
```

The controlled child references guide human acceptance. They do not become
runtime rules. The solution succeeds only if it generalizes across ages,
expressions, scenes and templates while preserving exact prompt ownership and
reference-channel authority.
