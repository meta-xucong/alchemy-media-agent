# Doc117 V3 Real Reference Provider Capability and Failure Closure

Status: post-Doc113/Doc114 corrective foundation authority.

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
   with an upstream 4xx before any pixels, review, or visual retry exist.

Neither risk is an apparel-only concern. They affect a person wearing a product,
same-person reference work, a product-on-person lifestyle image, and any other
V3 task that requires a real reference input. The correct architecture is:

```text
normalized request/reference evidence
  -> locally authoritative capability activation and frozen envelope
  -> remote Brain creative direction only
  -> reference-input admission and one gateway-owned image-edit request
  -> shared Provider result or structured reference failure
  -> shared pixel review/retry only when pixels exist
  -> append-only history and safe user-visible state
```

Doc117 extends Docs 93, 96, 100, 102, 113, and 114. It wins if an older
implementation lets remote creative prose weaken capability activation, turns a
required reference image into a text-only substitute, treats a reference-input
rejection as a visual failure, or hides it behind an opaque provider error.

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

### R2. Positive person evidence requires an auditable Human Realism decision

`visible_person`, `product_on_person`, and explicit human-surface evidence are
normalized facts, not remote creative preferences. For a non-stylized,
non-excluded real-person target, the frozen activation record must contain one
of the following explicit outcomes:

```text
human_realism = active
human_realism = inactive_with_reason(nonhuman | explicitly_excluded | stylized_nonphotoreal)
human_realism = blocked_with_reason(invalid_or_conflicting_evidence)
```

Silence is invalid. A task profile that contains a positive `visible_person`
fact while the enforced plan omits `human_realism` must block before Provider
materialization with `human_realism_activation_inconsistent`.

`product_on_person` is evidence of a depicted person only when the request or
trusted task profile actually requires a person wearing/holding/using the
product. A product reference by itself, a mannequin, or a small garment does
not imply a child or activate Human Realism.

### R3. Reference input has its own execution state

A user-authorized reference with a required reference-truth channel is not
ordinary prompt context. It is a Provider input contract. Its lifecycle must be
observable separately from creative planning and visual quality:

```text
declared -> locally_admissible | locally_ineligible
         -> provider_pending
         -> provider_accepted | provider_rejected | provider_unavailable
         -> pixels_available | blocked
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
  "product_on_person": true,
  "human_realism_state": "active | inactive_with_reason | blocked_with_reason",
  "human_realism_reason_code": "visible_real_person | visible_human_surface | nonhuman | explicitly_excluded | stylized_nonphotoreal | conflicting_evidence",
  "activation_source": "local_normalized_evidence",
  "remote_brain_may_override": false
}
```

The public projection may expose only the state and safe reason code. Evidence
IDs and internal activation traces remain audit-only.

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

### 4.2 Reference input execution record

For every Provider request with one or more reference inputs, persist an
append-only, safe `ReferenceInputExecution` record. It is distinct from the
reference policy and from a generated candidate:

```json
{
  "schema_version": "v3_reference_input_execution_v1",
  "state": "locally_admissible | locally_ineligible | provider_pending | provider_accepted | provider_rejected | provider_unavailable | blocked",
  "reference_requirement": "required | optional",
  "operation": "image_edit | image_generate",
  "reference_count": 1,
  "transport_profile": "safe_capability_identifier",
  "gateway_owned_failover": true,
  "outer_request_count": 1,
  "failure_code": "reference_input_unsupported | reference_input_capability_mismatch | reference_input_rejected | provider_timeout | provider_unavailable | null",
  "retry_eligible": false,
  "safe_message": "string | null"
}
```

This record must not include provider credentials, raw response text, provider
paths, full prompt text, local filenames, or opaque provider policy details.
The audit-only record may retain a redacted status code, transport operation,
and correlation fingerprint sufficient to diagnose the route.

Required invariants:

1. A required `provider_input_required` reference is materialized as a real
   image input or the Job is blocked. It cannot silently become prompt-only.
