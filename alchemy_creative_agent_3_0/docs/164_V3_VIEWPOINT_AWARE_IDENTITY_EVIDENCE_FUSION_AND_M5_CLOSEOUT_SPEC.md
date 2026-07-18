# Doc164 — V3 Viewpoint-aware Identity Evidence Fusion and M5 Closeout

Status: implementation complete; formal serial Professional M5 rerun required.

## 1. Reproducible finding

The second bounded Doc162 Professional front run used the face-localized Doc163
identity derivatives and reached the real shared Vision gate. Prompt/reference
parity, Remote Brain ownership, high-fidelity image edit, Human Realism and the
Professional review contract were all active.

The remaining rejection was not caused by a missing prompt rule. The authorized
root portrait is a downward-looking three-quarter view, while the required first
anchor is straight-on. For a visually credible candidate, the evidence was:

- objective SFace score: `0.8650`;
- multimodal same-person score: `0.8600`;
- human realism: `0.9100`;
- visual quality: `0.9300`;
- two-dimensional landmark geometry score: `0.5688`.

The legacy fusion treated the last value as if source and output were captured at
the same viewpoint. It therefore pulled the fused identity score below `0.82` even
though the pose change was the requested operation and the two pose-robust identity
signals agreed. A second candidate showed the same pattern. This is a review-
evidence calibration defect, not a reason to relax the commercial identity gate.

One of the three independent materializations also ended in a Provider policy
failure with no pixels. That remains append-only upstream evidence. It is not
reclassified as an identity-quality failure and does not authorize replaying the
same operation.

The first rerun after the cross-view correction produced a verified passing front
winner (`same-person 0.8806`, `human realism 0.90`, `visual quality 0.93`). It then
exposed a separate supplementary-reference transport defect: the reviewed front
winner was canonical in Product API metadata, but Scenario Runtime reconstructed it
as a generic upload and stripped the top-level `output_id` / `source_type` before
Provider admission. All three three-quarter operations correctly failed closed with
zero pixels. The correction freezes the server-resolved root plus prior-winner list
as typed `reference_assets`; it does not change prompts, reference counts or review.

The following run admitted the reviewed winner and produced real three-quarter
pixels, but exposed one final parity projection defect: the frozen activation plan
contained the serial reference strategy and stage while per-output generation
metadata did not. Provider therefore used the ordinary two-derivative policy for
both sources (four references) instead of the frozen three-reference stage policy.
The runtime now projects only the validated strategy/stage from the immutable plan
into each generation plan. A parity mismatch is recorded as a bounded candidate
failure rather than escaping as a validation exception.

The next bounded run showed that enriching the returned generation plan is too
late for the real Provider path: `run_generation_loop` has already materialized
the request at that point. The same frozen selector projection is therefore now
applied to planning metadata and, critically, generation metadata before the
generation loop begins. Post-run enrichment reuses the identical helper so the
execution receipt and returned plan cannot disagree.

Live receipt inspection then found one further narrowing: CentralCreativeBrain
constructs each output plan through an explicit metadata allow-list. The runtime
metadata was correct, but the serial strategy/stage were absent from that list,
so the Provider still received the ordinary reference policy. The fields are now
preserved at this per-output boundary, with a direct CentralCreativeBrain test;
their values still originate only from the frozen-plan projection above.

Once the 2/3 reference budgets were correct, real three-quarter pixels exposed
a review-authority ambiguity rather than a renderer failure. The root garden,
blue wardrobe and warm location light were not inherited, but shared Vision
treated continuity with the already-reviewed neutral front anchor as if every
reference were an identity-only upload. Serial anchor review now distinguishes
the immutable root (`identity_only`) from prior reviewed winners
(`identity_plus_neutral_anchor_capture_continuity`). This is review-only typed
authority derived from the frozen strategy/stage. It does not add renderer
language, suppress issue codes locally, relax identity/Human Realism thresholds,
or change ordinary portrait review.

