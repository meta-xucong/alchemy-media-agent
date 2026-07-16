# Professional Mode Implementation Handoff And Acceptance

## Status

```text
PROPOSED_IMPLEMENTATION_PLAN
DOCUMENT_ONLY
SUBORDINATE_TO_PRIMARY_PROFESSIONAL_MODE_SPEC
NO_PRODUCTION_ACTIVATION
```

This handoff turns the primary Professional Mode contract into bounded
implementation milestones. It does not create a second runtime architecture.
The first implementation milestone is deliberately Face Identity only; future
body, hair, styling, and other dimensions are separate optional modules.
The primary authority is:

`PROFESSIONAL_MODE_VISUAL_ASSET_LIBRARY_AND_PEOPLE_ASSET_MODULE_SPEC.md`

The implementation must target the current post-Doc140 shared V3 path, not an
older local-prompt interpretation:

```text
sanitized mode/asset evidence
  -> complete Remote Brain semantic task profile and activation intent
  -> frozen CapabilityActivationPlan
  -> complete signed canonical Provider prompt and hashes
  -> Human Realism preflight/re-signing when active
  -> exact GPT Image 2 Provider request
  -> shared real-pixel review, bounded retry, and final delivery
```

The Face Identity implementation contributes typed evidence and lifecycle
state only. It must not author prompt prose, add negatives, locally classify
the scene, patch retry prompts, or create a second reviewer/provider.

## 1. Execution Boundary

The only supported Professional Mode path is:

```text
explicit user mode choice
  -> select exactly one project People Asset
  -> require a user-confirmed active Face Identity module/pack version
  -> activate the declared capability before the V3 plan freezes
  -> use existing V3 planning / GPT Image 2 / review / retry / delivery
```

The Standard Mode path remains:

```text
no Professional Mode choice
  -> existing V3 planning / Provider / review / retry / delivery
  -> no People Asset lookup or Professional Mode metadata
```

Missing or invalid Professional Mode assets produce a safe blocked state. They
never trigger a Standard Mode fallback.

## 2. Milestones

### M0 — Contract And Red Tests

Before runtime work:

```text
freeze the mode precedence matrix
freeze project-scoped multiple-People-Asset semantics
freeze modular People Asset semantics with Face Identity as the only first-release module
freeze root guard + pack-support ordering
freeze user-confirmed pack activation
add Standard/Professional isolation red tests
freeze compatibility with Doc134/135/136/137/138/139/140 semantic and prompt
signing gates
```

### M1 — Project People Asset Catalog

Add only an additive project-scoped catalog/index:

```text
People Asset ID and project binding
module registry (Face Identity first; future modules additive)
root source/reference/output IDs
pack-version lifecycle pointers
consent and provenance summaries
active/superseded/blocked state
```

The catalog must reference existing Project/Reference/Output/History records.
It must not copy image bytes, create a second reference registry, or decide
Provider admission.

### M2 — Anchor Pack Preparation

The preparation flow is a bounded sequence:

```text
root source or protected text-only character direction
  -> three GPT Image 2 standard-front candidates
  -> likeness-first identity review and best-result selection
  -> three three-quarter candidates from root + winning front
  -> likeness-first three-quarter winner
  -> three profile candidates from root + winning front + winning three-quarter
  -> likeness-first profile winner
  -> per-view review and cross-view identity review
  -> user confirms activation of the complete passing Face Identity pack
```

View names constrain evidence coverage only. Remote Brain owns the complete
semantic task profile and canonical Provider prompt for each candidate. No
fixed camera, lighting, makeup, background, or cosmetic recipe may be added by
this module, and no local prompt fragment may fill a missing Brain decision.

The original uploaded portrait remains the root guard. Provider materialization
uses Doc93/95 evidence preparation; a generated white-background presentation
card is not sent as unrestricted full-frame evidence.

Each candidate must pass through the Remote Brain semantic task-profile and
capability-activation gates before planning. The candidate is not executable
until Remote Brain returns a complete canonical Provider prompt and verified
hash. If Human Realism is active, its semantic preflight and independent
natural-presence re-signing must also pass. The pack module supplies view and
identity evidence; it does not fill any missing semantic or prompt field
locally.

Only a user-confirmed `active` Face Identity pack version can enter
Professional Mode Provider inputs. Warning, failed, superseded, or unconfirmed
candidates remain append-only history. Body, hair, styling, and other future
modules are not inferred or activated in this milestone.