2. Local admission validates only safe technical facts: decodability, declared
   MIME/format, dimensions, byte limits, derivative integrity, reference count,
   and configured transport capability. It never asserts content-policy
   eligibility.
3. `provider_accepted` is recorded only when the configured Provider accepted
   the request and returned candidate pixels. A successful upload or a valid
   local derivative is not provider acceptance.
4. A stable upstream 4xx attributed to the reference input maps to
   `reference_input_rejected`; it is not sent to the visual retry loop.
5. Gateway-owned failover means V3 sends one outer image-edit request. The
   gateway may manage upstream routing internally, but V3 must not multiply
   requests. The existing single recorded input-fidelity compatibility replay
   remains allowed only when the gateway explicitly rejects that optional
   parameter, not the image reference itself.
6. No pixel means no `pass`, `warning`, `verified`, automatic delivery, or
   candidate-selection event.

## 5. Failure taxonomy and recovery discipline

| Condition | State / code | Owner | Required handling |
| --- | --- | --- | --- |
| Corrupt, over-limit, or unsupported local reference | `locally_ineligible` / `reference_input_unsupported` | shared Provider admission | Block before upstream call; request a valid user replacement. |
| Transport declares no native edit/reference support | `blocked` / `reference_input_capability_mismatch` | Provider capability layer | Block; do not reduce required truth to text. |
| Upstream rejects the supplied reference with a stable 4xx | `provider_rejected` / `reference_input_rejected` | gateway + shared Provider projection | One outer request only; expose safe failure state; no visual retry. |
| Gateway/Provider timeout or unavailable route | `provider_unavailable` / `provider_timeout` or `provider_unavailable` | gateway + shared Provider projection | Follow existing gateway-owned resilience policy; preserve bounded transport provenance. |
| Candidate pixels exist but garment/person/scene contract fails | normal candidate/review state | Product Identity, Human Realism, template, or universal quality | Use existing shared bounded visual retry only for observed pixel issues. |
| Required reference was rejected and an optional unrelated output exists | `blocked` for required-reference deliverable | Product API/template delivery | Keep unrelated diagnostics append-only; do not certify or substitute them. |

The user-visible outcome for `reference_input_rejected` must be plain and
non-accusatory: the current image route could not accept this reference for
generation, so the requested reference-grounded image was not created. It may
offer a replacement-image or explicitly selected supported-route choice, but
must not advise cropping, obscuring, or otherwise altering an image to bypass
upstream controls.

## 6. Provider, review, and browser behavior

### Provider behavior

Provider materialization consumes only the Doc113 ledger plus the frozen
reference input record. It may prepare a size/format-compatible derivative
without changing declared source truth or using an unrecorded substitute.
Reference preparation records the derivative fingerprint and safe technical
facts; it does not claim identity/product fidelity or policy approval.

When a required reference is blocked or rejected:

```text
no candidate asset
no post-generation visual inspection
no visual repair prompt
no selected output
one append-only blocked Provider attempt
```

### Review and retry behavior

