# 106 V3 Photography Profile And Non-Human Identity Foundation Contract

Status: mainline foundation contract implemented. The Photography Scenario Pack
remains activation-gated until its own P5/P6 work and live-provider acceptance
are complete.

## 1. Scope And Ownership

This document freezes two shared V3 interfaces requested by the Photography
module:

1. trusted, named photographer-profile selection; and
2. individual non-human subject identity preservation from a typed reference.

The V3 foundation owns validation, activation, immutable bindings, native
provider conditioning, review/retry governance, and compatibility. Photography
owns its scenario directions, named-profile catalog population, and future UI
workflows. Neither interface makes General Template a photography product or
adds photography-only deliverable maps to E-Commerce.

## 2. Trusted Photographer Profile Selection

### 2.1 Public contract

The read-only catalog endpoint is:

```text
GET /api/v3/creative-agent/scenarios/photography/photographer-profiles
```

The job and Project Mode create payloads accept only these product-level
fields:

```text
photographer_profile_id: str | null
photographer_profile_selection_source: "user_explicit_ui" | null
```

The server-owned immutable binding is persisted with the job and, for Project
Mode, under `ProjectRecord.photographer_profile_bindings[job_id]`:

```text
binding_mode: "general" | "named"
profile_id
profile_display_name
profile_version
selection_source
catalog_version
availability_decision
technique_package_checksum
pinned_at
```

The browser exposes this selector only when the resolved scenario is
`photography`. Named entries require a separate manual confirmation click.
Until that click, the payload uses `general_photography`; it never silently
submits a selected named ID.

### 2.2 Validation and compatibility

- no profile ID in Photography creates a `general_photography` binding;
- named IDs require `user_explicit_ui`, otherwise the API returns
  `422 named_profile_requires_explicit_ui_selection`;
- unknown IDs return `422 photographer_profile_not_found`;
- unavailable IDs return `409 photographer_profile_unavailable`;
- region restrictions return `403 photographer_profile_region_restricted`;
- a client cannot submit a stored binding or mutate it during generation;
  either action returns `409 photographer_profile_binding_immutable`;
- the fields are inert outside the resolved Photography scenario;
- historical jobs without a binding remain readable; a new job in an existing
  project defaults to General unless the user confirms a named profile again.

The default catalog intentionally contains only General Photography. A future
Photography catalog owner may register a named record only after rights,
availability, region, and version data are available.

## 3. Non-Human Subject Identity

### 3.1 Typed evidence boundary

The public V3 upload role is:

```text
nonhuman_identity_reference
```

The compatibility alias `nonhuman_subject_identity` resolves to that role.
There is no client species field and no species, pet, animal, or Photography
recipe branch in shared runtime code. Activation requires this typed evidence;
ordinary reference images and ambiguous user words do not silently activate
the capability.

The frozen capability is:

```text
capability_id = nonhuman_subject_identity
profile = reference_truth
evidence = nonhuman_identity_reference
dependencies = reference_channel_policy + universal_visual_quality
```

Its reference truth preserves only the individual’s stable morphology, head
geometry, body proportions, distinctive markings/pattern, and visible coat,
feather, scale, or surface character. The current prompt owns habitat, action,
camera, lighting, color treatment, and finish.

Typed non-human evidence wins over ambiguous photographic terms such as
“portrait”; it must not activate `portrait_identity` or `human_realism` merely
because of that vocabulary.

### 3.2 Provider and review requirements

The shared plugin contributes:

```text
native_nonhuman_identity_reference
input_fidelity = high
on_unsupported = block
```

Production rendering materializes the source as
`nonhuman_subject_identity_truth`. Missing/unreadable references, transport
profiles without high-fidelity conditioning, and upstream rejection of
`input_fidelity` raise a capability mismatch. They must never degrade to a
text-only identity request.

The shared visual review contract uses only ephemeral image comparison. It
does not persist biometric vectors. Its retry codes are:

```text
nonhuman_subject_identity_drift
nonhuman_subject_marking_drift
nonhuman_subject_proportion_drift
nonhuman_reference_used_as_style
```

Retry remains on the ordinary frozen-plan generation/review/retry path, is
limited to one automatic retry for this capability, and never invokes the
human face-local repair flow. Candidate/output history remains append-only;
the existing final-delivery resolver remains the only beginner-facing result
surface.

## 4. Acceptance Matrix

| Area | Required evidence | Mainline status |
| --- | --- | --- |
| Named profile catalog and explicit confirmation | API, UI payload, immutable Job/Project binding | Implemented and regression-tested |
| General/E-Commerce isolation | Profile fields inert and selector hidden outside Photography | Implemented and regression-tested |
| Three materially different scenes | Typed identity evidence activates in shoreline, forest, and architectural-studio prompts | Regression-tested |
| Native reference requirement | Provider emits high-fidelity truth layer; missing/unsupported paths block | Regression-tested |
| Review/retry ownership | Shared capability owns four issue codes, one bounded retry, no face-local repair | Regression-tested |
| Live provider quality gate | Same individual preserved in real outputs across multiple scenes | Pending Gate C/D; not implied by unit tests |

## 5. Handoff To Photography P5

Before activating `photographer_template`, the Photography branch must
fetch/rebase mainline, use the catalog endpoint rather than a local profile
list, send `user_explicit_ui` only after confirmation, and upload same-
individual non-human references with `nonhuman_identity_reference`.

It must not implement a local identity-preservation prompt, a local image
comparison metric, a provider shortcut, or a separate retry path. Live provider
quality evidence remains a production gate and is independent of this contract
implementation.
