# Doc117 V3 Real Reference Provider Capability and Failure Closure

Status: post-Doc113/Doc114 corrective foundation authority and gated
acceptance contract. Activation closure is implemented on the mainline
integration candidate `e458d23`; this document retains the regression contract
and must not introduce a second activation mechanism.

Scope: V3 normalized evidence, capability activation, reference policy/Product
Identity, Provider materialization, Product API/Project Mode failure projection,
and cross-template real-chain acceptance. This document adds no renderer,
template, Scenario Pack, or child-specific capability.

## 1. Purpose and authority

Doc113 establishes one enforced execution envelope and Doc114 establishes
source-proportionate garment truth plus shared Human Realism. A controlled
real-reference regression exposed two execution risks that must be closed at
the shared boundary:

1. a remote Brain may recognize a visible person in its task profile while its
   returned activation intent omits shared `human_realism`; and
2. an actual image-edit Provider may reject a user-authorized reference image
   with an upstream 4xx before any pixels, review, or visual retry exist; and
3. a compliant, fully fictional school-age-child scene may be explicitly
   blocked by the configured Provider's policy before pixels exist.

Neither risk is an apparel-only concern. They affect a person wearing a product,
same-person reference work, a product-on-person lifestyle image, and any other
V3 task that requires a real reference input. The correct architecture is:

```text
normalized request/reference evidence
  -> locally authoritative capability activation and frozen envelope
  -> remote Brain creative direction only
  -> reference-input admission and one gateway-owned image-edit request
  -> shared Provider result or structured Provider failure
  -> shared pixel review/retry only when pixels exist
  -> append-only history and safe user-visible state
```

Doc117 extends Docs 93, 96, 100, 102, 113, and 114. It wins if an older
implementation lets remote creative prose weaken capability activation, turns a
required reference image into a text-only substitute, treats a reference-input
rejection as a visual failure, or hides it behind an opaque provider error.

It does not override Doc93's existing, narrowly classified direct-Provider
transport retry. For a gateway-owned operation, V3 still submits exactly one
outer request and leaves lane selection/failover to the gateway. This document
also does not recast an explicit Provider policy block as a visual failure or a
reason to substitute a young adult for a child.

Doc100 remains authoritative: GPT Image 2 is the sole production final-pixel
renderer. The configured gateway remains the sole owner of upstream routing and
failover.

## 2. Boundaries and non-goals

This document is shared-foundation work. It must not:

- create a child, kidswear, beauty, or product-on-child module, Provider route,
  prompt recipe, classifier, or fixed studio treatment;
- add E-Commerce delivery roles, General suites, Photography roles, or static
  camera/lighting/pose direction;
- infer age from garment size or persist biometric/age information;
- change a required reference image into a text-only prompt, a local redraw, or
  a different model after an upstream rejection;
- replay a generic upstream 4xx merely to evade gateway policy/capability
  decisions;
- make a duplicate paid image-edit call solely as a speculative preflight; or
- expose raw upstream errors, credentials, image paths, prompts, candidate IDs,
  or safety-policy internals on public result surfaces.

Template ownership remains unchanged:

```text
General / E-Commerce / Photography -> requested delivery intent and count
Reference policy + Product Identity -> reference channel and source truth
shared activation + Human Realism -> evidence-based human rendering quality
shared Provider -> one gateway-owned image operation
shared review/retry -> pixels that were actually produced
```

## 3. Corrected findings

### R1. Remote creative direction cannot own capability activation

For a real image request, the remote Brain owns natural-language creative
direction only. It does not own the final `VisualTaskProfile`,
`CapabilityActivationIntent`, or `CapabilityActivationPlan`.

The local normalizer builds those objects from the original request, declared
asset roles, reference policy, and trusted template policy before the envelope
is frozen. A compact remote response must not be asked to reproduce activation
bookkeeping. If a compatibility response nevertheless supplies task-profile or
activation fields, the runtime validates them as non-authoritative input and
rejects/ignores them when they weaken, contradict, or incompletely replace the
local result.

