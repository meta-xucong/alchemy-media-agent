# 97 V3 Subject Continuity Asset Pack And Adaptive Reference Routing Spec

## 1. Purpose

Doc97 improves long-running subject consistency without replacing the V3
foundation, Project Mode, Central Brain, Scenario Packs, or the existing Visual
Capability Cluster.

The implementation target is:

```text
turn uploaded and explicitly selected references into an auditable subject pack
keep the user's selected image operationally first while retaining uploaded truth
choose reference evidence that fits the requested camera view
prevent weak generated images from silently becoming long-term truth
route identity repair according to provider capability instead of assuming every
image-edit provider can repair a face without replacing it
```

The first active consumer is portrait identity in General Template. The same
contracts support product and structured-subject continuity. Specialized
Photography and E-Commerce templates may add their own deliverable policy later,
but they must reuse these shared contracts instead of duplicating them.

## 2. Authority And Compatibility

Doc97 extends:

```text
Doc58 selected-output strong reference loop
Doc73 first-output identity anchor
Doc75 identity hero and strict review
Doc83 reviewed delivery presentation
Doc85 image-to-image truth
Doc86 bone-structure identity
Doc87 identity/style separation
Doc90 explicit user reference priority
Doc93 reference-channel ownership
Doc94 universal shared-runtime governance
Doc95 complementary identity evidence and best-result selection
Doc96 objective identity metric and bounded repair
```

Doc97 is authoritative when older text implies that:

```text
all active references should be sent in insertion order
the latest selected generated image may replace uploaded root truth
one reference image is equally suitable for every target camera view
every generated image may automatically enrich long-term identity memory
every provider that accepts a mask is identity-native and safe for face repair
```

Compatible rules:

```text
explicit user selection is the operational master for the next generation
uploaded truth remains the immutable root guard and is still sent when available
generated references are append-only support, never silent root replacement
reference selection is bounded and view-aware
generic local face repair is capability-gated
the existing reviewed best-result selector remains final delivery authority
```

Doc97 does not change API namespaces, Project/Job ownership, template activation,
account isolation, uploaded files, user-visible Advanced controls, requested image
count, or V1/V2/Lab runtime boundaries.

## 3. Architecture Placement

No new top-level framework is allowed.

```text
Central Brain
  decides subject type, current request, template, and explicit user controls
  does not calculate face metrics or rank image files

Visual Capability Cluster
  Subject Continuity Asset Pack        new child module
  Adaptive Reference Retriever         new child module
  Identity Drift Guard                 new child module
  Identity Repair Strategy Router      new child module
  existing identity/reference/review modules remain unchanged

Generation Router
  consumes the adaptive reference plan
  preserves selected-master and uploaded-root ordering
  records applied source order

Vision Review And Product API
  continue objective scoring and reviewed best-result delivery
  consume repair strategy before attempting local identity repair
```

All four additions are constructor-injected child components of
`VisualCapabilityClusterModule`. They may be replaced in tests or future
deployments. They do not register as independent Central Brain agents.

## 4. Runtime Contracts

### 4.1 Subject Continuity Evidence

```python
class SubjectContinuityEvidence:
    evidence_id: str
    source_id: str
    source_type: str
    asset_id: str | None
    output_id: str | None
    file_path: str | None
    subject_type: str
    evidence_role: str
    authority: str
    view_hint: str
    framing_hint: str
    face_detection_confidence: float | None
    identity_score: float | None
    geometry_score: float | None
    trust_score: float
    provider_eligible: bool
    quarantine_reason: str | None
    user_selected: bool
```

`authority` values:

```text
user_selected_master
uploaded_root_truth
reviewed_generated_support
unreviewed_generated_support
style_or_context_reference
```

No face embedding is stored in this contract.

### 4.2 Subject Continuity Asset Package

```python
class SubjectContinuityAssetPackage:
    package_id: str
    project_id: str | None
    job_id: str | None
    applies: bool
    subject_type: str
    evidence: list[SubjectContinuityEvidence]
    user_selected_master_ids: list[str]
    uploaded_root_truth_ids: list[str]
    accepted_generated_support_ids: list[str]
    quarantined_ids: list[str]
    provider_candidate_ids: list[str]
    root_truth_preserved: bool
    embeddings_persisted: bool
```

`embeddings_persisted` must always be `False`.

