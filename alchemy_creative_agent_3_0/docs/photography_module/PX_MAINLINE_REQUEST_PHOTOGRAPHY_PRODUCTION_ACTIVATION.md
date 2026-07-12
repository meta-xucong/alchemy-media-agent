# PX Mainline Request: Photography Production Activation

## 1. Request Status

```text
request_id: PHOTOGRAPHY-MAINLINE-003
status: open - blocking P6 production activation and real-provider acceptance
request_owner: Photography Module
implementation_owner: V3 Scenario Runtime / Project Mode / product composition owners
```

`PHOTOGRAPHY-MAINLINE-001` and `PHOTOGRAPHY-MAINLINE-002` are landed at
`origin/main@1c9b254`.  P5 now has an approved-record projection and immutable
binding adapter.  The remaining blocker is not a profile field: it is the
shared, central-runtime activation path.

## 2. Current Mainline Behavior

The default `ScenarioPackRegistry` statically lists General, E-Commerce and
placeholder packs only.  `PhotographyScenarioPack` is intentionally absent.
`ProjectTemplateRegistry` therefore keeps `photographer_template` as a
placeholder pointing to `future_photographer`.  `ScenarioRuntime` resolves
only General/E-Commerce template capability policies, and `V3ProductApiService`
has only an E-Commerce-specific pack-output integration.

Consequently, registering the Photography pack locally, directly calling the
provider, copying E-Commerce's service shortcut, or changing a job's metadata
after planning would bypass the central brain, frozen plan, shared review/retry
and final delivery resolver.  All are forbidden.

## 3. Minimal Requested Change

Provide a mainline-owned, explicit production activation seam for a specialized
Scenario Pack.  Its first use is Photography, but it must not turn General or
E-Commerce into Photography code.

Required composition responsibilities:

1. Register an approved active `PhotographyScenarioPack` into the default
   Scenario Hub only behind an explicit deployment/feature gate.
2. Replace the `photographer_template` placeholder with a Photography template
   manifest whose scenario pack is `photography`, status is active only under
   the same gate, and whose output role owner is `photography_scenario_pack`.
3. Let the selected specialized pack provide a **frozen planning contribution**
   to `ScenarioRuntime` before the central Brain/capability-plan preparation.
   The runtime must compose that contribution through existing
   `CapabilityContributionComposer`; it must not let a pack call a provider.
4. Pass only the server-pinned `photographer_profile_binding` to the
   Photography adapter.  The adapter must call
   `PhotographyScenarioPackPlanner.plan_from_pinned_binding`, not its legacy
   local-control `plan` helper.
5. Build the server's `PhotographerProfileCatalog` from the deployed,
   operator-reviewed Photography record source and expose only the existing
   mainline catalog endpoint.  The frontend must continue to read that route,
   retain General as default, and submit `user_explicit_ui` only after a manual
   confirmation.
6. Route `nonhuman_identity_reference` only through the landed shared
   `nonhuman_subject_identity` capability.  Missing/unreadable/unsupported
   high-fidelity paths must stay blocked; no template fallback is permitted.
7. Preserve mainline shared visual review, one bounded non-human retry, frozen
   plan retry, append-only attempt history and final-delivery resolution.

## 4. Typed Integration Contract

The seam should accept a server-owned context, rather than newly exposing low
level renderer inputs:

```python
class SpecializedScenarioPlanningContext:
    job_id: str
    user_input: str
    scenario_resolution: ScenarioPackResolution
    selected_mode_id: str | None
    uploaded_asset_ids: list[str]
    uploaded_asset_roles: list[str]
    project_context_snapshot: dict[str, Any]
    photographer_profile_binding: PhotographerProfileBinding | None
    frozen_capability_activation_plan: CapabilityActivationPlan | None
```

The Photography adapter result may contain only structured direction,
capability contributions, shot specifications and review expectations.  It may
not return provider requests, prompt text replacing the central Brain output,
profile-selection changes, or custom retry counters.

The Photography template policy needs its own manifest-level policy (for
example `photography_template_capabilities`), with universal quality and
reference-channel policy reusable from foundation.  Its deliverable roles and
professional-set direction remain Photography-owned; no Photography map may be
added to General's policy.

## 5. Validation And Failure Semantics

```text
activation gate off                         -> Photography remains inactive/placeholder
gate on + no named selection                -> General Photography binding
gate on + named selection                   -> existing mainline explicit binding rules
binding absent/mismatched in adapter        -> block before central Brain/provider
attempt to mutate profile on generate/retry -> existing 409 immutable binding error
typed animal reference missing/unsupported  -> existing capability mismatch block
pack returns direct provider request         -> reject adapter result / fail closed
```

An inactive deployment must not make the named profile selector visible as an
operational workflow outside Photography, and General/E-Commerce requests must
remain byte-for-byte compatible at their public boundaries.

## 6. Required Mainline Tests

1. Gate-off scenario cards, templates and product requests remain unchanged.
2. Gate-on registers Photography only; General/E-Commerce cards, policies,
   catalog fields and output summaries remain isolated.
3. The runtime adapter receives the exact immutable profile binding and cannot
   use prompt/LLM metadata to replace it.
4. The P5 adapter path uses `plan_from_pinned_binding`; the local shadow
   `plan()` entrypoint is not called in production.
5. The profile endpoint and frontend confirmation continue to enforce explicit
   selection in direct and Project Mode creation.
6. Typed non-human reference reaches the shared high-fidelity capability and
   blocks without text fallback on all mismatch paths.
7. A generate/retry keeps the frozen Photography contribution, profile binding,
   shared retry budget and selected-result semantics.
8. Real-provider acceptance records raw renderer, foundation-only and
   foundation-plus-Photography comparisons for all four first-wave scenes and
   both text/reference input modes (Doc103 Gate C/D).

## 7. Photography Work Paused

The Photography branch will not register itself in `ScenarioPackRegistry`,
modify `ScenarioRuntime`, modify `V3ProductApiService`, activate the
`photographer_template`, alter shared capability policy code, or call a
provider.  It can continue only module-local P6 planning and test work that
does not claim production activation.  Production set delivery, continuation,
live output review and merge readiness wait for this request.
