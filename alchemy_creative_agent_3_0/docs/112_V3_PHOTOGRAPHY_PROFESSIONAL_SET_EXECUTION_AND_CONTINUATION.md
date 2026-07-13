# Doc112 — V3 Photography Professional-Set Execution and Continuation

Status: implemented in the shared runtime; production deployment gate remains off by default.

## Purpose

PHOTOGRAPHY-MAINLINE-004 turns the Photography module's frozen professional-set plan into shared V3 work. It does not create a photography-specific provider, review loop, retry loop, or result selector.

The three immutable roles are:

1. `session_hero`
2. `environmental_context`
3. `detail_or_moment`

When `V3_PHOTOGRAPHY_PRODUCTION_ENABLED` is off, the Photography Scenario Pack is not registered and the photographer template remains unavailable. A disabled deployment must never silently create a General job or reduce a requested professional set to one image.

## Execution contract

With the gate enabled, a `professional_set` request follows this path:

```text
Photography planner freezes brief, profile binding, shot specs and set coherence
  -> Scenario Runtime freezes a generic shared role-execution plan
  -> Central Brain maps one frozen role recipe to each of the three assets
  -> shared Provider generation, review and bounded retry run for every asset
  -> shared final-delivery resolver exposes one winner for each role
```

The frozen role plan carries each role's composition/crop, camera relation, focus/motion, lighting, color/finish anchor, reference truth, negative constraints and review obligations. It is opaque to Central Brain's creative-reasoning request: Central Brain receives only the specialized-plan activation marker and the shared runtime materializes the already approved role facts afterward.

All three assets use the same frozen:

- photographer profile ID, version and technique checksum;
- color and finish anchor;
- reference-truth contract;
- frozen `CapabilityActivationPlan`, unless a continuation has one allowed auditable amendment.

Automatic retry results remain append-only. The ordinary delivery surface resolves the current winner per role and folds superseded attempts into history.

## Project Mode interface

Create a professional set through the normal project job route with:

```json
{
  "template_id": "photographer_template",
  "metadata": {"selected_mode_id": "professional_set"}
}
```

The public role-continuation route is intentionally Photography-namespaced:

```text
POST /api/v3/creative-agent/projects/{project_id}/jobs/{parent_job_id}/photography-roles/{role_id}/continuations
GET  /api/v3/creative-agent/projects/{project_id}/jobs/{root_job_id}/photography-roles/{role_id}/delivery
```

Continuation request:

```json
{
  "correction_note": "optional user correction",
  "new_reference_asset_ids": ["optional authorized project asset"],
  "profile_selection_source": "user_explicit_ui",
  "reconfirmed_profile_id": "required only for a named profile",
  "reconfirmed_profile_version": "required only for a named profile",
  "reconfirmed_technique_package_checksum": "required only for a named profile"
}
```

Rules:

- A continuation is an append-only child job; it never uses select, delete, or an internal automatic retry as a user redo API.
- It can target only a declared role from the root professional-set contract.
- The default child reuses the parent's frozen capability plan exactly.
- New authorized evidence is re-negotiated through the shared capability path. If it materially changes the plan, one auditable amendment per root-role lineage is allowed only when `V3_CAPABILITY_PLAN_AMENDMENT_ENABLED=true`; otherwise the child is blocked.
- A named profile requires the user to reconfirm the exact ID, version and checksum through `user_explicit_ui`. A mismatch blocks; no General Photography fallback is permitted.
- New animal/pet identity evidence must pass the same shared native high-fidelity negotiation. A missing or unsupported capability blocks instead of falling back to text-only identity instructions.
- Historical jobs without `photography_role_lineage` remain readable but cannot use role continuation.

The role-delivery resolver preserves previous successful delivery when a later child is planned, blocked, or failed. Once a child succeeds, it becomes the current final result for that role while all older candidates remain in append-only history.

## Isolation and release boundary

`professional_set`, `photography-roles`, photographer profile reconfirmation and Photography role recipes are not General Template concepts and are not imported into E-Commerce. E-Commerce continues to own `ecommerce-slots`; its contracts and UI do not consume the Photography role routes.

This code change does not certify production use. P10's real-provider matrix remains required for portrait, landscape, still life and animal, each in text-to-image and reference-reshoot modes. The release still needs real Provider, visual-review and human acceptance evidence before enabling the Photography production gate in an environment.

## Automated acceptance

`tests/test_v3_photography_mainline_004.py` covers:

- three-role generation, per-role shared review and final delivery;
- append-only per-role continuation and persistence/reload;
- exact named-profile reconfirmation and immutable binding;
- new animal identity evidence re-negotiation and native-capability blocking;
- General isolation.

The existing P6 module planning and P10 Provider acceptance-matrix tests remain the Photography-owned evidence contract; this document only supplies the shared-runtime execution seam they require.
