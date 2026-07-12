# P09: P6 Professional Set And Continuation Audit

## Status

```text
module-owned planning: implemented
central-runtime single-hero handoff: verified at origin/main@71a4679
professional-set production execution: blocked on PHOTOGRAPHY-MAINLINE-004
real-provider quality acceptance: not run
deployment gate: remains off by default
```

## Scope Classification

This milestone is Photography specialized-template work. It defines what a
professional photographic session contains and therefore belongs only in
`app/scenario_packs/photography/`. It does not add session roles to General,
reuse E-Commerce listing/A+ roles, or create a shared visual capability.

## Implemented Module-Owned Contract

The Photography planner can now produce this planning-only set:

```text
session_hero
environmental_context
detail_or_moment
```

Every pair of roles differs across at least two observable dimensions among
framing, camera relation, decisive moment, depth/focus and motion. All roles
retain one immutable photographer-profile checksum, color/finish anchor and
reference-truth contract.

`PhotographyProfessionalSetPlan` records:

- the Photography-owned role order and shot IDs;
- the exact pinned General or explicit named-profile snapshot;
- set-level color, finish, identity and reference coherence;
- shared final-delivery ownership across append-only attempts; and
- beginner delivery of one final winner per role, with superseded attempts
  folded into history.

The module does not call a provider, inspect pixels, retry, or select results.
Those responsibilities remain with the shared V3 runtime.

## Continuation Contract

`PhotographySetContinuationDirector` creates planning-only, append-only child
intent for one set role. It preserves the parent set ID, role, immutable truth,
profile snapshot and coherence contract.

For a named profile, continuation requires an exact explicit UI
reconfirmation of profile ID, version and technique checksum. A mismatch or
missing confirmation blocks. General Photography never receives a named
selection source. New reference evidence is marked for shared capability
revalidation, including shared non-human identity negotiation when applicable.

No Project Mode route is claimed by this module-local contract.

## Gated Mainline Verification

The landed `PHOTOGRAPHY-MAINLINE-003` path passes its gate-off/on, immutable
binding, pinned planner, non-human identity, shared review/retry and
General/E-Commerce isolation tests.

The professional-set production probe found the expected safe activation
boundary:

1. the active Photography manifest supports only `single_hero` and
   `reference_reshoot`;
2. a `professional_set` selection warns and resolves to `single_hero`;
3. `PhotographyScenarioPlanningAdapter` hard-codes `delivery_mode=single_hero`,
   `output_count=1` and `requested_image_count=1`;
4. the active Project Mode template exposes `photography_single_hero`; and
5. the shared runtime has no Photography role-continuation lineage or per-role
   final-delivery contract.

Expanding any of those seams requires shared runtime, Project Mode, public
contract and delivery-resolver ownership. The Photography branch therefore
opened `PHOTOGRAPHY-MAINLINE-004` and left the production manifest unchanged.

## Acceptance Evidence

The focused P6 suite covers:

- three meaningful set roles;
- all four first-wave scene directors;
- set-level profile/color/reference coherence;
- explicit-only named profile behavior;
- reference-conditioned identity truth across every role;
- exact named-profile continuation reconfirmation;
- General continuation neutrality;
- new-evidence shared capability revalidation; and
- no private provider/review/retry/final-delivery path.

Real-provider text/reference comparisons and pixel-quality review remain a
release gate after `PHOTOGRAPHY-MAINLINE-004` lands and credentials are
available.
