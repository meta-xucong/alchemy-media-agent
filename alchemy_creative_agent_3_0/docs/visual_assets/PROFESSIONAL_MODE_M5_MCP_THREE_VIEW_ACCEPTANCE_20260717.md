# Professional Mode M5 — MCP Three-View Anchor-Pack Acceptance Record

Date: 2026-07-17  
Feature branch: `codex/professional-m5-three-view-acceptance`  
Baseline: `origin/main@ad62882`  
Status: **non-counting / blocked for strict M5 certification; reference-budget fix awaiting a fresh pixel rerun**

## Scope and boundary

This record covers the smallest relay seam needed to exercise Professional
Mode through the existing Alchemy planning path and the Codex-native MCP
surface. The new `prepare_frozen_professional_native_imagegen_plan` tool is a
planning-only projection: the server-owned Professional binding is resolved by
the embedding host, the existing `ScenarioRuntime` freezes the plan, and the
existing Provider materializer produces the canonical prompt and admitted
references. The relay does not own a Brain, Provider, review/retry store,
candidate store, output storage, or delivery record. It never downgrades an
explicit E-Commerce or Photography template to General.

The resulting images remain
`conversation_only_not_certified`. This is not Web Provider Gate C/D, General
Gate D, Photography P10, E-Commerce Gate C/D, or a production approval.

## Three-view attempt

The real portrait source was copied to the external evidence directory
`D:\AI\m5_professional_acceptance_20260717\root.png` (source SHA-256:
`19a7f099245086b4310299f18a9972cba0703523e581dbea71255d35c1032917`). The
candidate files are intentionally outside the repository and are not committed:

| Stage | Frozen reference lineage | Candidates | Likeness-first winner | Winner SHA-256 |
| --- | --- | ---: | --- | --- |
| front | root | 3 | `front-candidate-3.png` | `2aa7aa6a4826b10e9e2a84b0f4527999d29d79f126a66f31e4b22bfe88262b4b` |
| three-quarter | root + front winner | 3 | `three-quarter-candidate-3.png` | `5de4ac30005b7031a08bebd107e0bd7bf511193d28aba9eafcd38a8dc31f680d` |
| profile | root + front winner + three-quarter winner | attempted | `profile-winner.png` (candidate 1) | `34342a977e80c81c1358fb94b2bfb96355d2d9adf7a7af145d02d9e7e3b26ab8` |

The front and three-quarter prompts were returned by the live remote Brain and
their canonical prompt hashes were respectively:

- front: `0b16ef86b3688ad1aaaa18b5349c711deb9d6eb9c72bb9b8d89fde93a30c2ece`
- three-quarter: `ab1890170606646bd5e6a6a815d22ac5168ff8420460a7e79311c51a784a39d5`

The profile run is deliberately recorded as an equivalent, controlled test,
not as a live remote-Brain pass. The live profile route either returned a
structured role failure or admitted only root/front, which the relay now
blocks with `codex_native_imagegen_professional_reference_parity_mismatch`.
The controlled profile prompt hash was
`37e5664e7500555917d0401a0307defb47ff5d5d0e5e49d41486135a8da3ce0d`.

## Reference-budget comparison

The original M5 attempt expanded root, front, and three-quarter into two
provider-only identity derivatives each (six paths), which exceeded Codex's
five-reference handoff cap before profile pixels could be counted. The branch
now implements `serial_anchor_pack_root_reuse_v1`:

```text
front: root detail + root geometry                            = 2
three-quarter: root geometry + front detail + front geometry  = 3
profile: root geometry + front detail + front geometry
         + three-quarter detail + three-quarter geometry       = 5
```

Focused tests cover root reuse without a second AI generation, exactly five
Professional profile references in declared order, and unchanged ordinary
two-derivative behavior. No new live profile pixels have been counted after
this change; the next run must use the five-reference list and repeat shared
review.

## Controlled five-reference effect comparison

To test the changed transport independently of the unavailable live
Professional relay, three new right-profile candidates were generated with
the exact five-reference bundle above and the same natural-language profile
direction. The files are external, non-certified comparison evidence:

| Candidate | File | SHA-256 | Qualitative observation |
| --- | --- | --- | --- |
| 1 | `D:\\AI\\m5_professional_acceptance_20260717\\profile-five-ref-candidate-1.png` | `728f94e25f162202381594616304d11633a2a47b1c2ce2320f8b5a048df17c3a` | Preserves the root's forehead-to-nose transition and natural asymmetry; the green hair cue remains visible. |
| 2 | `D:\\AI\\m5_professional_acceptance_20260717\\profile-five-ref-candidate-2.png` | `cbc4044619f6bf223870c53ecbb8a7347613d8009ac23d1dd72380a66aa6af67` | Cleanest silhouette and mouth/chin contour in this small comparison, while retaining the root hair cue; not a shared-review winner. |
| 3 | `D:\\AI\\m5_professional_acceptance_20260717\\profile-five-ref-candidate-3.png` | `a5b8d0b722e361f03ac75e51fef5c8a8ea207fcd8d0f447a28f0d78e7957ee38` | Strong nose-bridge and jaw continuity; slightly more stylized hair edge than candidate 2; not a shared-review winner. |

The previous controlled profile winner used the six-derivative-era route. The
new candidates are at least as structurally coherent in this visual spot check
and avoid the transport failure, but this is not an apples-to-apples quality
certificate: the new images were produced through the image-generation tool
with the five references, not through the Alchemy frozen-plan relay and shared
Vision review. Therefore no candidate is promoted to the append-only final
winner record from this comparison alone.

## Shared review evidence

The shared `VisionOutputInspector` was run against the selected front winner
with real-image verification enabled. It returned `status=pass`,
`verification_state=verified`, confidence `0.98`, and score card:

```text
artifact_safety=0.99
composition=0.95
overall=0.97
technical_finish=0.96
issue_codes=[]
```

This is evidence for one winner only. The exploratory nine-output batch was
stopped after an unbounded provider wait and is not counted as nine successful
reviews. No review/retry/final-delivery record was fabricated for the
conversation-only images.

## Professional binding / activation evidence

The frozen-plan contract resolved the server-owned fixture binding with:

```text
project_id=project_professional
people_asset_id=person_1
pack_version_id=pack_1
professional_identity_view_ids=front_1,three_quarter_1,profile_1
professional_binding_evidence_sha256=30386a57ac3b5ad7935ce7dfc27eeca0448e7c199a621bcb978567b54a492f9f
```

The activation receipt is projected from the existing V3 frozen capability
plan and contains the Professional binding evidence without exposing the
binding record to the Brain. No new active Face Identity pack was published:
full three-stage shared review, strict reference parity, and final-winner
acceptance are incomplete, so activation is evidence-only and remains
non-counting.

## Blocking findings

1. The live remote profile plan did not reliably admit all three serial-chain
   winners; the new relay fails closed instead of silently dropping the
   three-quarter reference.
2. The previous six-reference transport blocker is addressed in this branch,
   but the new five-reference profile path has not yet completed a fresh live
   pixel run and parity receipt.
3. Only the front winner has an explicit verified shared Vision review record;
   the three-quarter/profile outputs are visual comparison evidence, not
   certified final delivery.

Accordingly, M5 remains blocked and all production gates remain closed. The
next permitted step is to rerun the three-stage append-only
candidate/review/final-winner evidence with the new five-reference list through
the same shared runtime.
