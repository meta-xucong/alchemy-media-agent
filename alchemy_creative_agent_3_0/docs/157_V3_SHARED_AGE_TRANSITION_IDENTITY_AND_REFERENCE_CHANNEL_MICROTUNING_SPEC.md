# Doc157 — V3 Shared Age-Transition Identity and Reference-Channel Micro-Tuning

Status: implemented in the mainline age-transition micro-tuning milestone; visual acceptance remains separate

## 1. Purpose

This document defines a small, shared-foundation refinement for the case where a
user asks for the same person to be visually re-expressed at a different age,
for example: “keep this approximately ten-year-old person's face, but create a
six-year-old version.”

The purpose is to improve age consistency without creating a child module,
adding a new capability family, changing the V3 framework, or returning to
keyword-heavy prompt construction.

The intended result is:

```text
preserve identity continuity
+ change the requested apparent age
+ keep current-prompt ownership for scene, wardrobe, light, camera, and mood
```

This is an age transition, not a simple resize of the source face and not a
request to generate an unrelated generic child.

## 2. Authority and compatibility

Doc157 is subordinate to and extends the following authorities:

```text
Doc93  reference-channel ownership and prompt ownership
Doc94  universal foundation de-overfitting and Brain final-prompt ownership
Doc95  complementary portrait identity evidence and best-result selection
Doc96  high-fidelity identity evaluation and bounded repair governance
Doc155 shared expression resolution and age adaptation
Doc156 controlled approximately-six-year comparison evidence
```

No wording in Doc157 permits a shared runtime to inherit a source person's
whole-image style, apparent age, body proportions, or wardrobe when the current
user instruction assigns those channels elsewhere. Doc93 remains authoritative
for reference ownership. Doc155 remains authoritative for expression resolution
and the v6 Human Realism contract.

Historical documents that describe “same person” as automatic inheritance of
the source person's age, body, hair, wardrobe, lighting, or complete frame are
historical only and must not override Doc93 or this document.

## 3. Scope and non-goals

This is a micro-tuning change inside the existing:

```text
remote V3 Brain intent resolution
shared Human Realism capability
existing reference-channel admission
existing provider/review/retry/final-delivery lifecycle
```

It does not add or change:

- a child, kidswear, or age-specific module;
- a new capability ID, provider, router, reviewer, retry loop, or MCP tool;
- a new public job state or second reference state machine;
- a local age classifier, regex creative decision, prompt atom catalogue, or
  fixed facial/body proportion recipe;
- biometric-vector persistence or an exact-age recognition service;
- General, E-Commerce, Photography, Project Mode, or template deliverables.

The existing `identity_age_fidelity`, `preserve_person_identity`, reference
channel policy, canonical prompt signing, shared review, bounded retry, and
MCP/provider prompt-parity contracts remain the only mechanisms used.

## 4. Semantic rule for an age transition

When the user explicitly requests an age change for the same person, the Brain
must resolve the reference channels before authoring the final creative
direction.

### 4.1 Identity continuity that remains inherited

The following identity-critical relationships may remain stable:

```text
overall facial-feature relationship
eye and brow relationship
nose-to-mouth relationship
face-outline direction and cheek transition
recognizable facial character
```

These are continuity cues, not a request to copy the source person's exact
age, body, expression, lighting, or styling.

### 4.2 Age and developmental appearance that must be re-expressed

When the requested age differs from the source person's apparent age, the
source apparent age is not automatically inherited. The Brain must reinterpret
the complete person for the requested age, including the overall impression of
facial maturity, body proportion, height, shoulder and limb relationship,
expression, and styling coherence.

The implementation must not translate this into a list such as “larger eyes,
rounder cheeks, shorter limbs.” Those may be considered internally by the
Brain, but only the Brain may decide how to express the complete image direction
in natural language.

### 4.3 Current-prompt ownership

The current explicit request remains authoritative for:

```text
age transition
scene
wardrobe or product truth
hair styling unless identity-locked by the user
lighting
camera and composition
mood and expression
```

If the user instead asks to continue the same person without changing age,
the source age remains part of identity continuity. The age-transition rule
must not silently apply to ordinary same-person continuation.

## 5. Mixed reference handling

An uploaded image may contain both a garment and a person. The existing
reference-channel policy must distinguish those contributions semantically:

```text
garment truth may be inherited
scene truth may be inherited only when assigned by the user
source-person age and body are not inherited when the user requests an age change
identity geometry is inherited only to the degree required by same-person continuity
```

If the reference is too mixed or too weak to separate these channels safely,
the run must not claim strict age fidelity. It may continue as a clearly
non-strict creative result or become `manual_review`/blocked according to the
existing lifecycle. It must not silently preserve the older source body and
call the result a six-year-old success.

No new content-altering crop pipeline is introduced by this document. Existing
technical reference normalization remains allowed when it preserves evidence
and provider admissibility; it must not be used to bypass provider policy or to
invent a new creative reference state.

## 6. Brain and Human Realism implementation handoff

