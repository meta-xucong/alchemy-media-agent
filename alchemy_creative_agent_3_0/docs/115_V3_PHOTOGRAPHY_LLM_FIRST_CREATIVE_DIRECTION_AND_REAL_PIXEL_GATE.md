# Doc115: Photography LLM-First Creative Direction And Real-Pixel Gate

> **Doc135 refinement:** photography roles are structural lineage only. No
> local camera, lighting, pose or retry phrase may be materialized; each
> complete image direction is signed by the remote Brain.

## Purpose

An active `photographer_template` is an LLM-first specialized template.  It
does not own a deterministic shot recipe, provider route, visual reviewer,
retry loop, or result selector.

The required execution path is:

```text
explicit user controls + reference truth + pinned profile contract
-> remote Central Brain
-> one natural-language whole-image direction for every frozen role
-> shared GPT Image 2 generation
-> shared vision-model or hybrid final-pixel review
-> bounded shared retry and final winner selection
```

## Frozen Template Contract

Photography may freeze only structural, auditable facts:

- the template/scenario identity and role IDs/count;
- the pinned photographer-profile checksum;
- reference-channel ownership and explicit user controls;
- safe cross-template exclusions;
- append-only role lineage.

`session_hero`, `environmental_context`, and `detail_or_moment` are role
bindings, not camera, lighting, pose, crop, scene, copy, or visual recipes.
The remote Brain owns all of that creative content.  Each Brain direction is
bound by position to exactly one frozen role.

## Fail-Closed Requirement

Photography requires `requires_remote_creative_brain=True` and
`creative_direction_owner=remote_v3_llm_brain`.

When the remote Brain is unavailable, falls back locally, returns invalid
output, or returns a direction count different from the frozen role count,
the job is blocked before provider execution.  It must not fall back to
keyword classification, static lens/lighting/pose prose, a single image, or a
General/E-Commerce plan.

## Real-Pixel Certification

All active Photography roles require shared `vision_model` or `hybrid`
inspection for terminal delivery.  `metadata_only`, local-only inspection,
unavailable vision inspection, or a non-passing inspection is retained in
append-only history but cannot become a delivery winner.  The shared retry and
winner-selection path remains the only retry/selection owner.

The Photography production deployment gate remains disabled by default.  This
contract does not certify a remote Brain, GPT Image 2 Provider, or vision
Provider deployment; those require separate real-environment acceptance.

## Isolation

General and E-Commerce Brain requests never receive the Photography profile,
role IDs, creative context, or prompt additions.  Photography never receives
General `suite_direction`/cover roles or E-Commerce marketplace/slot/copy
semantics.
