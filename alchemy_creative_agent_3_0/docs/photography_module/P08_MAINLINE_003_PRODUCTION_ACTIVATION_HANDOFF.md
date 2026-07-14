# P08: PHOTOGRAPHY-MAINLINE-003 Production-Activation Handoff

> Historical status: this document describes the initial 003 seam. Its
> professional-set limitation was superseded by mainline `1578cbc`; specialized
> role prompt ownership was corrected by `364a1c8`. Current release authority
> is P11 plus the active shared runtime contracts.

## Status

```text
mainline contract: implemented
deployment default: disabled
real-provider acceptance: still required before enabling the deployment gate
first active scope: one Photography single-hero output or reference reshoot
```

This document records the mainline integration for
`PHOTOGRAPHY-MAINLINE-003`.  It does not mark the Photography template as
generally released: the explicit deployment gate remains off until the
Photography team records the required real-output evidence.

## Runtime Contract

The deployment gate is:

```text
V3_PHOTOGRAPHY_PRODUCTION_ENABLED=true
```

With the gate off, `photography` is absent from the default Scenario Pack
registry and `photographer_template` remains the existing placeholder.  With
the gate on, the pack is active and the template is active, maps to
`photography`, and declares `photography_scenario_pack` as its deliverable
owner.  General and E-Commerce registration, policies, cards, and public
result shapes do not change.

For each Photography job, the mainline flow is:

```text
mainline validates and pins profile
-> PhotographyScenarioPackPlanner.plan_from_pinned_binding
-> frozen specialized planning contribution
-> Central Brain + frozen CapabilityActivationPlan
-> CapabilityContributionComposer
-> existing generation / pixel review / bounded retry / final resolver
```

The specialized adapter cannot call the local `plan()` selector helper, a
provider, a visual reviewer, a retry loop, or a result selector.  It receives
only the server-owned immutable profile binding.  The mainline Product API
persists the frozen planning contribution beside the frozen capability plan;
generate and retry paths reuse it and reject attempts to replace the profile
binding or specialized-plan snapshot.

`photography_direction` is a capability manifest restricted to
`photographer_template`.  It composes through the existing
`CapabilityContributionComposer` only after that capability is present in the
frozen plan.  The plan carries technique facts, not a named photographer's
name, into generation guidance.

## Profile And Non-Human Identity Boundaries

- The existing mainline public catalog endpoint remains the only profile
  selection source.  General Photography is the default; a named record
  requires `user_explicit_ui` confirmation and the mainline pins the resulting
  version/checksum.
- A deployed operator catalog must project the same approved record set into
  the mainline catalog and into the Photography planner.  If a pinned named
  record cannot be resolved exactly, the job blocks; it never substitutes
  General Photography.  The gate-on default Product API composition performs
  that projection from one operator catalog; custom deployments must inject
  the same catalog pair when they add their own reviewed records.
- An explicit same-animal/pet request or a typed
  `nonhuman_identity_reference` requires the shared
  `nonhuman_subject_identity` capability.  Missing, unreadable, or unsupported
  native high-fidelity input blocks rather than becoming a text-only request.
- The current active contract intentionally limits the scenario to
  `single_hero` and `reference_reshoot`.  `professional_set` remains a future
  Photography-owned delivery contract and is not exposed by this gate.

## Verification

The focused production-activation and existing Photography/mainline/non-human
contracts pass together.  They verify gate-off behavior, gate-on registration,
immutable general and named profile bindings, pinned-only planner entry,
composer provenance, shared generation/review/retry reuse, non-human failure
semantics, and General/E-Commerce isolation.

## Remaining Photography-Team Work

After rebasing onto the mainline commit that contains this handoff, the
Photography branch can begin P6 integration verification.  It must keep the
deployment gate off until it records real-provider, real-pixel evidence for
portrait, landscape, still life, and animal directions in both text and
reference-conditioned modes.  That acceptance must demonstrate the shared
review/retry/final-delivery path; no Photography-private provider or retry
implementation is permitted.
