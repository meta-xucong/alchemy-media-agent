# Doc143 — V3 Shared Human Authenticity and Photographic-Skin Review

Status: **active shared-foundation refinement authority.** This document
extends Docs 128 and 136–142 after their controlled M4 pixel matrix. It does
not replace the V3 execution architecture or authorize a template, Provider,
or demographic-specific visual route.

## 1. Evidence and precise problem statement

The Doc142 controlled matrix proved that the shared route is live:

```text
frozen Human Realism activation
-> Remote Brain finalization and independent re-signing
-> exact Provider materialization
-> shared hybrid pixel review
-> bounded retry and final delivery
```

It also exposed a qualitative gap that a mere `hybrid / pass / verified`
verdict did not catch consistently:

1. A young person can retain an interchangeable lower-face/smile archetype
   despite being age-appropriate and anatomically plausible.
2. An adult can retain an over-smoothed, painterly or beauty-filter-like skin
   surface despite otherwise credible features and lighting.

These are **not** evidence for a child/kidswear module, a face prompt library,
or a renderer-side patch. They are two general failures of photographed-person
credibility. Young-person requests expose the first failure more readily, but
the rule must hold for every real visible person.

## 2. Root cause

The existing Human Realism semantic contract already asks the Brain for
`individual_human_presence`, and the existing reviewer already receives broad
issue labels such as `human_rendering_artifact` and `human_skin_or_retouch`.
That is necessary but incomplete.

The current enforced review projection does not carry the frozen semantic
meaning of individual personhood and photographic skin material to the vision
reviewer. The reviewer can therefore find obvious distortion while accepting a
technically coherent but archetypal face or painterly surface.

The correction is to make that frozen meaning an explicit review obligation,
not to enlarge the renderer prompt or locally score facial parts.

## 3. Non-negotiable boundaries

```text
Foundation work only.
General remains scenario-neutral.
E-Commerce and Photography retain their own delivery contracts.
Remote Brain remains the sole author of every renderer-facing whole prompt.
Vision/hybrid review remains the sole authority for rendered-pixel verdicts.
```

Prohibited in every new enforced path:

- child, teen, apparel, ethnicity, platform, or template-specific capability;
- keyword/regex selection of expression, skin, face geometry, camera or pose;
- local positive/negative prompt additions, retry prose, image retouching or
  facial scoring;
- a second Provider, review/retry loop, storage system or delivery path;
- numerical beauty, pore, symmetry, age, or skin thresholds;
- exposing reviewer reasoning, hidden checklists or internal issue prose to the
  renderer or normal user surface.

Docs 91 and 92 retain historical observations and compatibility aliases only.
Their legacy child and skin wording is not executable authority for a new
enforced job. Doc143 is the forward refinement authority.

## 4. Minimal frozen semantic extension

Fresh enforced Human Realism contracts move from semantic v2 to semantic v3.
The existing fields remain, and exactly two generic perceptual obligations are
added:

```text
personhood_requirement:
  individual_noninterchangeable_presence

photographic_material_requirement:
  camera_observed_human_materiality
```

They are typed goals, not strings copied into a Provider prompt.

`individual_noninterchangeable_presence` means the Brain must decide whether
the complete direction can plausibly produce one particular person present in
the stated situation, rather than an interchangeable polished face, stock
smile, or generic beauty archetype. It does not prescribe a smile, facial
feature, ethnicity, pose, camera angle, or age-specific look.

`camera_observed_human_materiality` means the Brain and reviewer must preserve
the requested photographic mood while requiring skin, facial planes and light
response to read as material recorded by a camera rather than a painted,
uniformly retouched, waxy or beauty-filter surface. It does not prescribe
pores, wrinkles, colour, exposure, or a beauty standard.

The runtime validates version, cardinality, owner, frozen bindings and this
closed enum shape. It never interprets the enums into natural-language
renderer fragments.

## 5. Brain re-signing rule

The existing Doc139/142 independent Human Realism re-signer remains the only
extra Brain pass. No third call is introduced.

For an active v3 contract it silently asks whether the candidate prompt gives
the renderer enough complete, situation-owned direction to avoid replacing the
person with an interchangeable archetype or a non-photographic beauty surface.
It preserves user facts, reference truth, requested mood, legitimate editorial
style and template contract. It returns the complete rewritten-or-approved
prompt plus the existing audit-only receipt:

```text
human_naturalness_decision:
  contract_version: v3_human_naturalness_decision_v1
  status: approved | rewritten
  owner: remote_v3_llm_brain
```

This receipt still does not contain rationale, scores, renderer wording or a
new check-list field. A missing receipt blocks before Provider materialization.