### 6.1 Brain change

Extend the existing Brain semantic instructions so that an explicit age
transition is resolved as:

```text
same-person identity continuity
with requested-age re-expression
and source-age non-inheritance
```

The Brain must author the final complete provider prompt after this reasoning.
The runtime may validate the existing semantic contract and reference
ownership, but it may not append age wording, choose facial proportions, or
rewrite the Brain prompt locally.

### 6.2 Human Realism change

Refine the existing Human Realism guidance under `identity_age_fidelity` so
that it distinguishes:

```text
same person, same age
same person, explicitly changed age
new person with an explicit target age
```

Only the second case enables age-transition interpretation. All cases continue
to use the same shared Human Realism v6 contract and the same expression-
resolution requirement from Doc155.

### 6.3 Review and retry

The existing shared visual review remains the authority for whether the
materialized result is visibly inconsistent with the requested age. If age
fidelity is not available from the active review mode, the result is
`manual_review`/unverified rather than falsely certified.

When an existing review result identifies a retryable identity or age-fidelity
problem, the current bounded retry path asks the Brain to rethink the complete
direction. It must not add a local “make younger” fragment, select from a
fixed child-face catalogue, or create a Human Realism-private retry path.

## 7. Provider and MCP parity

The canonical provider prompt must be identical between the normal V3 provider
path and the Codex-native MCP relay for the same frozen intent, reference
channels, and output ordinal.

The MCP relay may only relay a frozen plan. It must not re-plan age, reinterpret
identity, or add age-related wording. A hash or provenance mismatch blocks the
relay rather than producing a visually different test path.

MCP-generated conversation-only images may provide diagnostic visual evidence,
but they do not by themselves certify Web Provider review, retry, or production
delivery.

## 8. Required regression coverage

The implementation must add focused tests before visual acceptance:

1. An adult same-person continuation preserves the existing age and identity
   semantics.
2. An approximately ten-year-old person explicitly re-expressed at
   approximately six years preserves identity relationships while allowing
   age-related appearance to change.
3. A same-person request without an age change does not activate the transition
   interpretation.
4. A new person with an explicit age uses the same shared contract without a
   child-specific branch.
5. A mixed person-and-garment reference does not leak the source person's age
   into an explicit age transition when the user assigns the garment as truth.
6. An ambiguous mixed reference cannot be marked as strict age-certified
   without the existing appropriate review evidence.
7. The final prompt is Brain-authored and no local code appends age, face, or
   body-proportion instructions.
8. MCP and normal provider canonical prompt/reference hashes remain identical.
9. General, E-Commerce, Photography, and adult identity regressions remain
   isolated.

The visual matrix should use at least three materially different scenes and
compare approximately six-year, approximately ten-year, and adult controls
where the source evidence permits. A pure garment reference should be used for
the strict six-year comparison; the mixed reference case should be recorded as
an explicit stress test rather than silently treated as equivalent evidence.

## 9. Acceptance criteria

The micro-tuning is acceptable only when all of the following hold:

- no new module, route, provider, or state machine is introduced;
- the same Human Realism v6 contract is used across ages;
- Brain provenance shows the final direction was authored and signed by the
  remote V3 Brain;
- source-age leakage is reduced in the explicit ten-to-six transition case;
- identity continuity remains recognizable without copying the older body or
  mature facial impression;
- same-age continuation and adult outputs do not regress;
- ambiguous references are not falsely certified;
- no fixed child-face prompt recipe, regex creative branch, or local prompt
  append is present;
- provider and MCP parity remains exact;
- the visual result is accepted only through the existing shared review and
  delivery rules.

## 10. Final architectural decision

Doc157 is a controlled refinement of the existing foundation. It does not
change the V3 architecture:

```text
reference ownership and user intent
→ remote Brain semantic resolution
→ shared Human Realism
→ Brain-authored canonical provider prompt
→ shared generation/review/bounded retry/final delivery
```

The central protection against overfitting is that age transition is a semantic
ownership decision, not a new collection of age-related prompt words.

## 11. Mainline implementation record

The implementation keeps the existing Human Realism v6 contract and makes
three narrow changes inside the existing foundation path:

1. The enforced Human Realism executor preserves the existing typed
   `age_fidelity` admission value instead of dropping it before canonical Brain
   sign-off. This is evidence propagation only; it does not decide an age
   transition locally.
2. The canonical Brain sign-off context carries the existing age-fidelity and
   reference-age ownership boundary. The remote Brain remains responsible for
   distinguishing same-age continuation from explicit same-person age change
   and for authoring the complete renderer prompt.
3. The legacy reference-truth materializer no longer states that source age
   and body direction are always locked when the resolved age policy assigns
   the age to the current prompt. Brain-signed enforced prompts still bypass
   this compatibility materializer as before.

Focused Doc157/reference/age regressions pass, and the complete V3 suite passes
with the existing two FastAPI deprecation warnings. No child, kidswear,
template, provider, review, retry, MCP, or public-state module was added.