### 4.3 Adaptive Reference Selection Plan

```python
class AdaptiveReferenceSelectionPlan:
    plan_id: str
    applies: bool
    target_view: str
    target_framing: str
    ordered_source_ids: list[str]
    required_source_ids: list[str]
    optional_source_ids: list[str]
    excluded_source_ids: list[str]
    max_identity_sources: int
    preserve_uploaded_root: bool
```

Default maximum identity sources is `3`. Each source may produce Doc95 feature
and geometry derivatives, keeping provider evidence bounded.

### 4.4 Identity Drift Guard

```python
class IdentityDriftGuardPlan:
    plan_id: str
    applies: bool
    status: str
    root_truth_ids: list[str]
    accepted_generated_ids: list[str]
    warning_generated_ids: list[str]
    quarantined_generated_ids: list[str]
    user_override_ids: list[str]
    minimum_identity_score: float
    commercial_identity_target: float
    root_comparison_required: bool
```

Default thresholds reuse Doc96:

```text
below 0.72: quarantine unless explicitly selected by the user
0.72 to below 0.82: auxiliary support only
0.82 or above: reviewed generated support
```

An explicit user selection remains eligible even below the threshold, but it is
recorded as `user_override`; uploaded truth remains in the provider set as the
root guard. This honors user intent without silently discarding the original
identity.

### 4.5 Identity Repair Strategy

```python
class IdentityRepairStrategyPlan:
    plan_id: str
    applies: bool
    strategy: str
    allow_face_local_repair: bool
    identity_native_provider_required: bool  # legacy field, always false in production
    provider_capability_key: str
    fallback_strategy: str
```

Strategies:

```text
regenerate_from_ranked_identity_pack
hold_best_reviewed_result
not_applicable
```

Production always uses the ranked identity pack for a bounded GPT Image 2 full
rerender and keeps the best reviewed result. Stale sidecar capability metadata,
generic mask support, and experimental local-repair flags cannot unlock another
final-pixel renderer. Doc100 is authoritative for this corrected boundary.

## 5. Evidence Authority And Promotion

### 5.1 User-Selected Master

When the user explicitly selects a generated image as a strong reference:

```text
it becomes the first operational reference for the next generation
it may guide current pose-ready appearance and the preferred rendition
it does not erase uploaded root truth
it is still compared with root truth during review
```

This implements the accepted user rule: explicit selection wins over automatic
hero selection.

### 5.2 Uploaded Root Truth

Uploaded person or product identity references are immutable root truth:

```text
at least one root source remains in every strict continuation request
generated support cannot replace it
root truth controls identity/product invariants only
Doc93 still prevents source scene, hair, wardrobe, light, and style leakage
```

### 5.3 Generated Support

Generated images enter the package only through one of these paths:

```text
explicit user selection
review evidence at or above the commercial identity threshold
review evidence in warning range as auxiliary support
```

Unselected candidates do not enter positive context. Failed, superseded, or
rejected outputs remain historical records and are excluded from provider input.

## 6. View-Aware Retrieval

Supported universal view hints:

```text
front
left_three_quarter
right_three_quarter
left_profile
right_profile
unknown
```

Supported framing hints:

```text
face_closeup
head_shoulders
half_body
full_body
environmental
unknown
```

View and framing may come from:

1. explicit reference metadata;
2. ephemeral YuNet landmarks and face-box ratio;
3. current prompt and role instruction;
4. `unknown` fallback.

Reference order:

```text
1. explicit user-selected master matching the target view, if present
2. explicit user-selected master with another view
3. uploaded root truth matching the target view
4. best uploaded root truth
5. reviewed generated support matching the target view
6. other reviewed support
```

At least one uploaded root is retained whenever one exists, even when an
explicitly selected master is first.

## 7. Provider Consumption

The Generation Router must:

```text
read adaptive_reference_selection_plan from the Visual Capability Cluster
reorder source assets before content/role deduplication
exclude quarantined identity sources
bound identity sources to the plan maximum
keep non-identity references subject to the existing six-source transport cap
record requested order, applied order, excluded IDs, target view, and target framing
continue Doc95 derivative creation and Doc96 input_fidelity negotiation
```

The user prompt remains lossless. The adaptive plan changes evidence selection,
not the user's written request.

## 8. Repair Routing