### R2. Resolved person evidence requires an auditable Human Realism decision

`visible_person`, `product_on_person_detected`, and explicit human-surface
evidence are normalized facts, not remote creative preferences. For a target
resolved as a non-stylized, non-excluded real-person target, the frozen
activation record must contain one of the following explicit outcomes:

```text
human_realism = active
human_realism = inactive_with_reason(nonhuman | explicitly_excluded | stylized_nonphotoreal)
human_realism = blocked_with_reason(invalid_or_conflicting_evidence)
```

Silence is invalid after relevance has been resolved. If the local evidence
resolves a real visible-person target and the enforced plan omits
`human_realism`, it must block before Provider materialization with
`human_realism_activation_inconsistent`. A visibly depicted person in an
explicitly stylized/non-photoreal target instead requires an explicit inactive
reason; it is not an activation defect.

`product_on_person_detected` is evidence of a depicted person only when the request or
trusted task profile actually requires a person wearing/holding/using the
product. A product reference by itself, a mannequin, or a small garment does
not imply a child or activate Human Realism.

`e458d23` implements this shared real-visible-person invariant in the enforced
planner. Doc117 requires the regression to remain covered across entry paths;
it does not authorize a new child, product, or template-specific activator.

### R3. Reference input needs an auditable projection, not a second lifecycle

A user-authorized reference with a required reference-truth channel is not
ordinary prompt context. It is a Provider input contract. Its execution facts
must be observable separately from creative planning and visual quality, but
must be derived from the existing asset plan, Provider attempt/result,
`provider_failure_retry`, and Job lifecycle. `ReferenceInputExecution` is an
append-only audit projection, never a second canonical Job status hierarchy:

```text
reference declared -> local admission result
                   -> materialization operation submitted
                   -> pixels received | classified failure
                   -> existing Job / delivery lifecycle
```

The first real image-edit request is the only valid semantic eligibility test
for the configured upstream. Local checks can establish file/transport
admission; they cannot claim that an upstream will accept the image content.

### R4. A reference rejection is not a failed visual review

When the upstream rejects a reference input before generating pixels, there is
no candidate and no image to review. Shared visual review/retry must not invent
a pixel verdict or issue a Human Realism/Product Identity repair. The Job is
blocked with append-only provenance. A text-only output, a new renderer, or a
different upstream line cannot count as a recovery for a required-reference
request.

## 4. Required contracts and invariants

### 4.1 Activation integrity record

The frozen `CapabilityExecutionEnvelope` must retain a compact,
non-biometric activation integrity projection:

```json
{
  "schema_version": "v3_activation_integrity_v1",
  "evidence_ids": ["..."],
  "visible_person": true,
  "product_on_person_detected": true,
  "human_realism_state": "active | inactive_with_reason | blocked_with_reason",
  "human_realism_reason_code": "visible_real_person | visible_human_surface | nonhuman | explicitly_excluded | stylized_nonphotoreal | conflicting_evidence",
  "activation_source": "local_normalized_evidence",
  "remote_brain_may_override": false
}
```

The public projection may expose only the state and safe reason code. Evidence
IDs and internal activation traces remain audit-only.

The canonical emitted field is `product_on_person_detected`, as required by
Doc113. A Product API boundary may read the older `product_on_person` spelling
only as a compatibility alias; new execution records and prompts must never
emit it.

Required invariants:

1. Remote Brain creative output cannot add, remove, or weaken an active
   capability after local evidence normalization.
2. A real-person request with positive evidence cannot reach Provider without
   a resolved Human Realism state.
3. An explicit nonhuman or no-person request must not activate Human Realism
   merely because a product has a handle, sleeve, mannequin, or human-like
   shape.
4. `human_realism` remains a shared capability; it never gains child-,
   apparel-, E-Commerce-, or Photography-specific ownership.

