# Doc167 — V3 Shared Developmental Facial Vitality and Soft-Tissue Coherence Spec

## Status

Architecture and visual-acceptance authority for the child-feel optimization
stage. This document refines Doc147/155 expression ownership and Doc166
developmental-age coherence. It does not create a child module, kidswear
recipe, template route, Provider path, facial measurement model or local prompt
patch.

## 1. Why Doc166 was not the final visual answer

Doc166 closed a real contract gap: when the current request assigns a new
developmental stage, the source portrait's apparent age is no longer an
automatic lock. The Remote Brain now signs a whole-person age decision and the
shared reviewer can reject obvious age drift.

The controlled results nevertheless expose a narrower gap. They are realistic,
clean and recognizably the same person, but a nominally six-year-old face can
still read as an older, camera-trained model. A generic statement such as
`ordinary childlike presence` can satisfy the current semantic receipt without
making the developmental stage materially observable in the face.

Against the three user-supplied real child-model boards, the current accepted
front/three-quarter/profile set shows:

1. thinner cheek and lower-face soft-tissue distribution than the benchmark;
2. a longer, more settled lower-face reading and less age-coherent facial
   fullness, despite correct overall proportions;
3. steady adult-like camera cooperation rather than child-stage attention;
4. a polite commercial mouth configuration that changes too little with the
   person's attention or moment;
5. correct skin realism but insufficient interaction between cheek volume,
   lower eyelid, mouth movement and expression;
6. neutral capture that becomes emotionally inert rather than simply neutral.

Baseline human comparison, with the supplied boards treated as a 9.0+ target:

| Dimension | Current result | Target |
| --- | ---: | ---: |
| Photographic realism | 9.2 | 9.0 |
| Developmental facial reading | 7.4 | 9.0 |
| Soft-tissue / lower-face coherence | 7.2 | 9.0 |
| Attention and affect authenticity | 6.8 | 9.0 |
| Mouth / teeth / expression coherence | 7.2 | 9.0 |
| Clean commercial capture | 9.2 | 9.0 |
| Overall child-stage vitality | 7.1 | 9.0 |

This is not a failure of photorealism. It is a failure to make the requested
developmental stage perceptually self-evident without relying on an age label.

## 2. Governing principle

The shared foundation must enforce one semantic invariant:

```text
When a visible person's developmental stage is owned by the current request,
the complete person must read at that stage through integrated facial presence,
not merely through scale, a stated age, or a younger-looking face outline.
```

The Remote Brain remains the only creative author. It decides how the person's
identity, developmental stage, soft-tissue response, attention, expression and
scene belong together in one natural-language image direction. Runtime code
freezes and transports the obligation; it does not decide a face type.

## 3. Shared, age-general scope

The refinement is called **developmental facial vitality**, not child realism.
It applies to any real visible person when developmental stage is relevant:

- a young child may require stage-coherent fullness, attention and mouth
  behavior without becoming a doll or a fixed round-face stereotype;
- a teenager must not be infantilized or given adult editorial presence;
- an adult must not inherit childlike facial behavior merely because an image
  is friendly;
- an older adult must retain stage-coherent facial material and presence
  without generic aging effects.

The word `vitality` does not require smiling, movement or extroversion. A quiet,
cool or neutral expression can have excellent developmental vitality when the
person's attention, facial resting state and soft-tissue response feel specific
and alive. Conversely, a broad smile can fail when it is an interchangeable
commercial mask.

## 4. Typed semantic contract

Fresh Human Realism execution advances to a small v8 contract with one new
semantic obligation:

```text
developmental_presence_requirement =
  integrated_stage_coherent_face_attention_and_affect
```

For hand/skin detail with no age-bearing face it is `not_applicable`.

This field is deliberately indivisible. It must not be expanded into local
cheek, eye, tooth, ratio or expression controls. The field tells the Brain that
the stage must be perceptually resolved as one person; it does not tell the
renderer how to build a face.

When the current request owns developmental stage, the existing Brain age
receipt advances to v2 and includes:

```text
developmental_presence = integrated_stage_coherent_face_attention_and_affect
```

The receipt proves that the Brain reconsidered and approved or rewrote the
complete prompt. It contains no age estimate, measurements, demographic
features, benchmark identity or renderer phrase.

Legacy v7/v1 records remain readable. They do not certify the fresh Doc167
obligation and cannot be silently upgraded.

## 5. Remote Brain final-signoff duty

When the obligation applies, the Brain must ask a perceptual question before
approving the canonical Provider prompt:

> If the explicit age words were removed, would this particular person's face,
> attention and expression still communicate the requested developmental
> stage in this exact scene?

If not, it rewrites the entire direction. The rewrite must remain natural,
person-specific prose. It must resolve the person's developmental presence in
the scene rather than append a quality phrase.

The Brain must preserve:

- identity-critical geometry and reference authority;
- user-owned expression, style, wardrobe, scene and complexion;
- the possibility of lean, round, quiet, serious, lively or smiling people;
- the difference between a neutral identity capture and a lifestyle moment.