Shared review/retry begins only after actual candidate pixels exist. A reference
input rejection is terminal for that required-reference attempt. Its repair is
not a request to make the garment, face, hand, or scene more realistic.

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
  "manual_confirmation_required": false,
  "safe_reason_code": "reference_input_rejected"
}
```

The browser shows a blocked reference-grounded request rather than an empty
final-result card, selectable output, or a misleading generic generation
success. Retry-superseded candidates and Provider diagnostics remain folded
history; no public surface exposes raw errors or provider internals.

## 7. Required implementation phases

### Phase 0 -- red regressions and data boundary freeze

Add failing tests for remote Brain activation omission, required-reference
rejection, safe public projection, and no-pixel review suppression. Freeze the
existing gateway-owned routing behavior and GPT Image 2 sole-renderer rule.

### Phase 1 -- activation integrity closure

Compute local normalized person/human-surface evidence before remote creative
merge. Persist the activation integrity record with the frozen envelope. For
real-image compact Brain contracts, omit capability/task-profile fields from the
remote schema; reject compatibility fields that conflict with local evidence.
Block inconsistent plans before Provider execution.

### Phase 2 -- reference input admission and provenance

Create `ReferenceInputExecution` at reference materialization. Implement local
technical admission, required/optional channel semantics, transport capability
projection, safe derivative provenance, and one outer-request accounting.

### Phase 3 -- classified Provider closure

Map known technical/capability/reference-input failures to the taxonomy above.
Sanitize upstream messages before persistence/public projection. Preserve
gateway-owned failover and the existing narrowly-scoped input-fidelity
negotiation; do not add generic SDK/HTTP retries around image edits.

### Phase 4 -- lifecycle and result-surface closure

Project the safe terminal reference state through Product API, Project Mode,
history/recovery, and browser results. Ensure blocked/rejected requests produce
neither delivery outputs nor misleading review certifications.

### Phase 5 -- real-chain acceptance

Run the matrix below on the current mainline with actual remote Brain, GPT Image
2, configured gateway, and shared review. A fixture or mock proves a branch;
it does not prove Provider acceptance.

## 8. Mandatory verification matrix

| Case | Required result |
| --- | --- |
| General, real product reference, person wearing product | Local evidence freezes `human_realism`; remote creative direction cannot remove it; one image-edit request reaches real Provider. |
| E-Commerce, real product reference, apparel-on-person | Doc114 garment facts, active Human Realism, template-owned count, and reference input lineage coexist without a vertical shared recipe. |
| Photography, real portrait/reference image | Photography role contract remains isolated; reference execution state follows the same shared contract. |
| Remote Brain omits/malforms activation fields | Local activation survives; incompatible remote sections are rejected/audited; no weakened plan is frozen. |
| Non-person product with no human evidence | Human Realism remains inactive with a safe reason; reference input can still proceed. |
| Explicit no-person/nonhuman request | No false Human Realism activation from product wording or human-like parts. |
| Locally invalid required reference | Blocks before upstream call with safe reason; no text-only fallback. |
| Real upstream reference 4xx | One outer gateway request; `reference_input_rejected`; no candidate, review, retry, or final delivery. |
| Input-fidelity-only compatibility 4xx | At most one recorded parameter-negotiation replay; same reference lineage; no generic replay. |
| Provider returns pixels after accepted reference | Shared vision/hybrid review and existing bounded visual retry run normally; final delivery contains only the winner. |
| Refresh/recovery after rejection | Same safe blocked state; no reconstructed success card or selectable empty output. |

At least one controlled acceptance must use a user-authorized, non-brand-claiming
real product reference and document whether it is accepted or rejected by the
configured route. A rejected sample proves the failure path only; it does not
prove product identity, a production Gate, or visual quality.

## 9. Relationship to Doc114 and release gates

Doc114 remains the authority for garment truth and generic Human Realism
quality. Its real product-reference gate cannot be marked passed merely because
a text-to-image run, upload, local derivative, or mock fixture succeeds.

A Doc114 real-chain acceptance requires all of the following for its selected
sample:

```text
local reference admission recorded
remote Brain used without creative fallback
one gateway-owned required-reference image-edit request accepted
actual GPT Image 2 candidate pixels returned
shared vision_model or hybrid review reaches a terminal verified conclusion
bounded retry, if any, preserves reference lineage
only final delivery is user-visible
```

If the current configured route rejects the reference, report the Doc117
failure state and keep the Doc114 production acceptance gate open. Do not
mistake a correctly blocked failure for a visual-quality pass.

## 10. Definition of done

Doc117 is complete only when:

1. local evidence is authoritative over remote creative output for activation;
2. every relevant real-person plan has an explicit Human Realism decision;
3. required reference inputs have auditable admission, request, and terminal
   states;
4. a reference-image rejection cannot silently fall back, visually retry, or
   appear as a delivery;
5. gateway-owned image-edit routing remains bounded and observable;
6. General, E-Commerce, and Photography share the same reference-input
   contract without inheriting each other's deliverable logic; and
7. the mandatory real-chain and failure-path evidence is recorded on the
   current mainline.