### 4.2 Reference input execution projection

For every Provider request with one or more reference inputs, persist an
append-only, safe `ReferenceInputExecution` projection. It is distinct from
reference policy and from a generated candidate, but links back to existing
canonical records rather than duplicating their lifecycle:

```json
{
  "schema_version": "v3_reference_input_execution_v1",
  "delivery_binding_id": "audit-only binding reference",
  "admission_outcome": "admitted | ineligible",
  "operation_outcome": "submitted | pixels_received | empty_provider_output | failed",
  "reference_requirement": "required | optional",
  "operation": "image_edit | image_generate",
  "reference_count": 1,
  "transport_profile": "safe_capability_identifier",
  "request_budget_owner": "gateway | direct_provider",
  "outer_request_count": 1,
  "failure_code": "reference_input_unsupported | reference_input_capability_mismatch | reference_input_rejected | image_edit_invalid_request_unattributed | provider_policy_blocked | provider_timeout | provider_unavailable | null",
  "failure_retry_link": "existing provider_failure_retry record or null",
  "safe_message": "string | null"
}
```

This record must not include provider credentials, raw response text, provider
paths, full prompt text, local filenames, or opaque provider policy details.
The audit-only record may retain a redacted status code, transport operation,
and correlation fingerprint sufficient to diagnose the route.

`outer_request_count` is scoped to one materialization operation/delivery
binding, not to an entire Job that can contain several independent requested
outputs. `pixels_received` is deliberately distinct from request submission:
an accepted transport with empty output is not a successful generated image.

Required invariants:

1. A required `provider_input_required` reference is materialized as a real
   image input or the Job is blocked. It cannot silently become prompt-only.
2. Local admission validates only safe technical facts: successful decode,
   decoded-media signature rather than declared MIME alone, dimensions, byte
   limits, derivative integrity, reference count, and configured transport
   capability. It never asserts content-policy eligibility.
3. A stable upstream 4xx maps to `reference_input_rejected` only when
   structured/redacted evidence actually attributes it to the reference input.
   A generic or garbled `400` is `image_edit_invalid_request_unattributed` and
   must not be presented as a reference rejection or policy decision.
4. An explicit, safely classified Provider safety/content-policy block maps to
   `provider_policy_blocked`; it is not retried, visually reviewed, or made to
   look supported by changing the requested age or scenario.
5. For gateway-owned failover, V3 sends exactly one outer image-edit request
   for this materialization operation. The gateway may manage upstream routing
   internally, but V3 must not multiply requests. A direct-Provider operation
   follows Doc93's existing, narrowly classified compatibility/transient retry
   rules and records every outer request; it must not be reimplemented around a
   gateway or used to bypass content policy.
6. No pixel means no `pass`, `warning`, `verified`, automatic delivery, or
   candidate-selection event.

The public reference-execution state is derived only when serializing Product
API/Project results; it is not persisted as another lifecycle source of truth:

| Audit projection / existing lifecycle | Public state |
| --- | --- |
| local ineligibility or unresolved required-input failure | `blocked` |
| attributed Provider rejection | `rejected` |
| explicit Provider policy block | `blocked` |
| Provider transport unavailable | `unavailable` |
| pixels received and normal delivery lifecycle continues | `ready` |

An ambiguous invalid request remains `blocked` with its safe code until the
existing retry/failure owner resolves it; it must not be falsely labeled
`rejected`.

## 5. Failure taxonomy and recovery discipline

