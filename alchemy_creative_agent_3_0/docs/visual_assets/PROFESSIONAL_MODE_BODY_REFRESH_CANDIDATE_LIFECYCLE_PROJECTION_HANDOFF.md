# Professional Body Refresh Candidate Lifecycle Projection Handoff

## Status

```text
CANDIDATE_LIFECYCLE_PROJECTION_FEATURE_GATE
IMPLEMENTATION_SCOPE_ONLY
NO_REFRESH_OR_GENERATION_AUTHORITY
NO_SLOT_ACTIVATION_OR_DOWNSTREAM_PRODUCT_IMAGE_AUTHORITY
```

This handoff records the narrow correction model for the Body Silhouette
refresh blocker where a controlled `inference_first` run produced two
generated front candidates and then timed out without a lifecycle summary.

## Observed Mismatch

The refresh contract requires each Body slot to attempt exactly three
candidates, then pass shared review, Body source-standard proof, formal receipt,
and later card-level parity before pending refresh can exist.

The observed run created generated artifacts for candidate 1 and candidate 2,
but no candidate 3 durable job and no closed refresh summary. This is not a
Body source-mode, prompt, provider-cap, Face Identity, activation, or downstream
product-image problem. The likely seam is the pre-durable ProductApi/Anchor
planning boundary: a candidate can enter planning before a durable job record
exists, so an outer runner timeout cannot see a public candidate terminal state.

## Authoritative Fix Boundary

The owning fix is a public-safe candidate lifecycle projection shared by the
CharacterCard refresh `_prepare_slot` path and the ProductApi/Anchor candidate
creation boundary. The projection may expose only closed typed fields:

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

1. candidate 1 and candidate 2 can generate and review, while candidate 3 blocks
   before durable ProductJob persistence, and the public state still contains a
   closed candidate lifecycle failure;
2. candidate review wait/failure receives the same public-safe lifecycle
   treatment;
3. formal receipt `ValueError` and existing `AnchorCandidateUnavailable`
   mappings remain compatible;
4. no generated artifact becomes an accepted slot, pending refresh, activation,
   or business output;
5. warnings and lifecycle diagnostics are sanitized consistently and contain no
   raw prompt, response, path, URL, provider payload, asset ID, or output ID.

