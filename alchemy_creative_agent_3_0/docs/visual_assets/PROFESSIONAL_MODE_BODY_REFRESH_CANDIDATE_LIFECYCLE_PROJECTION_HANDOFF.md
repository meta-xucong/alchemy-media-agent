# Professional Body Refresh Candidate Lifecycle Projection Handoff

## Status

```text
CANDIDATE_LIFECYCLE_PROJECTION_FEATURE_GATE
IMPLEMENTATION_UNDER_REVIEW
NO_REFRESH_OR_GENERATION_AUTHORITY
NO_SLOT_ACTIVATION_OR_DOWNSTREAM_PRODUCT_IMAGE_AUTHORITY
```

This handoff records the narrow correction model for the Body Silhouette
refresh blocker where a controlled `inference_first` run produced generated
candidate artifacts but did not return a refresh summary. A later audit narrowed
the durable card `last_failure_details` in that root to pre-existing readback:
the same `body_formal_slot_reviewed_candidate_count_invalid` details were
already present in the pre-call checkpoint. The current defect is therefore not
proved to be a new formal receipt failure. The confirmed current-run mismatch is
that a candidate can be generated while the synchronous candidate lifecycle
boundary after generation remains non-terminal and publicly under-attributed.

## Observed Mismatch

The refresh contract requires each Body slot to attempt exactly three
candidates, then pass shared review, Body source-standard proof, formal receipt,
and later card-level parity before pending refresh can exist.

The observed run confirmed one new generated candidate with
`candidate_index = 1`. The job metadata safely exposed
`stage = body_silhouette` and `body_refresh_source_mode = inference_first`, but
did not expose the Body slot key or the candidate count. The runner did not
return a terminal refresh summary, did not form pending refresh slots, and did
not activate or write downstream product images. The exact post-generation
phase is unknown from durable public evidence: it may be before review
extraction, inside review extraction, before formal receipt, or inside formal
receipt.

The fix must not infer the missing phase from call order. It must make the
server-owned candidate lifecycle phase explicitly readable.

## Authoritative Fix Boundary

The owning fix is a public-safe candidate lifecycle checkpoint/projection
shared by the CharacterCard refresh `_prepare_slot` path and the ProductApi /
Anchor candidate creation boundary. ProductApi/Anchor must persist or expose
server-owned progress before and after every synchronous boundary where the
runner can otherwise stop without a closed terminal state.

The current implementation scope is deliberately narrower than the earliest
draft wording: it covers durable post-job checkpoints once a ProductJobRecord
exists, plus returned-stage CharacterCard formal checkpoints. It does not claim
to solve a permanent pre-durable create/plan hang where ProductApi never
returns a job record. That pre-durable authority remains a separate caveat for a
future gate.

The projection may expose only closed typed fields:

```text
stage
slot_key
candidate_index
candidate_count
lifecycle_phase
status
failure_family
failure_code
```

The projection must not expose prompts, raw responses, URLs, filesystem paths,
provider payloads, asset IDs, output IDs, job IDs, candidate IDs, or raw
exception text.

Required progress/checkpoint points:

1. after ProductApi creates a durable candidate job record and generated job
   returns;
2. before review extraction;
3. after review extraction returns or blocks;
4. before formal receipt construction when the CharacterCard stage returns;
5. after formal receipt construction or formal blocked terminal when the
   CharacterCard stage returns.

Superseded/narrowed: the earlier "before ProductApi/Anchor candidate
create/plan" checkpoint wording is not implemented in this feature because no
durable ProductJobRecord exists at that boundary. The feature must not be
reported as fixing a pre-durable permanent plan hang.

The fields must be server-owned and typed: `candidate_index` is an integer in
`1..3`; `candidate_count` is the formal expected count, normally `3`; phase,
status, family, and code are closed literals. Client metadata must not be able
to forge these fields.

## Non-Changes

This feature must not:

- relax `standard_three_candidate = 3`;
- treat a generated artifact as an accepted slot, winner, or pending refresh;
- change shared review, formal receipt, Body source-standard, or cross-view
  parity eligibility;
- extend outer runner watchdogs as the fix;
- add thread-kill watchdog behavior that leaves orphan provider work;
- change prompt wording, provider route, provider cap, source-mode contract,
  Face Identity ownership, slot activation, downstream E-Commerce, Photography,
  or General behavior.

## Required Deterministic Coverage

The feature must prove with fake/deterministic seams:

1. ProductApi/Anchor candidate request metadata carries server-owned
   `stage`, `slot_key`, `candidate_index`, and `candidate_count`;
2. a generated job produces a readable checkpoint before review extraction;
3. review extraction produces before/after checkpoints;
4. formal receipt produces before/after checkpoints, including blocked
   terminals;
5. pre-durable plan boundary exceptions remain closed typed projections, while
   permanent pre-durable non-return remains a documented caveat;
6. ordinary `RuntimeError` and `KeyboardInterrupt` are not swallowed or
   reclassified as lifecycle progress;
7. no generated artifact becomes an accepted slot, pending refresh, activation,
   or business output;
8. warnings and lifecycle diagnostics are sanitized consistently and contain no
   raw prompt, response, path, URL, provider payload, asset ID, or output ID.

## Current Gate

This gate may implement only the closed checkpoint contract and deterministic
tests described above. It must not run a real refresh, call Host/MCP/ImageGen,
activate slots, or write downstream product images. Merge and any follow-up
refresh require separate reviewer gates.