| Condition | State / code | Owner | Required handling |
| --- | --- | --- | --- |
| Corrupt, over-limit, or unsupported local reference | `ineligible` / `reference_input_unsupported` | shared Provider admission | Block before upstream call; request a valid user replacement. |
| Transport declares no native edit/reference support | `blocked` / `reference_input_capability_mismatch` | Provider capability layer | Block; do not reduce required truth to text. |
| Structured failure attributes a stable upstream 4xx to the supplied reference | `failed` / `reference_input_rejected` | gateway + shared Provider projection | For a gateway-owned operation: one outer request, safe rejected state, no visual retry. |
| Generic/garbled image-edit 4xx cannot distinguish reference, prompt, parameter, or gateway cause | `failed` / `image_edit_invalid_request_unattributed` | shared Provider failure classifier | Do not assert reference rejection or policy. Only the existing Doc93 direct-Provider transient rule may issue its bounded fresh request; a gateway-owned operation makes no V3 outer replay. |
| Explicit Provider safety/content-policy refusal, with or without a reference | `failed` / `provider_policy_blocked` | gateway + shared Provider projection | No visual retry, no text-only substitution, no age/scenario substitution, and no claim of quality acceptance. Preserve safe blocked evidence and wait for supported-route/upstream confirmation. |
| Gateway/Provider timeout or unavailable route | `failed` / `provider_timeout` or `provider_unavailable` | gateway + shared Provider projection | Follow existing gateway-owned resilience policy; preserve bounded transport provenance. |
| Request submitted but provider returns no candidate bytes | `empty_provider_output` | shared Provider result classifier | Use the existing provider-failure owner; do not mark the request accepted or visually reviewed. |
| Candidate pixels exist but garment/person/scene contract fails | normal candidate/review state | Product Identity, Human Realism, template, or universal quality | Use existing shared bounded visual retry only for observed pixel issues. |
| Required reference was rejected and an optional unrelated output exists | `blocked` for required-reference deliverable | Product API/template delivery | Keep unrelated diagnostics append-only; do not certify or substitute them. |

The user-visible outcome for `reference_input_rejected` or
`provider_policy_blocked` must be plain and non-accusatory: the current image
route could not complete this requested image, so it was not created. It may
offer a valid replacement image or an explicitly selected supported route, but
must not advise cropping, obscuring, changing the depicted age, or otherwise
altering a request to bypass upstream controls.

## 6. Provider, review, and browser behavior

### Provider behavior

Provider materialization consumes only the Doc113 ledger plus the frozen
reference input record. It may prepare a size/format-compatible derivative
without changing declared source truth or using an unrecorded substitute.
Reference preparation records the derivative fingerprint and safe technical
facts; it does not claim identity/product fidelity or policy approval.

Doc93's already-authorized focused crop and minimum-dimension upscale remain
technical evidence-preserving preparation, not a content-policy workaround.
They apply before the operation and remain traceable to the same source. They
must not be suggested to a user, or invoked after a policy block, to evade an
upstream decision.

When a required reference is blocked or rejected, or a no-reference request is
explicitly Provider-policy blocked:

```text
no candidate asset
no post-generation visual inspection
no visual repair prompt
no selected output
one append-only classified Provider attempt
```

### Review and retry behavior

Shared review/retry begins only after actual candidate pixels exist. A reference
input rejection or Provider policy block is terminal for that materialization
attempt. Its repair is not a request to make the garment, face, hand, scene, or
depicted age more realistic or more likely to be admitted.

If pixels exist, Doc113/Doc114 ownership resumes unchanged: Product
Identity/reference policy repairs garment truth; Human Realism repairs observed
human defects; templates repair frozen delivery evidence; universal quality
repairs renderer/technical defects. A retry preserves valid reference input
lineage and cannot replace its source with a text-only equivalent.

### Product API, Project Mode, and browser projection

The user-facing Job/Project state must expose a safe terminal reference state:

```json
{
  "reference_execution_state": "ready | blocked | rejected | unavailable",
  "automatic_delivery_available": false,
  "manual_confirmation_required": true,
  "safe_reason_code": "reference_input_rejected | provider_policy_blocked | image_edit_invalid_request_unattributed"
}
```

