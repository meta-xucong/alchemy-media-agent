# Doc253 — V3 Face Standard-Front Framing Contract Diagnosis

## Purpose

The Doc248 comparison exposed visible framing drift across three otherwise
accepted `standard_front` candidates. This is not a Doc252 micro-realism module
responsibility. It is a pre-existing Face Identity / Character Card framing
contract issue.

This document records the owning layer and the minimum diagnosis model. It is a
separate task from micro real-human fidelity.

## Ownership

Formal Face framing belongs to the existing Face Identity / Character Card
view-role system:

- `standard_front` and other face view roles;
- `v3_character_card_face_framing_standard_v1`;
- `face_view_framing_parity`;
- `character_card_framing_truth`;
- shared Vision framing projection for face-card candidates.

The numeric envelope discussed here applies only to the formal Face
`standard_front` `formal_slot`. It must not change:

- historical/context-only Face records;
- target-only existing-output collection;
- `left_front_25` / `right_front_25` auxiliary reference bridges;
- Expression Set framing;
- Body Silhouette framing;
- public compatibility display of non-formal historical material.

It does not belong to:

- Doc248 absolute portrait realism;
- Doc252 micro real-human fidelity;
- FormalSlotAcceptanceCore;
- receipt/activation authority;
- Provider/MCP transport selection.

The current code already points to this owner:

- `ProfessionalModeRuntimeBridge._face_identity_framing_contract()` defines
  `v3_character_card_face_framing_standard_v1`;
- the Face evidence capture contract defines `face_view_framing_parity`;
- Provider materialization carries `character_card_framing_truth` and
  `card_framing` evidence scope;
- Product API service already treats `standard_front` as a Face view-role
  stage.

Therefore the fix should tighten this existing owner. It should not be moved
to the micro-realism module merely because the drift was discovered during a
realism comparison.

## Current evidence

The three Doc248 comparison candidates were all accepted by the existing
generic/shared review path, but their face boxes varied:

| Candidate | Face width | Face height | Center X | Center Y |
| --- | ---: | ---: | ---: | ---: |
| candidate1 | 0.476207 | 0.332980 | 0.531081 | 0.539832 |
| candidate2 | 0.446465 | 0.304249 | 0.535615 | 0.512449 |
| candidate3 | 0.452909 | 0.321446 | about 0.560 | about 0.516 |

The width spread is roughly 6.7%, and the height spread is roughly 9.4%. That
is visible enough for a formal model-card set.

## Initial root-cause model

### Request and planning layer

Existing contracts say the front card should be a head-and-upper-shoulders
reference crop. This is a correct semantic requirement, but it is not a
measurable envelope.

Likely missing or weak fields:

- target face-box size band;
- target face center band;
- eye-line band;
- head-top margin band;
- shoulder/collar visibility band;
- allowed variance across three candidates in one formal round.

### Reference channel ownership

The Provider materializer already has a `character_card_framing_truth` channel
and prioritizes a full-frame/card-framing reference when available. That
indicates the right owning layer exists.

The gap is not that framing ownership is missing entirely. The gap is that the
ownership is still expressed mostly as prompt/reference semantics rather than
as a strict numeric candidate evidence contract.

### Provider/MCP rendering contract

The transport contract fixes output canvas and transport quality, for example
`1024x1536` and high-quality image-edit behavior. It does not, and should not,
own subject crop. A 1024x1536 image can still have a face that is too large,
too small, too high, or too low.

### Vision/review projection

The review path can observe face-box data, pose, composition, and framing
signals, but the current pass/fail standard does not appear to require a tight
front-card numeric envelope or candidate-set variance limit.

This is the most likely owning seam for the red test: a candidate can pass
generic composition while still failing strict Face standard-front framing.

### Formal Core

Formal Core correctly does not understand face crop. It should receive only
candidate eligibility after the Face framing profile has decided whether each
candidate is eligible.

## Diagnosis conclusion

The likely defect is:

```text
Face standard-front framing is owned by the right old module, but its evidence
contract is too semantic and not strict enough at the shared Vision projection
/ Face view-role profile boundary.
```

This should be fixed in the Face Identity / Character Card framing profile and
shared Vision framing projection, not in the micro-realism Enhanced module.

## Minimum future repair model

Introduce a Face-owned `standard_front_framing_envelope_v1` proof in the
existing Face view-role framing profile.

Candidate-level dimensions may include:

- face_box_width_ratio;
- face_box_height_ratio;
- face_center_x;
- face_center_y;
- eye_line_y;
- head_top_margin;
- shoulder_visibility_ratio;
- collar/upper-shoulder visibility;
- background left/right balance;
- candidate-set face-box variance.

