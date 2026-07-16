# Professional Mode Asset Channel Authority And Reference Admission

## Independent Backend Specification

This is an unnumbered Professional Mode companion specification. It extends
the Visual Asset Library / People Asset document set without rewriting any
existing numbered V3 contract. It is a backend-first contract: no frontend
implementation is authorized by this document until the backend gates and
tests are complete.

The purpose is to make Professional Mode largely invisible during normal use:
the user explicitly chooses Professional Mode and a visual asset, while the
backend automatically decides which parts of every other reference are
admissible. A visual asset owns only its declared visual channels. It does not
replace General, E-Commerce, Photography, or future Video scene semantics.

## 1. Product Decision

Professional Mode is an asset-authority overlay on the existing V3 scenario
modules, not a second template system:

```text
explicit Professional Mode
  -> selected Visual Asset binding(s)
  -> existing General / E-Commerce / Photography scenario planning
  -> Remote Brain semantic interpretation and canonical prompt
  -> asset-channel authority and reference admission gate
  -> existing Provider / shared review / bounded retry / final delivery
```

The ordinary user surface exposes only:

```text
ordinary mode / Professional Mode
selected Visual Asset
```

The user does not manually manage channel IDs, evidence hashes, Provider
inputs, Brain fields, biometric data, or internal scores. Ambiguous or unsafe
conflicts surface as a plain-language blocked state with a safe next action;
they must not be silently guessed or silently dropped.

## 2. Authority And Compatibility

The authority order for a channel is:

```text
active selected Visual Asset claim for that channel
  > explicit prompt-owned transformation that preserves the asset identity
  > explicitly admitted non-owned reference channel
  > generic visual defaults
```

An active Visual Asset is authoritative only for its `owned_channels`. It does
not lock channels it does not claim.

The first People Asset / Face Identity module owns the existing face identity
channels:

```text
face_geometry
face_feature_relationships
same_person_continuity
```

For compatibility, the existing Face Identity contract remains the source of
the first two channel names. A future authority adapter may recognize a
semantic `face_identity` alias, but it must normalize it to the same protected
identity set rather than add a second identity system.

The first module does not own:

```text
hair, makeup, wardrobe, pose, lighting, scene, composition, style,
product, object, logo, or brand channels
```

Those channels remain prompt-owned, scenario-owned, or explicitly owned by a
future approved asset module.

This specification does not change:

```text
Standard Mode behavior or request semantics
General Template neutrality
E-Commerce role/deliverable semantics
Photography role/profile semantics
Central Brain ownership of semantic judgment and creative direction
GPT Image 2 Provider ownership of pixel rendering
shared review/retry/final-delivery contracts
```

## 3. Visual Asset Channel Claim

Every future Visual Asset module must expose a typed, project-scoped claim:

```text
AssetChannelClaim:
  project_id
  asset_type
  asset_id
  asset_version_id
  owned_channels[]
  evidence_ids[]
  active=true
```

The claim is an authority statement and evidence binding, not a prompt body.
It must not contain scenario fields such as slot, marketplace, platform,
A+, photographer role, or campaign packaging.

Contract rules:

1. Every claim belongs to the same project as the job.
2. An active claim must have a version and at least one approved evidence ID.
3. Owned channels must be unique within a claim.
4. Two active claims in the same job may not own the same canonical channel.
5. A missing, inactive, stale, or ambiguous claim blocks Professional Mode.
6. Raw filesystem paths, credentials, private prompts, and biometric vectors
   are never claim fields.

The current People Asset binding is adapted into one claim. Future Product,
Brand, Landscape, Body, or other modules add claims through the same adapter;
they do not modify the Face Identity module or create a second runtime.

## 4. Professional Asset Binding Set

The internal Professional Mode job context is a binding set:

```text
ProfessionalAssetBindingSet:
  mode = professional
  project_id
  job_id
  claims[]
  contract_version
```

The first implementation may contain exactly one People Asset claim. The
binding set is intentionally extensible so that a future job can explicitly
bind a People Asset and a Product Asset together, provided their owned channel
sets do not overlap.

The binding set is created after project/lifecycle validation and before the
frozen CapabilityActivationPlan. It is never inferred from a keyword, old
metadata, a filename, or a scenario name.

The public request remains beginner-friendly. The UI or session may carry an
explicit mode and selected asset ID, but the server resolves the project,
version, module, and evidence claim. The Brain receives sanitized typed asset
evidence, not private library internals or raw reference payloads.