The browser shows a blocked reference-grounded request rather than an empty
final-result card, selectable output, or a misleading generic generation
success. Retry-superseded candidates and Provider diagnostics remain folded
history; no public surface exposes raw errors or provider internals. Manual
confirmation records that a user has seen the blocked outcome; it cannot turn a
no-pixel attempt into a verified result, delivery, or quality pass.

## 7. Required implementation phases

### Phase 0 -- red regressions and data boundary freeze

Add/retain red regressions for remote Brain activation omission,
required-reference rejection, ambiguous 4xx attribution, explicit policy
block, safe public projection, and no-pixel review suppression. Freeze the
existing gateway-owned routing behavior and GPT Image 2 sole-renderer rule.

### Phase 1 -- activation integrity regression lock (implemented candidate)

`e458d23` computes/enforces the shared real-visible-person activation invariant
before Provider execution, even when the remote Brain omits the capability.
Keep its regression coverage across entry paths. Do not add a second local
activator, child detector, or template-specific merge path. Compatibility fields
from a compact Brain response remain non-authoritative and cannot weaken the
enforced plan.

### Phase 2 -- reference input admission and provenance

Create the derived `ReferenceInputExecution` projection at reference
materialization. Implement local technical admission, required/optional channel
semantics, decoded-media validation, safe derivative provenance, and
per-operation request accounting without adding a second Job lifecycle.

### Phase 3 -- classified Provider closure

Map known technical/capability/reference-input failures to the taxonomy above.
Sanitize upstream messages before persistence/public projection. Preserve
gateway-owned failover. Preserve Doc93's existing direct-Provider, narrowly
scoped compatibility/transient retry only where it already applies; do not add
generic SDK/HTTP retries around gateway-owned image edits.

### Phase 4 -- lifecycle and result-surface closure

Project the safe terminal reference state through Product API, Project Mode,
history/recovery, and browser results. Ensure blocked/rejected requests produce
neither delivery outputs nor misleading review certifications, and ensure an
explicit policy block cannot be manually certified as a visual pass.

### Phase 5 -- real-chain acceptance

Run the matrix below on the current mainline with actual remote Brain, GPT Image
2, configured gateway, and shared review. A fixture or mock proves a branch;
it does not prove Provider acceptance. A route policy block is evidence for the
failure contract only; it does not prove or disprove visual quality.

## 8. Mandatory verification matrix

| Case | Required result |
| --- | --- |
| General, real product reference, person wearing product | Local evidence freezes `human_realism`; remote creative direction cannot remove it; one image-edit request reaches real Provider. |
| E-Commerce, real product reference, apparel-on-person | Doc114 garment facts, active Human Realism, template-owned count, and reference input lineage coexist without a vertical shared recipe. |
| Photography, real portrait/reference image | Photography role contract remains isolated; reference execution state follows the same shared contract. |
| General, fully fictional, fully clothed school-age-child daily scene, no reference | It remains General, and active shared Human Realism is frozen. If the Provider explicitly policy-blocks it, record `provider_policy_blocked`; do not call it a quality pass/failure or substitute a young adult. |
| Remote Brain omits/malforms activation fields | For a real visible-person target, local activation survives; incompatible remote sections are rejected/audited; no weakened plan is frozen. Explicit stylized/non-photoreal targets retain their explicit inactive reason. |
| Non-person product with no human evidence | Human Realism remains inactive with a safe reason; reference input can still proceed. |
| Explicit no-person/nonhuman request | No false Human Realism activation from product wording or human-like parts. |
| Locally invalid required reference | Blocks before upstream call with safe reason; no text-only fallback. |
| Structured real upstream reference 4xx | One outer gateway request; `reference_input_rejected`; no candidate, review, retry, or final delivery. |
| Generic image-edit 400 | `image_edit_invalid_request_unattributed`, never a fabricated reference/policy reason. A direct Provider may follow the existing Doc93 bounded rule; a gateway-owned operation has no V3 outer replay. |
| Input-fidelity-only compatibility rejection | Use only the existing documented technical negotiation, preserve the same reference lineage, and record each direct outer request. It must not become a content bypass. |
| Explicit Provider policy block | `provider_policy_blocked`; no candidate, review, retry, delivery, young-adult substitution, or manual visual certification. |
| Provider returns pixels after an admitted reference | Shared vision/hybrid review and existing bounded visual retry run normally; final delivery contains only the winner. |
| Refresh/recovery after rejection | Same safe blocked state; no reconstructed success card or selectable empty output. |

