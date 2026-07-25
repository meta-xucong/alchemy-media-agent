# Doc254 — Doc252 Controlled Production Seam Plan

## Purpose

Doc252 and Doc253 now exist as independent contract modules. Phase4 must not
turn them into broad production behavior. This plan defines the only proposed
production seam before any code is written.

No image generation, slot write, activation, Provider/MCP routing change, or
Formal Core change is authorized by this document.

## Current approved pieces

- Doc252 `micro_real_human_fidelity_v1`:
  - default off;
  - trusted Host only;
  - additive prompt guidance only;
  - approved scope only: `character_card_face_identity:standard_front`;
  - requires existing prompt authority;
  - candidate Enhanced proof only;
  - no route, budget, retry, age, identity, or reference ownership mutation.

- Doc253 `standard_front_framing_envelope_v1`:
  - standalone Face framing contract;
  - requires explicit server-owned approved calibration artifact;
  - applies only to Face `standard_front` formal slot;
  - not enabled for production until calibration is separately approved.

## Proposed Phase4 seam

Only the existing Face trusted Host path may call Doc252:

```text
ProductApiAnchorPackPreparationHost
  -> existing professional standard_front request metadata
  -> existing Brain/Host prompt-authority contract
  -> Doc252 append_micro_real_human_fidelity_guidance()
  -> existing prompt compilation / provider materialization path
  -> canonical shared Vision review
  -> Doc248 proof
  -> Doc252 proof
  -> Face-local Doc248+Doc252 composite eligibility bundle
  -> one module-neutral candidate Enhanced eligibility summary
  -> Formal Core may rank eligible candidates
```

The seam is strictly additive. It may add Doc252 guidance and later Doc252
candidate proof, but it must not create a second prompt author or a second
winner path.

## Candidate Enhanced proof composition

The current FormalSlotCandidateSummary carries a single `enhanced_proof`.
Therefore Phase4 must not simply "add Doc252 proof" into that field after
Doc248. Doing so would either overwrite Doc248, create a second hidden winner
authority, or force Formal Core to understand multiple portrait modules.

The production seam must use a Face-local composite adapter:

```text
Doc248 absolute_portrait_realism_v1 proof
Doc252 micro_real_human_fidelity_v1 proof
  -> FaceStandardFrontEnhancedProofBundle
  -> one FormalSlotCandidateEnhancedProofSummary
```

Rules:

1. Doc248 proof remains intact and independently inspectable in Face-local
   evidence.
2. Doc252 proof remains intact and independently inspectable in Face-local
   evidence.
3. The composite adapter emits exactly one module-neutral
   `FormalSlotCandidateEnhancedProofSummary` bound to the same
   candidate/output.
4. Formal Core receives only the composite eligibility summary and the ranking
   key. It does not know Doc248, Doc252, micro-realism, beauty, skin, hair,
   ears, or framing.
5. No second winner, second receipt, or second activation path is created.
6. If Doc252 is disabled, the existing Doc248 path must remain byte-for-byte
   equivalent to the current implementation.

Suggested composite identity:

```text
profile_id = face_standard_front_enhanced_quality_bundle_v1
requirement_id = doc248_absolute_realism_plus_optional_doc252_micro_fidelity_v1
```

This identity belongs to the Face standard-front adapter, not to Formal Core.

## Explicit non-seams

Doc252 must not be called from:

- public route payload parsing;
- ordinary `CreateCreativeJob` metadata;
- Expression Set;
- Body Silhouette;
- 25-degree auxiliary bridge;
- target-only collection;
- historical/context-only Face loading;
- Provider/MCP routing;
- MCP recovery/checkpoint replay;
- FormalSlotAcceptanceCore;
- slot receipt persistence;
- public activation.

Doc253 must not be connected to production until an approved calibration
artifact exists.

## Authority table

| Decision | Owner | Doc252 authority |
| --- | --- | --- |
| Whether Doc252 is enabled | trusted Face Host | may request only approved scope |
| Prompt authorship | existing Brain/Host | may append guidance only |
| Generation route | server-owned existing route/pipeline | no authority |
| Candidate count | Formal/professional slot flow | no authority |
| Candidate winner | Formal Core | no authority |
| Micro-realism evidence | Doc252 Enhanced proof | yes, only as one input to Face-local composite eligibility |
| Composite candidate eligibility | Face standard-front adapter | Doc252 contributes only when explicitly required |
| Face framing | Face framing profile / Doc253 later | no authority |
| Slot receipt/activation | FormalSlotReceipt/lifecycle | no authority |

## Required red tests before implementation

### Default-off behavior

1. Existing Face standard_front preparation without Doc252 trusted metadata
   produces the same prompt contract and metadata as before.
2. Ordinary route payload cannot enable Doc252.
3. Ordinary job metadata cannot enable Doc252.

### Trusted additive guidance

4. Trusted Face Host standard_front call appends Doc252 guidance to the existing
   prompt contract.
5. The prompt contract must already contain prompt authority; missing authority
   fail-closes.
6. Generated projection does not add, remove, or alter route, budget, retry,
   age, identity, or reference ownership fields.
7. Expression, Body, and 25-degree auxiliary calls do not call Doc252 and their
   behavior remains unchanged.

### Candidate proof composition

8. A standard_front candidate with canonical shared Vision + Doc248 pass +
   Doc252 pass emits one composite candidate Enhanced proof.
9. Doc248 pass + Doc252 pass is eligible when Doc252 is required.
10. Doc248 fail + Doc252 pass is not eligible.
11. Doc248 pass + Doc252 fail is not eligible when Doc252 is required.
12. Doc248 pass + missing Doc252 proof is not eligible when Doc252 is required.
13. Doc252 disabled preserves the existing Doc248 candidate Enhanced proof path
    byte-for-byte.
14. The composite proof is bound to the same candidate_id/output_id as both
    source proofs; mismatch fails closed.
15. Doc252 proof is not treated as generic shared Vision receipt.
16. There is no second winner, receipt, or slot write.

### Isolation

17. Formal Core source remains free of Doc252 strings.
18. Provider/MCP route source remains unchanged except for receiving already
    compiled additive guidance.
19. Public summary leaks no prompt/path/provider/handoff/artifact IDs.

## Implementation boundary after tests

If the red tests are accepted, implementation may touch only:

- the Face trusted Host prompt-preparation seam;
- the Face candidate review-to-composite-Enhanced-proof adapter;
- Doc252-specific tests.

Implementation must not touch:

- Formal Core;
- slot receipts;
- activation;
- Provider/MCP route selection;
- recovery/retry;
- Expression/Body;
- Doc253 production activation.

## Controlled validation after implementation

Only after code review and pure tests pass may a controlled image comparison be
considered. That future run must:

- use an isolated evidence root;
- generate exactly three standard_front candidates;
- keep Doc252 enabled only through trusted Host;
- produce canonical shared Vision + Doc248 + Doc252 proof per candidate;
- use Formal Core only for an ephemeral comparison winner unless separately
  authorized;
- not write Face slot or activation.
