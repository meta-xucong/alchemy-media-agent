# P4 First-Wave Scene Director Implementation Audit

## 1. Milestone Status

```text
phase: P4 first-wave scene directors
ownership: Photography specialized-template module
implementation commit: 507a9b3
shadow planning status: verified
production activation: disabled
real-output acceptance: blocked until shared activation/provider hooks exist
```

P4 implements the safe, module-owned portion of Portrait, Landscape, Still Life
and Animal direction. The planner remains absent from the default Scenario Pack
registry and creates no provider input requirement or provider call.

## 2. Implemented Scene Ownership

| Scene | Capability | Photography-owned direction | Reused foundation boundary |
| --- | --- | --- | --- |
| Portrait | `portrait_photography_direction` | expression, pose, face/body/hands framing and environmental relation | Human Realism, Portrait Identity and reference channel policy |
| Landscape | `landscape_photography_direction` | viewpoint, depth, scale, atmosphere, weather/light coherence and natural materials | Scene Continuity, universal quality and reference channel policy |
| Still Life | `still_life_photography_direction` | grouping, negative space, surface relation, set light, edges and reflections | universal quality and reference channel policy |
| Animal | `animal_photography_direction` | behavior, gaze, body language, motion, habitat relation and species-plausible texture | universal quality and reference channel policy |

Exactly one evidenced first-wave scene director contributes. An unknown or
General scene activates none. Still Life does not create listing or A+ roles.
Portrait does not duplicate anti-AI face guidance. Animal does not claim that a
module-local prompt can replace a shared non-human identity capability.

## 3. Reference And Profile Governance

The P4 tests preserve these invariants:

```text
declared person identity != hair, wardrobe, makeup, lighting or style lock
declared landmark truth != weather, time, lighting or color lock
declared object truth != surface, background, grouping or finish lock
declared animal identity != habitat, action, lighting or finish lock
```

Named photographer activation authority is unchanged:

```text
no trusted frontend selection -> General Photography
free-text name -> General Photography
LLM proposal -> ignored
explicit named selection in the inactive runtime -> blocked, never General fallback
```

## 4. Verification Evidence

```text
Photography P1/P3/P4 focused suite: 28 passed
shared activation/reference/renderer + General/E-Commerce/Project regression: 132 passed
full V3 suite: 553 passed
root suite: 144 passed, 1 unchanged mainline Alchemy Lab failure
compileall: passed
git diff --check: passed
```

The root failure is
`tests/test_api_smoke.py::test_lab_image_planner_never_routes_to_deepseek`.
Both the failing test and `src_skeleton` have no Photography diff relative to
`origin/main`.

## 5. Real-Output Gate

P4 does not claim real-output acceptance. Running provider images from this
branch would require changing or bypassing the shared registration, Central
Brain, provider and result paths, which is forbidden. The metadata reviewer
therefore continues to report `not_run_until_production_activation`.

Real-output acceptance remains required after mainline activation hooks land.
It must compare raw renderer, foundation-only and foundation-plus-Photography
outputs with stable fixtures for all four scenes and both input modes.

## 6. Remaining Blockers

1. P5 requires trusted frontend profile selection, catalog read and persisted
   immutable binding contracts. See
   `PX_MAINLINE_REQUEST_TRUSTED_PHOTOGRAPHER_PROFILE_SELECTION.md`.
2. A specific pet or animal reference requires a shared non-human subject
   identity capability accepted under the three-scene foundation rule. See
   `PX_MAINLINE_REQUEST_NONHUMAN_SUBJECT_IDENTITY.md`.
3. Production registration, real-output review, retry and final delivery remain
   paused until the relevant mainline interfaces land.

No local compatibility field, metadata escape hatch, provider bridge or shared
registry modification was added.