At least one controlled acceptance must use a user-authorized, non-brand-claiming
real product reference and document whether it is accepted or rejected by the
configured route. A rejected sample proves the failure path only; it does not
prove product identity, a production Gate, or visual quality.

The shared regression suite must also include materially different non-vertical
fixtures: a non-person product, a real-person portrait/lifestyle request, and a
product-on-person request. The fictional school-age-child fixture is a
cross-domain safety/quality regression only; it may never produce a named
runtime branch, prompt fragment, classifier, or delivery map.

## 9. Relationship to Doc114 and release gates

Doc114 remains the authority for garment truth and generic Human Realism
quality. Its real product-reference gate cannot be marked passed merely because
a text-to-image run, upload, local derivative, or mock fixture succeeds.

A Doc114 real-chain acceptance requires all of the following for its selected
sample:

```text
local reference admission recorded
remote Brain used without creative fallback
one gateway-owned required-reference image-edit request submitted
actual GPT Image 2 candidate pixels returned
shared vision_model or hybrid review reaches a terminal verified conclusion
bounded retry, if any, preserves reference lineage
only final delivery is user-visible
```

If the current configured route rejects the reference, report the Doc117
failure state and keep the Doc114 production acceptance gate open. Do not
mistake a correctly blocked failure for a visual-quality pass.

### 9.1 Current controlled school-age-child Gate status

The controlled General request `job_3863e5d5f2` was a no-reference, fully
fictional, fully clothed school-age-child daily scene. It reached remote Brain
successfully without fallback, and the enforced plan froze `human_realism` as
required. The real GPT Image 2 request then received an explicit non-retryable
Provider 400 identified by the mainline acceptance environment as an upstream
content-safety/not-applicable generation decision. No candidate pixels,
visual-review record, retry, or delivery exist.

Its Gate is therefore **Provider-policy blocked**, not passed and not failed on
children's visual quality. It also does not prove that Human Realism or garment
truth is visually effective. Do not transform the request into a young-adult
sample, text-only fallback, alternate renderer, or a private children-specific
rule in order to obtain a green result.

Until the upstream explicitly supports this compliant scenario and the
mainline reruns it, permitted work is limited to offline/contract checks:

1. confirm General routing, remote-Brain/no-fallback provenance, and frozen
   shared Human Realism activation;
2. confirm the classified no-pixel state suppresses review, visual retry,
   delivery, and manual certification;
3. confirm the public blocked projection survives refresh/recovery without
   exposing upstream detail; and
4. keep the real-reference Doc114 Gate independently open. A no-reference
   child policy block cannot replace its authorized-product-reference evidence.

## 10. Definition of done

Doc117 is complete only when:

1. local evidence is authoritative over remote creative output for activation;
2. every relevant real-person plan has an explicit Human Realism decision;
3. required reference inputs have auditable admission, materialization, and
   terminal-failure projections;
4. a reference-image rejection cannot silently fall back, visually retry, or
   appear as a delivery;
5. gateway-owned image-edit routing remains bounded and observable;
6. General, E-Commerce, and Photography share the same reference-input
   contract without inheriting each other's deliverable logic; and
7. the mandatory real-chain and failure-path evidence is recorded on the
   current mainline; and
8. a Provider-policy-blocked child request remains a correctly classified open
   Gate until a compliant real-pixel rerun exists, never a surrogate visual
   pass or a reason to add vertical special cases.