## 2. Authority and scope

This document extends Docs 93, 95, 96, 161, 162 and 163. It is shared foundation
work and is independent of template, subject age, ethnicity, wardrobe and scene.

The correction must not:

- add a child, kidswear, Professional-only or scene-named identity algorithm;
- parse prompts with keywords or regex to guess viewpoint;
- add identity prompt prose, negative lists or deterministic repair text;
- lower the `0.82` same-person commercial gate;
- bypass shared Vision or convert a failed Human Realism verdict into a pass;
- create another Provider, reviewer, retry loop or persistence model.

## 3. Runtime contract

### 3.1 Ephemeral viewpoint evidence

The existing local identity metric already detects one face for ephemeral SFace and
landmark evaluation. It may derive two coarse labels from those same landmarks:

- selected reference viewpoint;
- generated output viewpoint.

Only `front`, `left/right_three_quarter`, `left/right_profile` and their relationship
(`same_view`, `cross_view`, `unknown`) are retained in the per-review receipt. No
landmarks, vectors or new biometric persistence are allowed.

### 3.2 Same-view evidence remains strict

When the selected reference and output are the same coarse view, the established
Doc96 weights are unchanged. Two-dimensional facial geometry remains a direct
identity signal and can block delivery.

### 3.3 Cross-view geometry becomes advisory

When the detector establishes a cross-view comparison, two-dimensional geometry is
pose-sensitive evidence. Perspective legitimately changes apparent eye spacing,
nose offset, mouth width and jaw projection. The fusion therefore retains geometry
at a small corroborating weight and reallocates the remaining weight to SFace and
multimodal same-person evidence.

The threshold remains exactly `0.82`. A candidate still fails when the pose-robust
signals do not agree, or when Human Realism, age direction, pose compliance,
distinctive features, prompt-owned channels or visual quality fail independently.

`unknown` viewpoint keeps the legacy conservative weights; it never receives the
cross-view treatment.

## 4. Separation from creative direction

Remote Brain continues to author and sign the complete canonical Provider prompt.
This change never adds a word to that prompt and never interprets user prose. It
changes only how already-observed pixel evidence is fused after generation.

Doc163 face-localized reference admission remains mandatory for the formal
Professional anchor run. Doc164 does not restore full-frame wardrobe, hair,
background or lighting inheritance.

## 5. Acceptance

Code acceptance requires:

1. the internal metric emits coarse reference/output view evidence without vectors
   or landmarks;
2. same-view weights and the `0.82` threshold are unchanged;
3. confirmed cross-view geometry is advisory and the applied weights are auditable;
4. unknown view remains conservative;
5. identity drift still fails when SFace and multimodal evidence are weak;
6. no prompt, template or Provider routing behavior changes;
7. a reviewed prior winner retains its canonical output binding across Product API,
   Scenario Runtime and Provider materialization;
8. Doc96/Professional/Doc163 focused tests and the complete V3 suite pass.

Pixel acceptance remains the existing bounded sequence:

```text
front: 3 candidates -> shared Vision -> one winner
three-quarter: root + front winner -> 3 candidates -> one winner
profile: root + front + three-quarter winners -> 3 candidates -> one winner
```

Candidate 1 may use the one existing shared bounded repair for its stage. Provider
failures, rejected candidates and repairs remain append-only. A complete reviewed
pack must be explicitly activated; no partial pack can pass M5.

## 6. Stop conditions

If the next formal run still fails, diagnose the recorded evidence category before
changing code:

- identity mismatch: inspect pose-robust identity evidence and reference admission;
- Human Realism or AI polish: improve shared generation semantics, never the score;
- pose failure: inspect the Brain-authored direction and Provider result;
- no pixels: classify as Provider/upstream evidence, not visual quality;
- incomplete serial references: fix lineage transport, not prompt wording.

No failure authorizes threshold reduction or local prompt stacking.