The Brain must not satisfy the contract with generic labels alone, including
`childlike`, `youthful`, `cute`, `natural`, `lively`, `baby fat`, `big eyes` or
`age appropriate`. These may appear only when genuinely useful inside a
complete person-and-scene direction; they are never sufficient evidence by
themselves.

## 6. Shared pixel review

The existing Human Realism review remains the sole quality gate. It evaluates
the same indivisible semantic dimension as
`human_developmental_age_coherence`; no child-only reviewer is introduced.

For age-bearing faces, vision/hybrid review must determine whether the pixels
show an integrated stage-coherent facial presence. It considers the visible
relationship among facial soft tissue, resting or moving attention, mouth and
teeth behavior when visible, expression timing and the rest of the person.

It must not require:

- a round face, large eyes, visible teeth, a smile or a fixed amount of cheek
  fullness;
- a facial landmark threshold, age estimator or demographic classifier;
- resemblance to any supplied benchmark identity;
- liveliness in a deliberately neutral or cool-expression capture.

It must reject or withhold certification when the result is realistic but the
requested developmental stage is carried mainly by the prompt label while the
visible person reads as a different stage, or when attention/expression is an
interchangeable adult-trained commercial presentation.

Professional anchor review additionally exposes the score dimension
`developmental_facial_presence` and generic issue code
`professional_developmental_presence_drift`. These remain review evidence;
they never become Provider wording.

## 7. Retry

One existing bounded retry may use normalized
`human_developmental_age_coherence` evidence. The retry goes back through the
Remote Brain for a complete prompt rewrite. No local component may append
`make younger`, `add baby fat`, `make eyes innocent`, tooth instructions or an
expression substitute.

Selection compares original and retry evidence and keeps the best valid result;
the newest result is not automatically preferred.

## 8. Benchmark governance

The three supplied child-model boards are external human-evaluation benchmarks
only. They establish a quality bar for developmental reading, facial vitality,
clean commercial capture and expression diversity.

They must never be:

- sent to the Provider as reference images;
- converted into a facial template, ratio table, color palette or prompt
  recipe;
- used to copy identity, hair, wardrobe, expression or composition;
- committed to Git without a separate rights decision.

Controlled before/after tests use the same authorized project reference,
frozen user intent and canonical materialization path. Only the implementation
version may change.

## 9. Iterative visual acceptance protocol

Each iteration performs:

```text
benchmark comparison
-> defect attribution
-> document/contract adjustment
-> focused and full regression
-> canonical Local MCP plan
-> one Codex ImageGen call per frozen output
-> shared Vision review
-> external benchmark scoring
```

At least two materially different tests are required:

1. neutral or cool-expression front capture, proving developmental morphology
   and attention without relying on a smile;
2. ordinary commercial/lifestyle moment with a user-authorized warm or lively
   affect, proving that vitality does not collapse into a stock grin.

At least one adult control and one no-person control must prove that no child
appearance leaks into unrelated jobs.

## 10. Acceptance threshold

The specialization may stop only when:

- shared Vision returns verified pass for the controlled outputs;
- identity and explicit age ownership remain intact;
- external human scoring is at least 8.8/10 overall child-stage vitality;
- developmental facial reading, soft-tissue coherence, attention/affect and
  mouth/expression coherence are each at least 8.5/10;
- neutral capture is alive but not performative;
- lively capture is specific to the moment and not a standardized presenter
  smile;
- clean background, complexion and skin material remain at the already
  accepted commercial standard;
- exact canonical prompt/reference parity is preserved between Web Provider
  and Local MCP planning;
- full V3 regression and isolation tests pass.

An attractive, realistic output below these developmental-presence thresholds
is not accepted merely because the Vision provider reports general Human
Realism pass. The controlled benchmark comparison is the final human quality
check for this stage.

## 11. Prohibitions

This work must not add:

- a child, kidswear or age-band module;
- regex/keyword classification as the creative decision;
- face ratios, age estimators, landmark thresholds or biometric persistence;
- local renderer prompt fragments, negative-word stacks or retry sentences;
- a catalogue of child expressions, smiles, eye shapes, teeth or face types;
- a second Brain, Provider, review, retry, storage or MCP interpretation path;
- General, E-Commerce, Photography or Professional template leakage.

## 12. Relationship to earlier documents

- Doc147/155 remain authoritative for expression ownership and the rejection
  of stock commercial smile geometry.
- Doc159 remains authoritative for commercial complexion and skin material.
- Doc160 remains authoritative for review-evidence-to-Brain complete rewrites.
- Doc166 remains authoritative for developmental-age ownership, source-age
  non-inheritance and neutral Professional capture. Its provisional visual
  acceptance does not certify the stronger Doc167 developmental-facial-
  vitality threshold.

Doc167 changes no foundation architecture. It strengthens one shared Human
Realism semantic obligation, its Brain sign-off receipt and its existing shared
review evidence.