## 5. Reference Channel Plan

Remote Brain and the shared reference/evidence preparation path produce a
typed internal plan for each user-supplied reference:

```text
ReferenceChannelPlan:
  project_id
  job_id
  reference_id
  declared_channels[]
  channel_evidence[]
  source_kind
```

Each `channel_evidence` item contains:

```text
channel
evidence_ids[]
representation:
  channel_isolated
  verified_non_person_derivative
  full_frame
```

The plan contains IDs and safe evidence descriptors only. It never contains a
raw path, provider-private prompt, credential, or unredacted uploaded payload.

`full_frame` is retained as a historical/source description, but it is not a
safe admitted representation for a non-owned channel when unwanted identity
pixels may be present. A channel is admitted only when the shared evidence
path proves a channel-specific representation or a verified derivative.

The local authority layer does not classify user language with a keyword
heuristic. Brain owns semantic interpretation; the authority layer validates
the resulting plan against active asset claims and shared evidence safety.

## 6. Reference Admission Algorithm

For each reference, the resolver performs these steps:

```text
1. Resolve active owned-channel claims for the Professional job.
2. Validate that every declared channel has a typed evidence representation.
3. For a channel owned by an active Visual Asset:
     suppress the competing reference channel;
     retain the asset's approved evidence as the only authority.
4. For a non-owned channel:
     admit it only when its representation is channel_isolated or
     verified_non_person_derivative.
5. Reject an unsafe full-frame representation rather than silently dropping it.
6. Return admitted IDs/channels, suppressed channels, and reason codes.
7. If any explicit reference cannot be safely admitted, block the Professional
   job before Provider materialization; do not fall back to Standard Mode.
```

The result is append-only internal evidence:

```text
ReferenceAdmissionDecision:
  reference_id
  status: admitted | partial | blocked
  admitted_channels[]
  suppressed_channels[]
  admitted_evidence_ids[]
  reason_codes[]
```

`partial` means an owned identity channel was intentionally suppressed while
one or more safe non-owned channels were admitted. It does not mean that an
unsafe channel was silently ignored.

## 7. Canonical Examples

### 7.1 Other person's photo plus a selected People Asset

```text
selected People Asset:
  face_geometry / face_feature_relationships / same_person_continuity

other-person photo:
  face identity -> suppressed
  clothing/pose/lighting -> admitted only with safe channel evidence
```

If the user explicitly asks to replace the person with the uploaded person,
the resolver blocks and offers only these safe choices:

```text
keep the selected People Asset and use the other image for non-identity cues
select a different People Asset
explicitly resubmit in Standard Mode
```

There is no automatic Professional-to-Standard fallback.

### 7.2 Cup or other object reference

With only a People Asset active, a verified cup reference may be admitted as an
object/product channel while the People Asset remains the sole face authority.
The person and cup may therefore appear in the same final scene without
mixing their identity sources.

### 7.3 Future Product Asset conflict

If a Product Asset owns `product_identity` and the user uploads another cup
claiming that same channel, the new reference cannot silently replace the
selected Product Asset. The job must either use the selected Product Asset or
ask the user to change the selected asset/mode.

### 7.4 Logo reference

Before a Brand Asset exists, an explicitly requested Logo reference may be
admitted through the existing object/mark evidence path. Once a Brand Asset is
selected and owns the relevant mark channel, it becomes authoritative under
the same conflict rule.

### 7.5 Composite image with a person and a cup

The system must not claim to ignore the person's pixels merely because the
Prompt mentions only the cup. It must use a verified non-person derivative or
channel-isolated evidence. If isolation cannot be proven, the reference
assignment is blocked with a safe explanation.

## 8. Prompt-Owned Transformations

Professional Mode does not freeze every visible property of a person. An
explicit current Prompt may request a same-person transformation such as:

```text
new age direction
new hair or makeup direction
new wardrobe
new pose
new lighting, scene, camera, mood, or composition
```

The transformation remains subject to shared Human Realism, safety, and
same-person review. A request for a materially different person identity is a
channel conflict and blocks until the asset or mode changes.

The authority layer must therefore distinguish:

```text
prompt-owned transformation of the selected identity
versus
replacement of the selected identity by another reference
```

This distinction is semantic Brain work followed by local contract
validation; it is not a local keyword classifier or a private prompt rewrite.

## 9. Evidence, Provider, Review, And History Parity

The same admitted evidence set must be used by Provider materialization and
shared pixel review:

```text
selected asset claims and versions
root/anchor evidence IDs and hashes
admitted non-owned reference evidence IDs
suppressed/conflicting channel decisions
canonical Brain prompt hash
```

The backend represents this parity with one immutable internal evidence
packet. Its `evidence_ids`, `provider_evidence_ids`, and
`reviewer_evidence_ids` must be identical. A packet cannot be created from a
blocked admission, and a frozen plan cannot pass when the evidence-packet
contract is missing or unsupported.

Retry is append-only. A retry may refine the Brain-owned canonical prompt only
through the existing shared retry contract; it may not re-admit a suppressed
identity channel or create a private face repair path.

Provenance may record safe IDs, hashes, contract versions, status, and reason
codes. It must not persist raw biometric vectors, secret values, private Prompt
bodies, or arbitrary filesystem paths.

## 10. Failure And Security Semantics

Professional Mode blocks before Provider when any of the following occurs:

```text
missing or inactive selected asset
stale asset version or overlapping active channel claims
missing root/anchor evidence
Brain reference-channel plan incomplete or invalid
unsafe full-frame reference cannot be isolated
reference conflicts with an owned channel and has no safe remaining channel
Provider and Reviewer evidence sets would differ
frozen capability plan lacks the asset/admission contract
```

The system must never:

```text
fall back to Standard Mode
send a competing person's full frame while claiming identity was ignored
silently discard an explicitly requested reference
infer a future asset module from a keyword
inject local Prompt prose or negative Prompt fragments
create a second Brain, Provider, review system, or image store
```

The public response should be plain-language and actionable. Internal reason
codes remain structured and auditable.

## 11. Backend Implementation Sequence

### A — Contract and red tests

Add the generic claim, binding-set, reference-plan, admission-decision, and
conflict contracts. Adapt the existing People Asset binding without changing
its public behavior. Prove Standard Mode remains untouched.

### B — Authority resolver

Implement deterministic validation of Brain/shared-evidence output:

```text
owned-channel suppression
safe non-owned admission
unsafe full-frame blocking
duplicate/overlap rejection
project/version binding checks
```

The resolver never writes creative Prompt prose.

### C — Runtime bridge

Require a successful admission result alongside the current Professional Mode
binding before capability-plan freeze. Preserve admitted IDs, suppressed
channels, hashes, and contract versions in internal planning provenance.

### D — Shared execution parity

Ensure Provider, Reviewer, retry, and final delivery consume the same resolved
evidence packet. No Professional-only pixel repair or reference loop may be
introduced.

### E — Real acceptance

Run real Provider and shared review acceptance through General, E-Commerce, and
Photography with:

```text
selected People Asset + another-person style reference
selected People Asset + cup/object reference
selected People Asset + Logo reference
conflicting identity request
unsafe composite reference
```

Keep production gates closed until the existing real-pixel and template gates
pass independently.

### F — Frontend only after backend closure

The frontend will expose only:

```text
ordinary mode / Professional Mode
selected Visual Asset
plain-language preparation or blocked status
```

It will not implement channel arbitration, identity filtering, Provider
selection, or local retry logic.

## 12. Required Tests

At minimum:

```text
Standard Mode creates no asset claims or admission records.
People Asset protects all current face identity channels.
Two active assets cannot claim the same channel in one job.
Other-person identity references are suppressed or blocked, never silently
treated as harmless full-frame style references.
Safe clothing/pose/lighting evidence can coexist with the selected face asset.
Cup/object and Logo references remain admissible when no conflicting asset is
selected.
Future Product/Brand claims take authority over the same channels.
Missing derivative or unsafe full-frame evidence blocks closed-loop execution.
Provider and Reviewer receive identical admitted evidence IDs and hashes.
Brain/provider secrets, raw paths, Prompt bodies, and biometric vectors do not
enter the public binding or provenance record.
General, E-Commerce, and Photography retain their existing role contracts.
No local keyword classifier, Standard fallback, second Provider, or private
review/retry path is introduced.
```

## 13. Non-Goals

This specification does not authorize:

```text
new UI implementation
product, brand, landscape, body, or video modules in this milestone
automatic asset selection from keywords
manual user management of internal channel IDs
local face swapping, canvas compositing, OCR, font, or pixel repair
changes to General Template, E-Commerce, Photography, or Standard semantics
production certification without real Provider/review evidence
```

The backend must first make channel authority safe and testable. Only then
may a thin Professional Mode UI be implemented on top of it.