### M3 — Frozen-Plan Runtime Bridge

The bridge must:

```text
resolve one selected People Asset for the job
activate Professional Mode before CapabilityActivationPlan freeze
pass sanitized mode/asset/version evidence and approved face root/anchor
  reference IDs into the existing Remote Brain semantic task profile
require complete capability activation intent before plan freeze
pass only the typed identity evidence binding into existing V3 inputs
require exact canonical_provider_prompts[] and hashes before Provider
require Human Realism preflight/re-signing when that capability is active
preserve the selected asset/version in internal provenance
leave the public Brain request free of asset-library internals
```

It must not inject identity capability after planning, create a private retry
loop, author local prompt prose, use a keyword/heuristic fallback, or alter
General/E-Commerce/Photography role contracts. Local MCP/Codex Native may only
relay the same canonical prompt and reference hashes and remains
conversation-only/non-certifying.

### M4 — Template Consumers

General, E-Commerce, and Photography may expose the same small outer choice:

```text
Standard Mode
Professional Mode: use Visual Assets
```

In Professional Mode:

```text
General remains scenario-neutral
E-Commerce retains its own LLM-first deliverable/role semantics
Photography retains its own LLM-first role/profile semantics
Face Identity supplies face identity only in the first release
body, hair, styling, and other dimensions remain unclaimed until their own
future modules are explicitly activated
product, garment, scene, and photographer/profile truth remain owned by their
existing shared or specialized contracts
```

No vertical slot, role, platform, marketplace, A+, or photographer field may
be added to People Asset records.

### M5 — Acceptance And Future Video Handoff

Run cross-scene and cross-view face acceptance with real pixels, then document
the stable modular People Asset interface for a future Video module. The
first-release face pack does not certify body continuity, temporal consistency,
or video readiness.

## 3. Shared Capability Mapping

| Responsibility | Existing authority | Professional Mode addition |
| --- | --- | --- |
| Channel ownership | Doc93 | People Asset is identity-only by default; prompt owns hair, wardrobe, light, scene, camera, mood, and style. |
| Identity evidence | Doc95 | Root + approved pack views are routed through existing feature-detail/head-geometry evidence. |
| Identity metrics | Doc96 | Ephemeral/approved summaries only; no biometric vectors. |
| Continuity routing | Doc97 | Approved pack views become reviewed generated support; root guard remains. |
| Renderer | Doc100 | Existing GPT Image 2 only. |
| Plan freeze | Doc101 | Professional capability active before freeze; no late activation. The asset binding is typed evidence, not a local creative contribution. |
| Review evidence | Doc121 | Reviewer sees exactly the admitted evidence used for the candidate. |
| Human realism/safety | Doc128 | Shared constraints remain active; age change is prompt-owned and reviewed. |
| Semantic ownership | Doc134/135/140 | Remote Brain owns semantic judgment, task-profile completeness, activation intent, and creative direction; no local fallback or prompt fragments. |
| Canonical prompt | Doc135/136 | Provider receives only the complete Brain-signed canonical prompt and matching hash. |
| Human Realism gates | Doc137/138/139 | When active, semantic preflight and independent natural-presence re-signing are required before Provider/MCP. |
| Module extensibility | This document set | Face Identity is the only first-release module; each future dimension needs its own contract and activation. |

## 4. Required Failure Semantics

The job must be blocked or withheld when any of these occur:

```text
selected People Asset is missing, inactive, or belongs to another project
Face Identity module/pack version is not active and user-confirmed
root provenance is missing when an uploaded root exists
required view or cross-view identity review fails
unwanted-person pixels cannot be isolated from a non-identity reference
CapabilityActivationPlan was frozen before the Professional capability existed
Remote Brain semantic task profile or capability activation intent is incomplete
canonical Provider prompt is missing, stale, or hash-mismatched
required Human Realism semantic preflight or independent re-signing failed
Provider/review evidence continuity is incomplete
shared review or final-delivery gate fails
```

The job must not:

```text
fall back to Standard Mode
use an unreviewed or warning anchor as identity truth
replace the uploaded root with a generated output
retry indefinitely
use a keyword/heuristic semantic fallback or local prompt fragment
create a local pixel repair or face-swap path
claim certification from metadata-only review
```

## 5. Required Regression Matrix

