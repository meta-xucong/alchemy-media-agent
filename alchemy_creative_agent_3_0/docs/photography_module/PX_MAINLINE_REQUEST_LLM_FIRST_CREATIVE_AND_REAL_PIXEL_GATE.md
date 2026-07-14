# PX-MAINLINE-005: LLM-First Photography Creative Direction And Real-Pixel Gate

> Historical request, fulfilled by mainline `fc3f5c2` and `db70c44`. It is
> retained as the acceptance contract. The remaining work is real-provider
> evidence, not a missing Photography-private implementation.

## Request

Implement the smallest shared-runtime contract that makes active Photography
creative direction LLM-authored and makes P10/production quality certification
depend on shared real-pixel review.

## Current Blocking Behavior

Photography is active through the shared runtime, but its specialized planner
still derives creative scene/commission/shot prose from keyword/default logic.
Its template policy does not require a successful remote creative Brain result,
while E-Commerce does. The controlled P10 reviewer is `metadata_only`, which
cannot certify visual quality.

## Required Mainline Changes

1. Add a Photography policy flag equivalent to E-Commerce
   `requires_remote_creative_brain=True`, with
   `creative_direction_owner=remote_v3_llm_brain`.
2. For active Photography, remote Brain unavailable, invalid, or
   role-cardinality-mismatched output must raise a typed block. Do not use
   deterministic Brain fallback as the creative result.
3. Pass the frozen non-creative Photography contract to the Brain: template and
   scenario ID, role IDs/count, pinned profile checksum, reference-channel
   ownership, explicit controls, and forbidden cross-template roles. The Brain
   returns one natural-language image direction per role.
4. Preserve the specialized role contract only as a validator/ledger record.
   It must not prepend fixed `cover hero`, camera, pose, crop, lighting, or
   scene text over the Brain's direction.
5. For P10 and production Photography, require shared `vision_model` or
   `hybrid` review. `metadata_only` produces a non-certifying terminal block,
   not a successful quality verdict. Reuse current shared retry and winner
   selection; add no photography-private path.

## Compatibility And Isolation

- Gate remains off by default.
- General keeps its existing fallback policy and receives no Photography data.
- E-Commerce keeps its existing LLM requirement and marketplace role map.
- Existing immutable profile and reference contracts remain authoritative.
- GPT Image 2 remains the sole production renderer.

## Required Tests

1. Photography remote Brain unavailable/invalid/wrong cardinality -> typed
   block, no deterministic role direction and no Provider call.
2. Successful Photography Brain output -> exactly one direction per frozen
   role; the role ledger validates but does not overwrite it.
3. General/E-Commerce -> no Photography controls, profile binding,
   `photography_direction`, role IDs, or prompt additions.
4. Photography -> no General `suite_direction` / `cover hero` or E-Commerce
   role prompt contribution.
5. `metadata_only` -> non-certifying production/P10 block; `vision_model` and
   `hybrid` -> shared retry/final-selection contract.
6. Existing three-role terminal aggregation, profile pinning, reference
   high-fidelity blocking, General isolation, and E-Commerce continuation tests
   remain green.

## Photography Work Paused

The Photography branch will not create a private LLM fallback, pixel reviewer,
Provider route, retry path, or schema workaround. After this lands, it will
rebase, remove active deterministic creative ownership, and run the P10 matrix.