## 6. Pixel-review attestation

For an active v3 Human Realism contract, the frozen review projection includes
the two semantic obligations and requires one small reviewer attestation:

```text
human_naturalness_verdict:
  status: pass | retry_recommended | not_verifiable
  issue_codes: subset of the already-frozen generic Human Realism issue codes
```

The vision model sees the generated pixels and the frozen review contract. It
must answer this explicitly, but its reasoning remains private. The attestation
does not carry a per-feature score or detailed face-analysis taxonomy.

Rules:

```text
missing or malformed attestation -> manual confirmation required
not_verifiable                 -> manual confirmation required
retry_recommended + generic issue evidence
                              -> existing one bounded shared retry
pass + no conflicting generic Human Realism issue
                              -> ordinary shared delivery policy
```

The only retry payload remains normalized review evidence. The finalizer and
re-signer return a new complete Brain prompt; no code turns a reviewer verdict
into face/skin wording.

## 7. Compatibility and isolation

Historical v2 contracts and detailed legacy issue aliases remain readable for
old records. They cannot be upgraded, re-certified, or used to generate a new
v3 final prompt. New v3 jobs never emit child-specific review codes; any old
alias is normalized to the existing broad Human Realism dimensions at the
explicit compatibility boundary.

General, E-Commerce and Photography all use the same shared contract. A
product reference may establish product truth, but it never changes this into
a garment- or child-specific visual capability. An uploaded portrait retains
the reference rights defined by Doc93; Doc143 does not expand those rights.

## 8. Required red regressions

1. New enforced real-person jobs freeze semantic v3 with exactly the two
   generic obligations; no child, garment, camera, or prompt field appears.
2. Product-only and stylized whole-image jobs do not require the new
   attestation.
3. The finalizer and re-signer receive v3 semantics, but materialization still
   receives only the exact Brain-signed complete prompt.
4. The enforced vision request receives the frozen obligations and a required
   attestation shape; it does not receive the legacy issue catalogue.
5. Missing, malformed, inconsistent or not-verifiable attestations withhold
   certification/delivery rather than silently passing.
6. A retry-recommended attestation uses only existing generic Human Realism
   evidence and reaches the Brain whole-prompt revision path with no local
   patch text.
7. Adult ordinary, young person with a product reference, person/object
   interaction and low-key real-person cases use the same contract and stay
   template-isolated.
8. Legacy child issue names and old prompt fragments remain archive-only and
   cannot reach a fresh enforced Provider call.

## 9. Acceptance sequence

> **Doc147 compatibility note (fresh jobs):** this document's v3 frozen
> personhood/material contract is retained for historical read compatibility.
> New enforced work uses Doc147's v4 contract, adding only the shared
> expression-ownership attestation; it does not reintroduce its historical
> narrow issue names.

1. Add the red contract and reviewer tests.
2. Implement v3 semantic projection, review attestation and fail-closed
   compatibility boundary.
3. Run focused Human Realism, review/retry, Provider, General/E-Commerce/
   Photography isolation and full V3 suites.
4. In a controlled real-pixel environment, compare the same blue-dress
   young-person reference with ordinary adult, person/object and low-key
   samples. Record only safe provenance, review state and qualitative outcome.
5. Accept only if the young-person result no longer defaults to the same
   formulaic smile/lower-face archetype and adult skin no longer shows the
   repeated painterly/over-smoothed failure, without degrading age fidelity,
   reference truth, lighting mood, hands, or product construction.

This document does not promise that a generative model will never create an
imperfect face. It raises the shared semantic and pixel-review bar, supplies a
bounded corrective path when that bar is not met, and preserves a clear audit
trail when a result must be withheld.

## 10. Initial controlled acceptance record

The Doc143 implementation passed its full offline contract suite. A traced
remote-Brain adult plan subsequently reached planning, canonical finalization
and the existing Human Realism re-signing with a valid v3 contract. This proves
the v3 obligation is compatible with the real Brain boundary; it is not a
test-double-only contract.

The same authorized blue-dress reference then produced one frozen,
Brain-signed Local MCP image-edit plan. Its one permitted conversation-only
Codex ImageGen call was rejected at **output moderation** before any pixels
were returned. That record is non-counting for visual quality. The prompt,
reference input, model path and semantics were not altered to evade the
decision, and no candidate or delivery was created.

The next qualifying pixel comparison remains the unchanged blue-dress plan
when the renderer accepts it, plus the ordinary-adult materiality comparison.
Neither may be replaced with a child-specific or prompt-keyword workaround.