### Standard Isolation

```text
Standard Mode with Professional Mode disabled is byte/contract compatible.
Standard Mode with the Professional package unavailable still runs.
Standard ProjectIdentityAnchor/SubjectIdentityCard behavior is unchanged.
Standard records never create or activate People Assets.
Professional metadata never enters Standard Brain/provider/review payloads.
```

### Professional Asset Lifecycle

```text
one project can create multiple People Assets
one job binds exactly one selected People Asset and active Face Identity module/pack version
three front candidates are append-only and scored
front scoring is likeness-first: same-person resemblance and distinctive
feature retention outrank polish, symmetry, and perfect framing
an over-perfect/generic AI face receives an explicit penalty and cannot win
solely on visual quality; modest head tilt remains a low-priority signal
the reviewer records human-realism, distinctive-feature, anti-overperfection,
visual-quality, and low-weight pose evidence alongside the primary likeness
three three-quarter candidates are generated only after a front winner and use
the root portrait plus that winner as admitted evidence
three profile candidates are generated only after a three-quarter winner and
use the root portrait plus both selected supplementary anchors as evidence
each supplementary role selects one likeness-first winner independently
a failed three-quarter stage blocks profile generation and pack activation
the typed generation request rejects missing, duplicated, reordered, or extra
evidence: front=root; three-quarter=root+front winner;
profile=root+front winner+three-quarter winner
Face Identity pack requires per-view and cross-view pass plus user activation
warning/failed/superseded/unconfirmed views cannot route to Provider
root provenance and consent remain auditable without raw paths or secrets
body/hair/styling modules are absent and cannot activate from legacy metadata
```

### Shared Runtime Compatibility

```text
activation is frozen before Professional contributions
Professional Mode binds sanitized mode/asset/version evidence before Brain
semantic planning
complete Remote Brain task profile and capability activation intent are
required before plan freeze
Face Identity emits no prompt additions, negative lists, retry prose, or
keyword-based activation
canonical Provider prompt and hash parity is verified before Provider/MCP
Human Realism preflight and independent re-signing are enforced when active
Provider receives GPT Image 2 requests only
first-release Provider inputs contain Face Identity evidence, not body/style locks
Doc95 evidence derivatives are used instead of synthetic matte cards
Reviewer receives the same admitted root/anchor evidence as Provider
shared retry remains bounded and append-only
Local MCP/Codex Native only relays the canonical prompt/reference hashes and
cannot re-plan or certify Professional Mode delivery
no local face swap, overlay, OCR, font, or private repair loop appears
```

### Cross-Template Isolation

```text
General remains scenario-neutral
E-Commerce retains its own LLM-first role/deliverable contract
Photography retains its own LLM-first role/profile contract
People Asset fields contain no slot/platform/marketplace/A+/photographer data
an explicit age change is reviewed as a same-person prompt transformation
an explicit different-person request blocks until asset/mode changes
```

### Shared-Contract Adaptation

Every future Standard Mode optimization must be classified before integration:

```text
Standard-only UI/default/heuristic change
  -> no Professional Mode behavior change

shared foundation contract change
  -> update this adapter, record supported contract versions, and rerun
     Professional Mode isolation/semantic/prompt-parity tests

unsupported shared contract change
  -> structured incompatibility block; never silently reinterpret an active pack
```

This keeps the Face Identity module reusable while preventing Standard Mode
defaults or local creative logic from leaking into Professional Mode.

## 6. Evidence And Release Gate

Source tests and mock contracts are not production certification. Before any
production claim, retain:

```text
pack version and user activation provenance
root/anchor source IDs and admitted Provider evidence
per-view and cross-view review results
shared retry history and final-winner evidence
real-pixel Provider/review status
template-specific acceptance evidence
Remote Brain semantic task profile, capability activation intent, canonical
prompt/hash, and Human Realism preflight/re-sign provenance
```

Professional Mode remains non-production until the existing GPT Image 2,
real-pixel review, template, and Provider gates are independently satisfied.

## 7. Mainline Handoff

The feature branch must hand the mainline maintainer:

```text
document-set commit(s)
compatibility matrix and authority statement
test list and exact results
explicit list of unchanged old documents
remaining implementation or real-provider blockers
```

Mainline integration must not edit old numbered documents to make them appear
compatible. If a shared contract truly needs change, it requires its own
architecture review and a separate authority decision.
