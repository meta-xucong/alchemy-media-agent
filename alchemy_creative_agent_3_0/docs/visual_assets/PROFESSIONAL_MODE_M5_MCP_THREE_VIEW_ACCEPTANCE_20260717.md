# Professional Mode M5 — MCP Three-View Anchor-Pack Acceptance Record

Date: 2026-07-17  
Feature branch: `codex/professional-m5-three-view-acceptance`  
Baseline: `origin/main@ad62882`  
Status: **non-counting / blocked for strict M5 certification**

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
2. The Codex built-in ImageGen handoff accepts at most five reference paths,
   while the strict profile chain contains six derived reference files (two
   crops per source view). The profile image therefore cannot be called strict
   parity evidence until that handoff limitation is resolved by the supported
   host surface.
3. Only the front winner has an explicit verified shared Vision review record;
   the three-quarter/profile outputs are visual comparison evidence, not
   certified final delivery.

Accordingly, M5 remains blocked and all production gates remain closed. The
next permitted step is to make the supported Codex handoff admit the complete
profile reference set (or obtain an explicitly approved equivalent) and rerun
the three-stage append-only candidate/review/final-winner evidence through the
same shared runtime.