Current live evidence showed that a generic masked face edit could improve
commercial finish while reducing identity from approximately `0.79` to `0.63`.
Therefore:

```text
provider accepts mask only                     -> not sufficient
provider explicitly supports identity-native edit -> local repair allowed
no identity-native provider                    -> ranked full retry or hold best
repair result below delivery gates             -> never replaces prior result
```

The existing Doc96 local-repair implementation remains available behind the
capability gate. This is a routing correction, not removal of the extension
point.

## 9. Privacy And Persistence

Allowed to persist:

```text
asset/output IDs
source authority
view/framing labels
face-box and detector confidence
review scores already present in output review
selection and quarantine decisions
```

Forbidden to persist:

```text
face embeddings
raw recognition vectors
derived biometric templates
provider-private feature tensors
```

The existing Doc96 ephemeral metric rule remains unchanged.

## 10. Failure And Degradation

```text
detector unavailable:
  use metadata and prompt-only view inference

no uploaded root:
  use explicit selected master, mark root_truth_preserved=false

no score on user-selected output:
  permit as unreviewed user-selected support and retain root guard

all generated support quarantined:
  send uploaded root only

provider does not consume adaptive plan:
  existing reference flow remains valid; emit degraded audit state

identity-native repair unavailable:
  skip generic face-local repair, preserve reviewed best result
```

No degradation may block ordinary text-to-image generation.

## 11. Implementation Order

1. Add Doc97 contracts to `visual_cluster/contracts.py`.
2. Add independently injectable child components:
   - `identity_drift_guard.py`
   - `subject_asset_memory.py`
   - `adaptive_reference.py`
   - `identity_repair_strategy.py`
3. Add non-persistent reference profiling to `identity_metric.py`.
4. Build packages inside `VisualCapabilityClusterModule` after strong bindings
   and subject type are resolved.
5. Reorder strong bindings before Doc93 policy and downstream identity plans.
6. Expose all packages through cluster facts, metadata, and constraints.
7. Make the Generation Router apply source ordering and exclusions.
8. Make Product API local repair obey the strategy plan when present.
9. Add focused tests, then run full V3, root, and frontend/API regressions.

## 12. Acceptance Tests

### 12.1 Architecture

- All new runtime classes live under the existing Visual Capability Cluster.
- Central Brain contains no detector, metric, source-ranking, or repair-provider
  branch.
- V1/V2 imports remain forbidden.
- Components are constructor-injectable.

### 12.2 Reference Priority

- Explicitly selected generated image is first operational reference.
- Uploaded root truth is also retained.
- With no explicit selection, uploaded root is first.
- Quarantined generated support is absent from provider inputs.
- Non-identity style/scene references remain available.

### 12.3 View Awareness

- A target profile request prefers profile evidence when available.
- A frontal request prefers frontal evidence.
- Unknown view falls back deterministically.
- Detector/model absence does not fail generation.

### 12.4 Drift

- Generated support below `0.72` is quarantined unless explicitly selected.
- Explicit selection produces a visible user-override audit decision.
- Generated support at or above `0.82` may be promoted.
- Root comparison remains required.

### 12.5 Repair

- Generic providers do not run face-local repair when the strategy plan forbids it.
- An explicit identity-native capability enables one bounded repair.
- Existing reviewed best-result protection still rejects a worse repair.

### 12.6 Regression

- Full V3 tests pass.
- Root tests pass.
- Frontend/API shell tests pass.
- Python and JavaScript syntax checks pass.
- Existing project data and APIs remain compatible.

## 13. Definition Of Done

Doc97 is complete when:

```text
one auditable subject asset package exists per applicable job
provider input is selected from that package rather than insertion order alone
explicit user selection and uploaded root truth coexist correctly
weak generated outputs cannot silently become long-term truth
generic masked face repair is no longer assumed identity-safe
all delivery results remain governed by reviewed best-result selection
```

Doc97 improves consistency with the existing provider. It does not claim that a
generic image provider has become an identity-specialized generator. A future
identity-native provider may plug into the repair/provider capability contract
without changing Project Mode or Central Brain.

Doc100 supersedes the former production sidecar extension. Doc97 remains
authoritative for subject evidence, ordering, root-truth retention, and drift
quarantine. Final correction is performed only by GPT Image 2 through bounded
rerender; Doc98/99 are isolated research references.