Initial thresholds must be calibrated from accepted model-card references, not
copied from Doc252. The current Doc248 three-candidate set should be used as a
red fixture showing that generic composition pass is not enough to guarantee
formal front-card framing parity.

Thresholds must not be hard-coded without a calibration artifact. A future
implementation must introduce a versioned calibration source, for example:

```text
standard_front_framing_envelope_calibration_v1
```

The artifact should record:

- source fixture set;
- measurement method;
- accepted face-box/eye-line/head-margin bands;
- round-level variance limits;
- review date/version;
- rationale for formal `standard_front` only.

Until that artifact exists, Doc253 remains a diagnosis and red-test model, not
an implementation instruction to bake numbers into production code.

### Where to carry the proof

The proof should be candidate-level Enhanced evidence, not Core data:

```text
candidate
  -> shared Vision observes face/framing dimensions
  -> Face view-role framing profile validates the numeric envelope
  -> candidate Enhanced eligibility records framing pass/fail
  -> Formal Core sees only eligible/ineligible candidates
```

Round-level variance is still owned by the Face framing adapter/profile. The
adapter may aggregate the three candidate face-box measurements and mark one or
more candidates ineligible, or mark the formal round invalid, before Formal Core
ranking. Formal Core must not receive or interpret geometry.

### Where not to carry the proof

- not in Doc252 micro-realism proof;
- not in FormalSlotReceipt as a new Core semantic;
- not as Provider transport fingerprint;
- not as MCP recovery metadata;
- not as prompt text alone.
- not in Expression/Body profile proof;
- not in historical/context-only or 25-degree auxiliary bridge activation.

## Candidate-set consistency

There are two related but separate checks:

1. Per-candidate envelope: each candidate must individually match the formal
   `standard_front` crop.
2. Round-level consistency: all three candidates in the same formal round must
   stay within an allowed face-box spread.

The second check explains why all three current candidates could individually
look acceptable but still feel inconsistent as a set.

## Diagnostic checklist before code

Before changing implementation, inspect these layers in order:

1. Request/planning metadata: is a numeric front-card envelope present?
2. Brain decision/signoff: does it preserve the envelope or only semantic
   wording?
3. Provider materializer: does it receive `character_card_framing_truth`
   reference in the expected order?
4. MCP/Provider transport: does it correctly fix canvas only, without being
   mistaken for crop authority?
5. Vision projection: does it emit face-box/framing dimensions in a canonical
   shape?
6. Face view-role profile: does it enforce per-candidate and round-level
   envelope checks?
7. Formal Core input: are failed framing candidates excluded before ranking?

## Red-test model

Add tests in the Face/Character Card framing owner:

1. `standard_front` candidate with generic Vision pass but missing numeric
   framing envelope fails framing eligibility.
2. Three candidates individually pass coarse composition but exceed face-box
   variance limit; strict front-card set fails.
3. Valid envelope proof passes without requiring Doc252 micro-realism proof.
4. Doc252 micro-realism pass cannot compensate for framing envelope failure.
5. Provider/MCP transport `1024x1536` alone cannot satisfy the framing proof.
6. Formal Core remains unaware of all framing dimensions.

Additional regression requirements:

7. Doc252 micro-realism can pass while strict framing fails; result remains
   ineligible for formal front-card selection.
8. Strict framing can pass while Doc252 micro-realism fails; result remains
   ineligible only when Doc252 is explicitly required.
9. Existing Expression and Body framing behavior is unchanged.
10. `left_front_25` / `right_front_25` remain auxiliary/reference semantics and
    do not become formal Face slots.
11. Historical/context-only Face records are not rejected by the new numeric
    formal envelope because they are not formal `standard_front` activation.
12. Target-only collection remains auxiliary and cannot satisfy the formal
    numeric envelope.
13. Missing calibration artifact prevents enabling the numeric envelope in
    production.

## Non-goals

- Do not change Doc248 or Doc252.
- Do not tune prompt text as the primary repair.
- Do not change Provider/MCP route, budget, retry, or transport fingerprint.
- Do not let framing proof judge skin, hair, eyes, ears, garment, or AI-feel.
- Do not use Formal Core to enforce crop geometry.
- Do not apply the numeric envelope to historical, target-only, 25-degree
  auxiliary, Expression, or Body paths.

## Expected outcome

After the old Face framing module is tightened, the system should be able to
say:

```text
The face card is not only a 1024x1536 image with a front-facing subject; it
also satisfies the approved standard-front model-card crop envelope and remains
consistent with the other candidates in the round.
```

That outcome is independent of whether Doc252 micro-realism is enabled.
